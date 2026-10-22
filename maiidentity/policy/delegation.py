from __future__ import annotations

import math
import uuid

from ..shared.core import Scope, canonical, digest, opaque, require
from .service import MAIVITA, NONDELEGABLE


class Delegations:
    """Local atomic reserve/receipt port; no external side effects or scheduler."""
    def __init__(self, policy):
        self.policy, self.db = policy, policy.db

    def create(self, actor, *, delegatee, capability, scope: Scope, purpose, expires, max_uses, budget, key,
               parameters, parent_ref=None, caller_plugin_id=None):
        require(parent_ref is None and capability not in NONDELEGABLE, "NONDELEGABLE")
        opaque(delegatee)
        opaque(purpose)
        if caller_plugin_id is not None:
            opaque(caller_plugin_id)
        require(type(max_uses) is int and max_uses > 0 and type(budget) in (int, float)
                and math.isfinite(budget) and budget >= 0 and type(expires) in (int, float)
                and self.db.clock.now() < expires, "INVALID_CONSTRAINT")
        def apply():
            self.policy.current(actor)
            grants, _ = self.policy.candidates(actor.subject_id, capability, scope)
            require(not any(g["effect"] == "deny" for g in grants), "EXPLICIT_DENY")
            candidates = [g for g in grants if g["effect"] == "allow" and g["delegable"]
                          and (g["expires"] is None or expires <= g["expires"])]
            require(bool(candidates), "PERMISSION_DENIED")
            ref = uuid.uuid4().hex
            data = {"id": ref, "delegator": actor.subject_id, "account": actor.account.key,
                    "epoch": actor.binding_epoch, "authorization_revision": actor.authorization_revision,
                    "policy_revision": self.db.policy_revision(), "delegatee": delegatee, "caller_plugin_id": caller_plugin_id,
                    "capability": capability, "scope": scope.data(), "purpose": purpose,
                    "not_before": self.db.clock.now(), "expires": expires, "max_uses": max_uses,
                    "budget": budget, "used": 0, "spent": 0, "status": "active", "parameters_hash": digest(parameters)}
            result = self.db.put("delegation", ref, data)
            self.db.audit("delegation.created", ref, {"capability": capability, "max_uses": max_uses})
            return result
        return self.db.once(key, ["delegate", actor.subject_id, delegatee, capability, scope.data(), purpose,
                                  expires, max_uses, budget, caller_plugin_id, parameters], apply)

    def revoke(self, ref, actor, *, expected, key):
        def apply():
            self.policy.current(actor)
            item = self.db.get("delegation", ref)
            require(item is not None and item["delegator"] == actor.subject_id and item["revision"] == expected, "PERMISSION_DENIED")
            item["status"] = "revoked"
            result = self.db.put("delegation", ref, item, expected)
            self.db.audit("delegation.revoked", ref, {})
            return result
        return self.db.once(key, ["revoke_delegation", ref, actor.subject_id, expected], apply)

    def reserve(self, ref, *, delegatee, caller_plugin_id, capability, scope, purpose, cost, parameters, key,
                expected_revision=1, external_policy=None):
        require(type(cost) in (int, float) and math.isfinite(cost) and cost >= 0, "INVALID_CONSTRAINT")
        payload = ["reserve", ref, delegatee, caller_plugin_id, capability, scope.data(), purpose, cost, parameters, expected_revision]
        def apply():
            from ..shared.core import AccountKey
            import json
            item = self.db.get("delegation", ref)
            require(item is not None and item["status"] == "active" and item["revision"] == expected_revision, "STALE_REVISION")
            require(item["delegatee"] == delegatee and item["caller_plugin_id"] == caller_plugin_id
                    and item["capability"] == capability and item["purpose"] == purpose, "PERMISSION_DENIED")
            require(Scope(**item["scope"]).contains(scope), "SCOPE_MISMATCH")
            require(item["parameters_hash"] == digest(parameters), "PARAMETERS_CHANGED")
            now = self.db.clock.now()
            require(item["not_before"] <= now < item["expires"], "EVIDENCE_EXPIRED")
            require(item["used"] < item["max_uses"] and item["spent"]+cost <= item["budget"], "BUDGET_EXHAUSTED")
            require(not any(a["grant_ref"] == ref and a["state"] in ("executing", "unknown")
                            for a in self.db.records("attempt")), "RECONCILIATION_REQUIRED")
            account = AccountKey(**json.loads(item["account"]))
            require(self.policy.identity.lookup(account) is not None, "STALE_REVISION")
            actor = self.policy.actor(account)
            require(actor.binding_epoch == item["epoch"] and actor.authorization_revision == item["authorization_revision"]
                    and self.db.policy_revision() == item["policy_revision"], "STALE_REVISION")
            decision = self.policy.authorize(actor, capability, scope, request_id=key, external_policy=external_policy)
            require(decision["allowed"], decision["reason_code"])
            item["used"] += 1
            item["spent"] += cost
            # Consumption does not change grant revision; revocation does.
            self.db.conn.execute("UPDATE records SET data=? WHERE kind='delegation' AND id=?",
                                 (canonical(item), ref))
            attempt = {"id": key, "grant_ref": ref, "parameters_hash": digest(parameters), "state": "executing"}
            self.db.put("attempt", key, attempt)
            self.db.audit("delegation.reserved", ref, {"cost": cost})
            return {"attempt_ref": key, "grant_ref": ref, "state": "executing"}
        # An idempotent replay reports the old reservation; it never authorizes
        # another application. Executors must consult the durable attempt state.
        result = self.db.once(key, payload, apply)
        current = self.db.get("attempt", result["attempt_ref"])
        return {**result, "state": current["state"], "reservation_only": True, "external_execution_authorized": False}

    def receipt(self, attempt_ref, *, state, key):
        require(state in ("succeeded", "failed", "unknown", "cancelled"), "INVALID_STATE")
        def apply():
            item = self.db.get("attempt", attempt_ref)
            require(item is not None and item["state"] == "executing", "RECONCILIATION_REQUIRED")
            item["state"] = state
            result = self.db.put("attempt", attempt_ref, item, item["revision"])
            self.db.audit("delegation.receipt", attempt_ref, {"state": state})
            return result
        return self.db.once(key, ["receipt", attempt_ref, state], apply)

    def reconcile(self, attempt_ref, *, state, evidence_ref, key):
        require(state in ("succeeded", "failed"), "INVALID_STATE")
        opaque(evidence_ref)
        def apply():
            item = self.db.get("attempt", attempt_ref)
            require(item is not None and item["state"] == "unknown", "RECONCILIATION_REQUIRED")
            item.update(state=state, evidence_ref=evidence_ref)
            result = self.db.put("attempt", attempt_ref, item, item["revision"])
            self.db.audit("delegation.reconciled", attempt_ref, {"state": state})
            return result
        return self.db.once(key, ["reconcile", attempt_ref, state, evidence_ref], apply)
