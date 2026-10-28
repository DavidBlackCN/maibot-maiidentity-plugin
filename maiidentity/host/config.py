from __future__ import annotations

from typing import Literal
from maibot_sdk import PluginConfigBase
from pydantic import ConfigDict, Field, field_validator, model_validator

from ..shared.core import AccountKey, Scope


class Section(PluginConfigBase):
    model_config = ConfigDict(extra="forbid", strict=True)


class PluginSection(Section):
    enabled: bool = True
    config_version: Literal["3"] = "3"
    acknowledgement: str = ""
    instance_id: str = ""
    writer_lock: str = ""
    migration_id: str = ""


class AccountEntry(Section):
    platform: Literal["qq"] = "qq"
    adapter_namespace: str
    account_id: str
    enabled: bool = True

    @model_validator(mode="after")
    def account(self):
        AccountKey(self.platform, self.adapter_namespace, self.account_id)
        return self


class IdentitySection(Section):
    adapter_namespace: str = "host-qq"
    route_scope: str = ""
    accounts: list[AccountEntry] = Field(default_factory=list)

    @field_validator("adapter_namespace")
    @classmethod
    def default_namespace(cls, value):
        return value or "host-qq"



class RoleEntry(Section):
    account: AccountEntry
    role: Literal["member", "trusted_contact", "stream_moderator", "operator_admin", "service_agent"]
    scope: dict

    @model_validator(mode="after")
    def scoped(self):
        Scope(**self.scope)
        return self


class RolesSection(Section):
    entries: list[RoleEntry] = Field(default_factory=list)


class ContextSection(Section):
    enabled: bool = True
    budget_bytes: int = Field(default=2048, ge=1200, le=8192)
    cache_ttl_seconds: int = Field(default=300, ge=10, le=3600)
    planner_actor_enabled: Literal[False] = False
    alias_enabled: Literal[False] = False
    guard_mode: Literal["context_only"] = "context_only"


class SecuritySection(Section):
    binding_challenge_enabled: Literal[False] = False
    raw_prompt_logging: Literal[False] = False


class IntegrationsSection(Section):
    enabled: Literal[False] = False
    cross_plugin_privileged_enabled: Literal[False] = False


class CompatibilitySection(Section):
    legacy_templates_enabled: Literal[False] = False


class ManagementSection(Section):
    # Local operator configuration. Empty means nobody may wake/replan Vita.
    vita_admin_accounts: list[str] = Field(default_factory=list,max_length=16)

    @field_validator('vita_admin_accounts')
    @classmethod
    def accounts(cls,value):
        from ..shared.core import qq
        for account in value: qq(account)
        if len(set(value))!=len(value): raise ValueError('duplicate admin account')
        return value


class MaiIdentityConfig(Section):
    plugin: PluginSection = Field(default_factory=PluginSection)
    identity: IdentitySection = Field(default_factory=IdentitySection)
    roles: RolesSection = Field(default_factory=RolesSection)
    context: ContextSection = Field(default_factory=ContextSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    compatibility: CompatibilitySection = Field(default_factory=CompatibilitySection)
    integrations: IntegrationsSection = Field(default_factory=IntegrationsSection)
    management: ManagementSection = Field(default_factory=ManagementSection)

    @model_validator(mode="after")
    def enabled_review(self):
        if self.plugin.enabled:
            from pathlib import Path
            from ..shared.core import opaque
            if self.plugin.writer_lock and not Path(self.plugin.writer_lock).is_absolute():
                raise ValueError("plugin.writer_lock must be absolute when specified")
            if self.plugin.instance_id:
                opaque(self.plugin.instance_id)
            opaque(self.identity.adapter_namespace)
            if self.identity.route_scope:
                opaque(self.identity.route_scope)
            if self.roles.entries and not self.plugin.instance_id:
                raise ValueError("explicit roles require plugin.instance_id matching their scope")
            for entry in self.identity.accounts:
                if entry.adapter_namespace != self.identity.adapter_namespace:
                    raise ValueError("account namespace differs from audited adapter namespace")
            for entry in self.roles.entries:
                if entry.scope["instance_id"] != self.plugin.instance_id or entry.scope["adapter_namespace"] != self.identity.adapter_namespace:
                    raise ValueError("role scope differs from deployment")
                if not entry.account.enabled or entry.scope["platform"] != entry.account.platform:
                    raise ValueError("role account must be enabled and match its scope platform")
                available = {(a.platform, a.adapter_namespace, a.account_id) for a in self.identity.accounts if a.enabled}
                if (entry.account.platform, entry.account.adapter_namespace, entry.account.account_id) not in available:
                    raise ValueError("role account must be explicitly present in enabled identity accounts")
        return self
