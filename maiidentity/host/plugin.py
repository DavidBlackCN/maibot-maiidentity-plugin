from __future__ import annotations

from pathlib import Path
import asyncio
import importlib.metadata
import os
import secrets
import uuid

from maibot_sdk import API, Command, HookHandler, MaiBotPlugin
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder

from .. import OLD_PLUGIN_ID
from ..context.projection import Projector, snapshot
from ..identity.messages import MessageResolver, host_message
from ..identity.service import BindingChallenges, IdentityService
from ..integrations.api import PublicAPI, descriptor
from ..policy.service import PolicyService
from ..relations.service import Relations
from ..shared.core import AccountKey, Scope, digest, qq, require
from ..storage.database import Database, WriterLease
from .config import MaiIdentityConfig


async def owned_io(function, *args, **kwargs):
    """Join worker I/O before cancellation cleanup releases its resources."""
    work = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        await work
        raise


class MaiIdentityPlugin(MaiBotPlugin):
    config_model = MaiIdentityConfig

    def __init__(self):
        super().__init__()
        self.db = self.lease = self.active = self.identity = self.policy = self.relations = None
        self.resolver = self.projector = self.challenges = None
        self.bot_account = ""
        self.data_lease = None
        self.ready = False

    def normalize_plugin_config(self, config_data):
        # Validate raw input before SDK normalization can discard old sections.
        MaiIdentityConfig.model_validate(config_data or {})
        return super().normalize_plugin_config(config_data)

    async def on_load(self):
        require(self.db is None and self.lease is None, "ALREADY_LOADED")
        cfg = self.config
        if not cfg.plugin.enabled:
            return
        try:
            require(os.environ.get('MAIBOT_HOST_VERSION') == '1.3.12', 'UNSUPPORTED_HOST')
            require(importlib.metadata.version("maibot-plugin-sdk") == "2.15.0", "UNSUPPORTED_SDK")
            loaded = await self.ctx.component.list_loaded_plugins()
            require(type(loaded) is list, "REGISTRY_UNAVAILABLE")
            for item in loaded:
                identity = item if type(item) is str else (item.get("plugin_id") or item.get("id") or item.get("name")) if type(item) is dict else None
                require(type(identity) is str and identity != OLD_PLUGIN_ID, "OLD_PLUGIN_ACTIVE")
            data = self.ctx.paths.data_dir
            require(isinstance(data, Path) and data.is_absolute(), "INVALID_DATA_ROOT")
            source = Path(__file__).resolve().parents[2]
            require(data.resolve() != source and source not in data.resolve().parents, "SOURCE_DATA_FORBIDDEN")
            self.lease = WriterLease(Path(cfg.plugin.writer_lock))
            await owned_io(self.lease.acquire)
            data.mkdir(parents=True, exist_ok=True)
            self.data_lease = WriterLease(data/"writer.lock")
            await owned_io(self.data_lease.acquire)
            from ..storage.activation import validate_activation
            await asyncio.to_thread(validate_activation, data, cfg.model_dump())
            path = data / "identity.db"
            # Assign inside the joined worker so cancellation cannot discard an
            # opened connection before the failure cleanup can see it.
            def open_database():
                self.db = Database(path, create=not path.exists())
            await owned_io(open_database)
            self.active = cfg.model_copy(deep=True)
            self.identity = IdentityService(self.db)
            self.policy = PolicyService(self.identity)
            self.relations = Relations(self.policy)
            self.challenges = BindingChallenges(self.identity)
            await owned_io(self._bootstrap)
            self.resolver = MessageResolver(ttl=cfg.context.cache_ttl_seconds)
            ownership_key = await owned_io(self._context_ownership_key)
            self.projector = Projector(cfg.context.budget_bytes, ownership_key=ownership_key)
            try:
                self.bot_account = qq(str(await self.ctx.config.get("bot.qq_account", "")))
            except Exception:
                self.bot_account = ""  # No self-bot evidence: author resolution disabled.
            self.ready = True
        except BaseException:
            await self.on_unload()
            raise

    def _context_ownership_key(self):
        # Persistent block ownership is NOT an identity/authorization key. It
        # only permits removal of this instance's earlier context after reload.
        with self.db.transaction():
            row = self.db.conn.execute("SELECT value FROM metadata WHERE key='context_ownership_key'").fetchone()
            if row is None:
                value = secrets.token_hex(32)
                self.db.conn.execute("INSERT INTO metadata VALUES('context_ownership_key',?)", (value,))
            else:
                value = row[0]
            key = bytes.fromhex(value)
            require(len(key) == 32, "STORAGE_UNAVAILABLE")
            return key

    def _bootstrap(self):
        cfg = self.active
        accounts = {AccountKey(e.platform, e.adapter_namespace, e.account_id).key for e in cfg.identity.accounts if e.enabled}
        for role in cfg.roles.entries:
            require(AccountKey(role.account.platform, role.account.adapter_namespace, role.account.account_id).key in accounts,
                    "ROLE_ACCOUNT_NOT_CONFIGURED")
        config_hash = digest({"accounts": [e.model_dump() for e in cfg.identity.accounts],
                              "roles": [e.model_dump() for e in cfg.roles.entries]})
        with self.db.transaction():
            old = self.db.get("bootstrap", "current")
            if old and old["hash"] == config_hash:
                return
            for binding in self.db.conn.execute("SELECT * FROM bindings WHERE method='operator_config'").fetchall():
                if binding["account"] not in accounts and binding["status"] == "active":
                    self.db.conn.execute("UPDATE bindings SET status='revoked',epoch=epoch+1 WHERE account=?", (binding["account"],))
                    self.policy._bump(binding["subject"])
            for role in self.db.records("role"):
                if role.get("config_origin") and role["status"] == "active":
                    role["status"] = "revoked"
                    self.db.put("role", role["id"], role, role["revision"])
                    self.policy._bump(role["subject"])
            for account in sorted(accounts):
                existing = self.db.conn.execute("SELECT * FROM bindings WHERE account=?", (account,)).fetchone()
                if existing:
                    # A revoked binding never reactivates just by reloading the
                    # same config. Changed config is an explicit local review.
                    self.db.conn.execute("UPDATE bindings SET status='active',epoch=epoch+? WHERE account=?",
                                         (int(existing["status"] != "active"), account))
                else:
                    sid = uuid.uuid4().hex
                    self.db.conn.execute("INSERT INTO subjects VALUES(?,'active',1)", (sid,))
                    self.db.conn.execute("INSERT INTO bindings VALUES(?,?,'active',1,'operator_config')", (account, sid))
            for entry in cfg.roles.entries:
                account = AccountKey(entry.account.platform, entry.account.adapter_namespace, entry.account.account_id)
                binding = self.identity.lookup(account)
                ref = uuid.uuid4().hex
                self.db.put("role", ref, {"id": ref, "subject": binding["subject"], "role": entry.role,
                    "scope": entry.scope, "status": "active", "config_origin": True})
                self.policy._bump(binding["subject"])
            self.db.put("bootstrap", "current", {"hash": config_hash}, old["revision"] if old else None)
            self.db.audit("bootstrap.reviewed", "current", {"revision": old["revision"]+1 if old else 1})

    async def on_unload(self):
        self.ready = False
        try:
            if self.resolver:
                self.resolver.close()
            if self.projector:
                self.projector.close()
            if self.challenges and self.db and self.db.conn is not None:
                await asyncio.to_thread(self.challenges.close)
        finally:
            try:
                if self.db:
                    await owned_io(self.db.close)
            finally:
                if self.data_lease:
                    self.data_lease.release()
                    self.data_lease = None
                if self.lease:
                    self.lease.release()
                self.db = self.lease = self.active = self.identity = self.policy = self.relations = None
                self.resolver = self.projector = self.challenges = None
                self.bot_account = ""

    async def on_config_update(self, scope, config_data, version):
        if scope != "self":
            return
        try:
            new = MaiIdentityConfig.model_validate(config_data)
        except BaseException:
            await self.on_unload()
            raise
        if self.active is not None and new != self.active:
            await self.on_unload()
            raise RuntimeError("RELOAD_REQUIRED")

    def _parse(self, raw):
        return host_message(raw, instance=self.active.plugin.instance_id,
                            namespace=self.active.identity.adapter_namespace, bot_account=self.bot_account,
                            route_scope=self.active.identity.route_scope)

    @HookHandler("chat.receive.after_process", name="maiidentity_observe", mode=HookMode.BLOCKING,
                 order=HookOrder.EARLY, error_policy=ErrorPolicy.SKIP)
    async def receive(self, message=None, **kwargs):
        if self.ready:
            try:
                self.resolver.observe(self._parse(message))
            except Exception:
                pass
        return None

    async def _inject(self, kwargs, stage):
        if not self.ready or not self.active.context.enabled:
            return None
        try:
            evidence = binding = visible = None
            if stage == "replyer" and kwargs.get("reply_message_id") and kwargs.get("session_id"):
                async def query(message_id, stream):
                    return await self.ctx.message.get_by_id(message_id, stream_id=stream)
                evidence, _ = await self.resolver.resolve(instance=self.active.plugin.instance_id, platform="qq",
                    namespace=self.active.identity.adapter_namespace, stream=kwargs["session_id"],
                    message_id=kwargs["reply_message_id"], query=query, parse=self._parse)
                if evidence:
                    binding = await asyncio.to_thread(self.identity.lookup, evidence.account)
                    if binding:
                        scope = Scope("stream", self.active.plugin.instance_id, "default", "qq",
                                      self.active.identity.adapter_namespace, "context", "default", evidence.stream_id)
                        visible = await asyncio.to_thread(self.relations.visible, binding["subject"], scope)
            return self.projector.inject(kwargs, snapshot(evidence, binding, visible, stage=stage))
        except Exception:
            return None  # Ordinary chat continues; raw prompt is never logged.

    @HookHandler("maisaka.replyer.before_request", name="maiidentity_replyer", error_policy=ErrorPolicy.SKIP)
    async def replyer(self, **kwargs):
        return await self._inject(kwargs, "replyer")

    @HookHandler("maisaka.planner.before_request", name="maiidentity_planner", error_policy=ErrorPolicy.SKIP)
    async def planner(self, **kwargs):
        return await self._inject(kwargs, "planner")

    @API("get_contract", public=True, version="1")
    async def get_contract(self, **kwargs):
        return descriptor(self.ready)

    @API("resolve_identity", public=True, version="1")
    async def resolve_identity(self, **kwargs):
        return PublicAPI().call("resolve_identity", **kwargs)

    @API("get_identity", public=True, version="1")
    async def get_identity(self, **kwargs):
        return PublicAPI().call("get_identity", **kwargs)

    @API("authorize", public=True, version="1")
    async def authorize(self, **kwargs):
        return PublicAPI().call("authorize", **kwargs)

    @API("get_confirmed_relations", public=True, version="1")
    async def get_confirmed_relations(self, **kwargs):
        return PublicAPI().call("get_confirmed_relations", **kwargs)

    @API("build_context", public=True, version="1")
    async def build_context(self, **kwargs):
        return PublicAPI().call("build_context", **kwargs)

    @API("get_diagnostics", public=True, version="1")
    async def get_diagnostics(self, **kwargs):
        return PublicAPI().call("get_diagnostics", **kwargs)

    @Command("owner_auth_status", pattern=r"^/(?:owner_auth_status|maiidentity_status)\s*$", description="MaiIdentity 脱敏只读状态")
    async def status(self, stream_id="", **kwargs):
        if not stream_id:
            return True, "MaiIdentity status: no target stream", 1
        text = "MaiIdentity 3.0.0；"+("已就绪" if self.ready else "未启用")+"；跨插件特权关闭；上下文不是执行许可。"
        try:
            sent = await self.ctx.send.text(text, stream_id)
            return True, "public status sent" if sent is True else "normal send denied", 1
        except Exception:
            return True, "normal send unavailable", 1
