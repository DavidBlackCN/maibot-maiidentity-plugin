import tomllib

import pytest

from maiidentity.compatibility.migration import activate, apply, preview
from maiidentity.host.config import MaiIdentityConfig
from maiidentity.host.plugin import MaiIdentityPlugin
from maiidentity.shared.core import AccountKey
from maibot_sdk.context import PluginContext, PluginPaths
from .conftest import scope
from .test_migration_lifecycle import context


@pytest.mark.asyncio
async def test_explicit_local_bootstrap_new_admin_only_not_legacy_owner(tmp_path):
    source = tmp_path/"legacy.toml"; source.write_text('[user1]\nqq="10001"\nnickname="主人"', encoding="utf-8")
    target = tmp_path/"stage"
    apply(preview(source, namespace="adapter", instance="instance"), target)
    bootstrap = tmp_path/"local-bootstrap.toml"
    bootstrap.write_text('''[[identity.accounts]]
adapter_namespace = "adapter"
account_id = "10004"
[[roles.entries]]
role = "operator_admin"
account = {adapter_namespace="adapter", account_id="10004"}
scope = {kind="instance", instance_id="instance", character_id="default", platform="qq", adapter_namespace="adapter", resource_type="context", resource_id="default"}
''', encoding="utf-8")
    activate(target, writer_lock=tmp_path/"writer.lock", route_scope="route", bootstrap_config=bootstrap)
    cfg = MaiIdentityConfig.model_validate(tomllib.loads((target/"config.toml").read_text(encoding="utf-8")))
    rpc_context, _ = context(tmp_path)
    rpc_context.paths = PluginPaths(target/"data", tmp_path/"runtime")
    plugin = MaiIdentityPlugin(); plugin._set_context(rpc_context); plugin.set_plugin_config(cfg.model_dump())
    await plugin.on_load()
    try:
        local_admin = plugin.policy.actor(AccountKey("qq", "adapter", "10004"))
        old_owner = plugin.policy.actor(AccountKey("qq", "adapter", "10001"))
        assert plugin.policy.authorize(local_admin, "identity.role.manage", scope(), request_id="admin")["allowed"]
        assert not plugin.policy.authorize(old_owner, "identity.role.manage", scope(), request_id="legacy")["allowed"]
        assert not plugin.policy.authorize(local_admin, "maivita.configure", scope(), request_id="configure", external_policy=True)["allowed"]
        assert plugin.db.conn.execute("SELECT COUNT(*) FROM audit WHERE kind='activation.bootstrap_config'").fetchone()[0] == 1
    finally:
        await plugin.on_unload()
