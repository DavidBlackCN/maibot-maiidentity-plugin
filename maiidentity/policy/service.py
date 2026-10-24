from __future__ import annotations

from dataclasses import dataclass
import uuid

from ..shared.core import AccountKey, Scope, opaque, require

MEMBER = {"identity.self.read", "binding.self.request", "relation.self.propose"}
ROLES = {
    "anonymous": {"identity.public.read"},
    "member": MEMBER,
    "trusted_contact": MEMBER,
    "stream_moderator": MEMBER | {"identity.stream.diagnostics.read"},
    "operator_admin": MEMBER | {"identity.binding.manage", "identity.role.manage", "identity.audit.read",
                                  "identity.delegation.manage", "relation.confirm.manage"},
    "service_agent": set(),
}
MAIVITA = {"maivita.private.read", "maivita.wake", "maivita.sleep.interrupt", "maivita.replan", "maivita.configure"}
MAIHUSH = {"maihush.mute", "maihush.renew", "maihush.unmute", "maihush.configure"}
# Operator-owned catalogue: declaration grants no role or permission.
CAPABILITIES = set().union(*ROLES.values()) | MAIVITA | MAIHUSH
NONDELEGABLE = {"identity.role.manage", "identity.binding.manage", "identity.delegation.manage", "relation.confirm.manage", "maivita.configure"} | MAIHUSH


def expand_roles(definitions: dict, role: str, visiting=None) -> set:
    visiting = set() if visiting is None else visiting
    require(role in definitions and role not in visiting, "INVALID_ROLE_GRAPH")
    visiting = visiting | {role}
    entry = definitions[role]
    capabilities = set(entry.get("capabilities", ()))
    require(capabilities <= CAPABILITIES, "UNKNOWN_CAPABILITY")
    for parent in entry.get("parents", ()):
        capabilities |= expand_roles(definitions, parent, visiting)
    return capabilities


@dataclass(frozen=True)
class Actor:
    """Domain value constructed only by a local trusted adapter, never wire parsing."""
    account: AccountKey
    subject_id: str
    binding_epoch: int
    authorization_revision: int
    expires_at: float


class PolicyService:
    def __init__(self, identity):
        self.identity, self.db = identity, identity.db

    def actor(self, controlled_account: AccountKey):
        binding = self.identity.lookup(controlled_account)
        require(binding is not None, "IDENTITY_UNRESOLVED")
        return Actor(controlled_account, binding["subject"], binding["epoch"], binding["revision"], self.db.clock.now()+30)

    def current(self, actor: Actor):
        require(type(actor) is Actor and self.db.clock.now() < actor.expires_at, "EVIDENCE_EXPIRED")
        binding = self.identity.lookup(actor.account)
        require(binding is not None and binding["subject"] == actor.subject_id
                and binding["epoch"] == actor.binding_epoch and binding["revision"] == actor.authorization_revision,
                "STALE_REVISION")

    def _bump(self, subject):
        self.db.conn.execute("UPDATE subjects SET revision=revision+1 WHERE id=?", (subject,))
        self.db.bump_policy()

    def definitions(self):
        result = {name: {"capabilities": sorted(caps), "parents": []} for name, caps in ROLES.items()}
        result.update({row["id"]: row for row in self.db.records("role_definition")})
        return result

    def define_role_operator(self, name, *, capabilities, parents, expected=None, key):
        opaque(name)
        require(name not in ROLES, "BUILTIN_ROLE_IMMUTABLE")
        payload = {"id": name, "capabilities": sorted(set(capabilities)), "parents": sorted(set(parents))}
        def apply():
            definitions = self.definitions() | {name: payload}
            for role in definitions:
                expand_roles(definitions, role)
            result = self.db.put("role_definition", name, payload, expected)
            self.db.conn.execute("UPDATE subjects SET revision=revision+1")
            self.db.bump_policy()
            self.db.audit("role.definition", name, {"revision": result["revision"]})
            return result
        return self.db.once(key, ["define_role", payload, expected], apply)

    def grant_operator(self, subject, capability, scope: Scope, *, key, effect="allow", delegable=False, expires=None):
        require(capability in CAPABILITIES and effect in ("allow", "deny"), "UNKNOWN_CAPABILITY")
        require(type(delegable) is bool and (not delegable or capability not in NONDELEGABLE), "NONDELEGABLE")
        opaque(subject)
        require(expires is None or expires > self.db.clock.now(), "EVIDENCE_EXPIRED")
        def apply():
            require(self.db.conn.execute("SELECT 1 FROM subjects WHERE id=? AND status='active'", (subject,)).fetchone() is not None, "IDENTITY_UNRESOLVED")
            ref = uuid.uuid4().hex
            result = self.db.put("grant", ref, {"id": ref, "subject": subject, "capability": capability, "scope": scope.data(),
                "effect": effect, "delegable": delegable, "expires": expires, "status": "active", "source": "operator_config"})
            self._bump(subject)
            self.db.audit("grant.operator", subject, {"capability": capability, "effect": effect})
            return result
        return self.db.once(key, ["grant", subject, capability, scope.data(), effect, delegable, expires], apply)

    def role_operator(self, subject, role, scope: Scope, *, key):
        require(role in self.definitions(), "UNKNOWN_ROLE")
        def apply():
            require(self.db.conn.execute("SELECT 1 FROM subjects WHERE id=?", (subject,)).fetchone() is not None, "IDENTITY_UNRESOLVED")
            ref = uuid.uuid4().hex
            result = self.db.put("role", ref, {"id": ref, "subject": subject, "role": role, "scope": scope.data(), "status": "active"})
            self._bump(subject)
            self.db.audit("role.operator", subject, {"role": role})
            return result
        return self.db.once(key, ["role", subject, role, scope.data()], apply)

    def assign_role(self, actor, target, role, scope, *, key, manageable_roles=()):
        require(target != actor.subject_id and role in manageable_roles and role in self.definitions(), "SELF_ESCALATION")
        def apply():
            require(self.authorize(actor, "identity.role.manage", scope, request_id=key)["allowed"], "PERMISSION_DENIED")
            for capability in expand_roles(self.definitions(), role):
                require(self.authorize(actor, capability, scope, request_id=key)["allowed"], "PERMISSION_DENIED")
            require(self.db.conn.execute("SELECT 1 FROM subjects WHERE id=? AND status='active'", (target,)).fetchone() is not None, "IDENTITY_UNRESOLVED")
            ref = uuid.uuid4().hex
            result = self.db.put("role", ref, {"id": ref, "subject": target, "role": role, "scope": scope.data(),
                                "status": "active", "issued_by": actor.subject_id})
            self._bump(target)
            self.db.audit("role.assigned", target, {"role": role})
            return result
        return self.db.once(key, ["assign_role", actor.subject_id, target, role, scope.data(), list(manageable_roles)], apply)

    def revoke(self, kind, ref, *, expected, key):
        require(kind in ("role", "grant"), "UNSUPPORTED")
        def apply():
            item = self.db.get(kind, ref)
            require(item is not None and item["revision"] == expected, "STALE_REVISION")
            item["status"] = "revoked"
            result = self.db.put(kind, ref, item, expected)
            self._bump(item["subject"])
            self.db.audit(kind+".revoked", ref, {})
            return result
        return self.db.once(key, ["revoke", kind, ref, expected], apply)

    def candidates(self, subject, capability, scope):
        now = self.db.clock.now()
        definitions = self.definitions()
        matches = [g for g in self.db.records("grant") if g["subject"] == subject and g["status"] == "active"
                   and g["capability"] == capability and (g["expires"] is None or g["expires"] > now)
                   and Scope(**g["scope"]).contains(scope)]
        roles = [r for r in self.db.records("role") if r["subject"] == subject and r["status"] == "active"
                 and r["role"] in definitions and capability in expand_roles(definitions, r["role"]) and Scope(**r["scope"]).contains(scope)]
        return matches, roles

    def authorize(self, actor, capability, scope: Scope, *, request_id, external_policy=None, host_allowed=True):
        from ..shared.core import Denied
        with self.db.guard:
            decision = {"allowed": False, "reason_code": "PERMISSION_DENIED", "actor_ref": None, "capability": capability,
                        "resource": [scope.resource_type, scope.resource_id], "scope": scope.data(), "request_id": request_id,
                        "policy_revision": self.db.policy_revision(), "authorization_revision": None,
                        "binding_epoch": None, "expires_at": self.db.clock.now()+10}
            try:
                opaque(request_id)
                require(capability in CAPABILITIES, "UNKNOWN_CAPABILITY")
                if capability in MAIHUSH:
                    require(scope.kind == 'stream' and scope.resource_type == 'group' and scope.platform == 'qq', 'SCOPE_MISMATCH')
                self.current(actor)
                require(scope.platform == actor.account.platform and scope.adapter_namespace == actor.account.adapter_namespace,
                        "SCOPE_MISMATCH")
                require(scope.subject_id in (None, actor.subject_id), "SCOPE_MISMATCH")
                decision.update(actor_ref=actor.subject_id, binding_epoch=actor.binding_epoch,
                                authorization_revision=actor.authorization_revision,
                                expires_at=min(actor.expires_at, decision["expires_at"]))
                grants, roles = self.candidates(actor.subject_id, capability, scope)
                require(not any(g["effect"] == "deny" for g in grants), "EXPLICIT_DENY")
                require(any(g["effect"] == "allow" for g in grants) or bool(roles), "PERMISSION_DENIED")
                require(host_allowed is True, "HOST_DENIED")
                if capability in MAIVITA | MAIHUSH:
                    require(external_policy is not None, "POLICY_UNAVAILABLE")
                    require(external_policy is True, "POLICY_DENIED")
                decision.update(allowed=True, reason_code="ALLOWED")
            except Denied as error:
                decision["reason_code"] = error.code
            return decision
