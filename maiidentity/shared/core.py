from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import time


class Denied(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if condition is not True:
        raise Denied(code)


def opaque(value: str) -> str:
    require(type(value) is str and 0 < len(value) <= 256 and value.strip() == value
            and not any(ord(c) < 32 for c in value) and "*" not in value, "INVALID_ID")
    return value


def qq(value: str) -> str:
    require(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value) is not None, "INVALID_ACCOUNT_ID")
    return value


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Clock:
    def now(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()

    def iso(self) -> str:
        return datetime.fromtimestamp(self.now(), timezone.utc).isoformat()


@dataclass(frozen=True)
class AccountKey:
    platform: str
    adapter_namespace: str
    account_id: str

    def __post_init__(self):
        opaque(self.platform)
        opaque(self.adapter_namespace)
        opaque(self.account_id)
        if self.platform == "qq":
            qq(self.account_id)

    @property
    def key(self) -> str:
        return canonical(asdict(self))


@dataclass(frozen=True)
class Scope:
    kind: str
    instance_id: str
    character_id: str
    platform: str
    adapter_namespace: str
    resource_type: str
    resource_id: str
    stream_id: str | None = None
    subject_id: str | None = None

    def __post_init__(self):
        require(self.kind in ("instance", "stream", "self"), "SCOPE_MISMATCH")
        for name in ("instance_id", "character_id", "platform", "adapter_namespace", "resource_type", "resource_id"):
            opaque(getattr(self, name))
        if self.kind in ("stream", "self"):
            opaque(self.stream_id)
        if self.kind == "self":
            opaque(self.subject_id)
        if self.stream_id is not None:
            opaque(self.stream_id)
        if self.subject_id is not None:
            opaque(self.subject_id)

    def contains(self, other: Scope) -> bool:
        fixed = ("instance_id", "character_id", "platform", "adapter_namespace", "resource_type", "resource_id")
        return (all(getattr(self, n) == getattr(other, n) for n in fixed)
                and (self.kind == "instance" or other.kind in ("stream", "self"))
                and (self.stream_id is None or self.stream_id == other.stream_id)
                and (self.subject_id is None or self.subject_id == other.subject_id))

    def intersection(self, other: Scope) -> Scope | None:
        fixed = ("instance_id", "character_id", "platform", "adapter_namespace", "resource_type", "resource_id")
        if any(getattr(self, n) != getattr(other, n) for n in fixed):
            return None
        values = {name: getattr(self, name) for name in fixed}
        for name in ("stream_id", "subject_id"):
            left, right = getattr(self, name), getattr(other, name)
            if left is not None and right is not None and left != right:
                return None
            values[name] = left if left is not None else right
        kind = "self" if values["stream_id"] and values["subject_id"] else "stream" if values["stream_id"] else "instance"
        return Scope(kind=kind, **values)

    def data(self) -> dict:
        return asdict(self)
