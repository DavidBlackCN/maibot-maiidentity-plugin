from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3
import threading

from ..shared.core import Clock, Denied, canonical, digest, require


class WriterLease:
    """OS advisory lock; the persistent file is never unlinked while held."""
    def __init__(self, path: Path):
        self.path, self.handle = path, None

    def acquire(self):
        require(self.handle is None, "WRITER_LOCKED")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            handle.close()
            raise Denied("WRITER_LOCKED")
        self.handle = handle

    def release(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None


SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE subjects(id TEXT PRIMARY KEY, status TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE bindings(account TEXT PRIMARY KEY, subject TEXT NOT NULL REFERENCES subjects(id),
 status TEXT NOT NULL, epoch INTEGER NOT NULL, method TEXT NOT NULL);
CREATE TABLE records(kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
 data TEXT NOT NULL, PRIMARY KEY(kind,id));
CREATE TABLE idempotency(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE audit(seq INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL,
 target_ref TEXT NOT NULL, summary TEXT NOT NULL);
"""


class Database:
    def __init__(self, path: Path, *, create: bool = False, clock=None):
        self.path, self.clock = Path(path), clock or Clock()
        self.guard = threading.RLock()
        self.conn = None
        exists = self.path.exists()
        require(exists or create, "STORAGE_UNAVAILABLE")
        if create:
            require(not exists, "TARGET_EXISTS")
        try:
            self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=2)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")
            if create:
                self.conn.executescript("BEGIN IMMEDIATE;" + SCHEMA + "PRAGMA user_version=1; COMMIT;")
                self.conn.execute("INSERT INTO metadata VALUES('policy_revision','1')")
            require(self.conn.execute("PRAGMA user_version").fetchone()[0] == 1, "UNKNOWN_SCHEMA")
            require(self.conn.execute("PRAGMA quick_check").fetchone()[0] == "ok", "STORAGE_UNAVAILABLE")
            self.conn.execute("SELECT key,value FROM metadata").fetchall()
        except BaseException:
            self.close()
            raise

    @contextmanager
    def transaction(self):
        with self.guard:
            require(self.conn is not None, "STORAGE_UNAVAILABLE")
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    def get(self, kind: str, ref: str):
        with self.guard:
            require(self.conn is not None, "STORAGE_UNAVAILABLE")
            row = self.conn.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, ref)).fetchone()
            return json.loads(row[0]) if row else None

    def records(self, kind: str):
        with self.guard:
            require(self.conn is not None, "STORAGE_UNAVAILABLE")
            return [json.loads(r[0]) for r in self.conn.execute("SELECT data FROM records WHERE kind=? ORDER BY id", (kind,))]

    def put(self, kind: str, ref: str, data: dict, expected: int | None = None):
        old = self.get(kind, ref)
        require((old is None and expected is None) or (old is not None and old["revision"] == expected), "STALE_REVISION")
        data = {**data, "revision": (old["revision"] + 1 if old else 1)}
        self.conn.execute("INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET revision=excluded.revision,data=excluded.data",
                          (kind, ref, data["revision"], canonical(data)))
        return data

    def audit(self, kind: str, target: str, summary: dict):
        # Account IDs, message bodies, challenges and proofs never enter audit.
        self.conn.execute("INSERT INTO audit(at,kind,target_ref,summary) VALUES(?,?,?,?)",
                          (self.clock.iso(), kind, digest(target)[:16], canonical(summary)))

    def once(self, key: str, payload, operation):
        require(type(key) is str and 0 < len(key) <= 256, "INVALID_IDEMPOTENCY_KEY")
        fingerprint = digest(payload)
        with self.transaction():
            old = self.conn.execute("SELECT fingerprint,result FROM idempotency WHERE key=?", (key,)).fetchone()
            if old:
                require(old[0] == fingerprint, "IDEMPOTENCY_CONFLICT")
                return json.loads(old[1])
            result = operation()
            self.conn.execute("INSERT INTO idempotency VALUES(?,?,?)", (key, fingerprint, canonical(result)))
            return result

    def policy_revision(self):
        with self.guard:
            require(self.conn is not None, "STORAGE_UNAVAILABLE")
            return int(self.conn.execute("SELECT value FROM metadata WHERE key='policy_revision'").fetchone()[0])

    def bump_policy(self):
        self.conn.execute("UPDATE metadata SET value=CAST(value AS INTEGER)+1 WHERE key='policy_revision'")

    def close(self):
        with self.guard:
            if self.conn is not None:
                self.conn.close()
                self.conn = None
