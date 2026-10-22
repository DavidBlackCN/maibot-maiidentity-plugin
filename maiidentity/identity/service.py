from __future__ import annotations

import hashlib
import secrets
import uuid

from ..shared.core import AccountKey, opaque, require


class IdentityService:
    def __init__(self, db):
        self.db = db

    def bind_operator(self, account: AccountKey, *, key: str, subject: str | None = None, method="operator_config"):
        require(method in ("operator_config", "operator_override"), "UNTRUSTED_CONTEXT")
        if subject is not None:
            opaque(subject)
        def apply():
            old = self.db.conn.execute("SELECT * FROM bindings WHERE account=?", (account.key,)).fetchone()
            if old:
                require(old["status"] != "active" or subject in (None, old["subject"]), "BINDING_CONFLICT")
                require(subject in (None, old["subject"]), "BINDING_CONFLICT")
                sid = old["subject"]
                epoch = old["epoch"] + (old["status"] != "active")
            else:
                sid, epoch = subject or uuid.uuid4().hex, 1
            self.db.conn.execute("INSERT OR IGNORE INTO subjects VALUES(?,'active',1)", (sid,))
            self.db.conn.execute("INSERT INTO bindings VALUES(?,?,'active',?,?) ON CONFLICT(account) DO UPDATE SET status='active',epoch=excluded.epoch,method=excluded.method",
                                 (account.key, sid, epoch, method))
            self.db.audit("binding.operator", sid, {"method": method, "epoch": epoch})
            return {"subject_id": sid, "epoch": epoch}
        return self.db.once(key, ["bind", account.key, subject, method], apply)

    def lookup(self, account: AccountKey):
        with self.db.guard:
            require(self.db.conn is not None, "STORAGE_UNAVAILABLE")
            row = self.db.conn.execute("SELECT b.*,s.revision,s.status AS subject_status FROM bindings b JOIN subjects s ON b.subject=s.id WHERE account=?", (account.key,)).fetchone()
            return dict(row) if row and row["status"] == row["subject_status"] == "active" else None

    def revoke(self, account: AccountKey, *, expected_epoch: int, key: str):
        def apply():
            row = self.lookup(account)
            require(row is not None and row["epoch"] == expected_epoch, "STALE_REVISION")
            self.db.conn.execute("UPDATE bindings SET status='revoked',epoch=epoch+1 WHERE account=?", (account.key,))
            self.db.conn.execute("UPDATE subjects SET revision=revision+1 WHERE id=?", (row["subject"],))
            self.db.audit("binding.revoked", row["subject"], {"epoch": expected_epoch + 1})
            return {"epoch": expected_epoch + 1}
        return self.db.once(key, ["revoke", account.key, expected_epoch], apply)


class BindingChallenges:
    """Domain-only bilateral control protocol. No public command or API enables it."""
    def __init__(self, identity):
        self.identity, self.db = identity, identity.db

    def request(self, original: AccountKey, candidate: AccountKey, *, instance: str, request_id: str):
        opaque(instance)
        opaque(request_id)
        require(original != candidate, "BINDING_CONFLICT")
        with self.db.transaction():
            binding = self.identity.lookup(original)
            require(binding is not None and self.identity.lookup(candidate) is None, "BINDING_CONFLICT")
            active = [c for c in self.db.records("challenge") if c["status"] == "pending" and c["expires"] > self.db.clock.now()
                      and (original.key in (c["original"], c["candidate"]) or candidate.key in (c["original"], c["candidate"]))]
            require(not active, "RATE_LIMITED")
            ref = uuid.uuid4().hex
            tokens = {"original": secrets.token_urlsafe(32), "candidate": secrets.token_urlsafe(32)}
            data = {"id": ref, "original": original.key, "candidate": candidate.key, "subject": binding["subject"],
                    "epoch": binding["epoch"], "instance": instance, "request": request_id, "purpose": "bind_account",
                    "hashes": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in tokens.items()},
                    "confirmed": [], "failures": 0, "expires": self.db.clock.now()+300, "status": "pending"}
            self.db.put("challenge", ref, data)
            self.db.audit("binding.requested", ref, {"method": "bilateral_control"})
            return ref, tokens

    def confirm(self, ref, *, controlled_account: AccountKey, token: str, instance: str, request_id: str):
        # controlled_account MUST come from a trusted private transport adapter.
        with self.db.transaction():
            data = self.db.get("challenge", ref)
            require(data is not None and data["status"] == "pending", "CHALLENGE_INVALID")
            require(data["expires"] > self.db.clock.now(), "EVIDENCE_EXPIRED")
            require(data["instance"] == instance and data["request"] == request_id, "UNTRUSTED_CONTEXT")
            side = next((s for s in ("original", "candidate") if data[s] == controlled_account.key), None)
            valid = side is not None and secrets.compare_digest(data["hashes"][side], hashlib.sha256(token.encode()).hexdigest())
            if not valid:
                data["failures"] += 1
                if data["failures"] >= 5:
                    data["status"] = "expired"
                self.db.put("challenge", ref, data, data["revision"])
                return {"confirmed": False, "reason": "CHALLENGE_INVALID"}
            require(side not in data["confirmed"], "CHALLENGE_REPLAY")
            data["confirmed"].append(side)
            if len(data["confirmed"]) == 2:
                original = self.db.conn.execute("SELECT * FROM bindings WHERE account=?", (data["original"],)).fetchone()
                require(original["status"] == "active" and original["epoch"] == data["epoch"], "STALE_REVISION")
                require(self.db.conn.execute("SELECT 1 FROM bindings WHERE account=?", (data["candidate"],)).fetchone() is None, "BINDING_CONFLICT")
                self.db.conn.execute("INSERT INTO bindings VALUES(?,?,'active',1,'bilateral_control')", (data["candidate"], data["subject"]))
                self.db.conn.execute("UPDATE subjects SET revision=revision+1 WHERE id=?", (data["subject"],))
                data["status"], data["hashes"] = "active", {}
                self.db.audit("binding.confirmed", ref, {"method": "bilateral_control"})
            self.db.put("challenge", ref, data, data["revision"])
            return {"confirmed": data["status"] == "active"}

    def close(self):
        with self.db.transaction():
            for c in self.db.records("challenge"):
                if c["status"] == "pending":
                    c.update(status="expired", hashes={})
                    self.db.put("challenge", c["id"], c, c["revision"])
