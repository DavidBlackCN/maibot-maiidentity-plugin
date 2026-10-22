from __future__ import annotations

import uuid

from ..shared.core import Denied, Scope, opaque, require

TYPES = {"owner_label", "maintainer_label", "friend", "family", "partner"}


class Relations:
    def __init__(self, policy):
        self.policy, self.db = policy, policy.db

    def propose(self, actor, right, relation_type, scope, *, visibility, domain, key, expires=None):
        self.policy.current(actor)
        opaque(right)
        require(right != actor.subject_id and relation_type in TYPES, "INVALID_RELATION")
        require(visibility in ("public", "participants") and domain in ("user_declared", "character_roleplay"), "INVALID_RELATION")
        require(expires is None or expires > self.db.clock.now(), "EVIDENCE_EXPIRED")
        require(not right.startswith("character:") or domain == "character_roleplay", "INVALID_RELATION")
        def apply():
            self.policy.current(actor)
            ref = uuid.uuid4().hex
            data = {"id": ref, "left": actor.subject_id, "right": right, "relation_type": relation_type,
                    "scope": scope.data(), "domain": domain, "visibility": visibility, "status": "pending_confirmation",
                    "confirmations": [actor.subject_id], "confirmation_method": None, "evidence_refs": [],
                    "created_by": actor.subject_id, "created_at": self.db.clock.iso(), "confirmed_at": None,
                    "expires": expires, "revoked_at": None}
            result = self.db.put("relation", ref, data)
            self.db.audit("relation.proposed", ref, {"type": relation_type})
            return result
        return self.db.once(key, ["relation", actor.subject_id, right, relation_type, scope.data(), visibility, domain, expires], apply)

    def _complete(self, data, expected):
        pair = sorted([data["left"], data["right"]])
        for other in self.db.records("relation"):
            if (other["id"] != data["id"] and sorted([other["left"], other["right"]]) == pair
                    and other["relation_type"] == data["relation_type"] and other["scope"] == data["scope"]
                    and other["status"] == "confirmed" and (other["expires"] is None or other["expires"] > self.db.clock.now())):
                raise Denied("RELATION_CONFLICT")
        data.update(status="confirmed", confirmed_at=self.db.clock.iso())
        result = self.db.put("relation", data["id"], data, expected)
        self.db.audit("relation.confirmed", data["id"], {"method": data["confirmation_method"]})
        return result

    def confirm(self, ref, actor, *, expected, evidence_ref, key, character_rule=False):
        opaque(evidence_ref)
        def apply():
            self.policy.current(actor)
            data = self.db.get("relation", ref)
            require(data is not None and data["revision"] == expected and data["status"] == "pending_confirmation", "STALE_REVISION")
            require(data["expires"] is None or data["expires"] > self.db.clock.now(), "EVIDENCE_EXPIRED")
            character = data["right"].startswith("character:")
            if character:
                require(character_rule is True and actor.subject_id == data["left"], "PERMISSION_DENIED")
                data["confirmation_method"] = "user_and_operator_character_rule"
            else:
                require(actor.subject_id == data["right"] and actor.subject_id not in data["confirmations"], "PERMISSION_DENIED")
                data["confirmations"].append(actor.subject_id)
                data["confirmation_method"] = "bilateral_control"
            data["evidence_refs"].append(evidence_ref)
            return self._complete(data, expected)
        return self.db.once(key, ["confirm_relation", ref, actor.subject_id, expected, evidence_ref, character_rule], apply)

    def confirm_operator(self, ref, *, expected, evidence_ref, key):
        """Offline local operator path, never labeled bilateral confirmation."""
        opaque(evidence_ref)
        def apply():
            data = self.db.get("relation", ref)
            require(data is not None and data["revision"] == expected and data["status"] == "pending_confirmation", "STALE_REVISION")
            require(data["expires"] is None or data["expires"] > self.db.clock.now(), "EVIDENCE_EXPIRED")
            data.update(confirmation_method="operator_config", evidence_refs=[evidence_ref])
            return self._complete(data, expected)
        return self.db.once(key, ["operator_relation", ref, expected, evidence_ref], apply)

    def revoke(self, ref, actor, *, expected, key, reason="participant_request"):
        def apply():
            self.policy.current(actor)
            data = self.db.get("relation", ref)
            require(data is not None and data["revision"] == expected, "STALE_REVISION")
            require(actor.subject_id in (data["left"], data["right"]), "PERMISSION_DENIED")
            data.update(status="revoked", revoked_at=self.db.clock.iso(), revoked_reason=reason)
            result = self.db.put("relation", ref, data, expected)
            self.db.put("relation_event", uuid.uuid4().hex, {"relation_ref": ref, "relation_revision": result["revision"], "kind": "revoked"})
            self.db.audit("relation.revoked", ref, {})
            return result
        return self.db.once(key, ["revoke_relation", ref, actor.subject_id, expected, reason], apply)

    def visible(self, subject, scope, *, viewer=None):
        """Public model projection always passes viewer=None; no private hints."""
        if subject is None:
            return {"relations": [], "relation_state": "unresolved", "completeness": "visible_scope_only", "relation_revision": None}
        visible = [r for r in self.db.records("relation") if subject in (r["left"], r["right"])
                   and r["status"] in ("confirmed", "disputed") and (r["expires"] is None or r["expires"] > self.db.clock.now())
                   and Scope(**r["scope"]).contains(scope)
                   and (r["visibility"] == "public" or viewer in (r["left"], r["right"]))]
        # A visible contradiction is neutralized. No timestamp-based winner.
        partners = {r["right"] if r["left"] == subject else r["left"] for r in visible if r["relation_type"] == "partner"}
        disputed = any(r["status"] == "disputed" for r in visible) or len(partners) > 1
        return {"relations": [] if disputed else [{"type": r["relation_type"], "domain": r["domain"],
                    "confirmation_method": r["confirmation_method"], "revision": r["revision"]} for r in visible],
                "relation_state": "disputed" if disputed else "confirmed" if visible else "none_confirmed",
                "completeness": "visible_scope_only", "relation_revision": max((r["revision"] for r in visible), default=0)}
