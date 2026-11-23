"""Append MaiIdentity's schema-1 Planner item without editing Host history."""
from datetime import datetime, timezone
import hmac
import json

from ..context.projection import render


def _item_id(item, ownership_key):
    # Sign the complete item except its ID, so edits by another hook are preserved.
    meta = dict(item["meta"])
    meta.pop("item_id", None)
    payload = json.dumps({**item, "meta": meta}, sort_keys=True, separators=(",", ":"))
    digest = hmac.digest(ownership_key, b"planner-item\0" + payload.encode("ascii"), "sha256")
    return "MaiIdentity-" + digest.hex()


def _owned(item, ownership_key):
    meta = item.get("meta")
    if item.get("item_type") != "SystemMessageItem" or not isinstance(meta, dict):
        return False
    item_id = meta.get("item_id")
    return (isinstance(item_id, str) and item_id.startswith("MaiIdentity-")
            and item_id == _item_id(item, ownership_key))


def inject(kwargs, facts, ownership_key):
    if type(kwargs.get("item_schema_version")) is not int or kwargs["item_schema_version"] != 1:
        return None
    items = kwargs.get("items")
    if type(items) is not list or any(type(item) is not dict for item in items):
        return None
    text = "MaiIdentity 身份参考：\n" + render(facts)
    if len(text) > 12000:
        return None
    item = {
        "item_type": "SystemMessageItem",
        "meta": {"logical_turn_id": None, "timestamp": datetime.now(timezone.utc).isoformat()},
        "parts": [{"type": "text", "text": text}],
    }
    item["meta"]["item_id"] = _item_id(item, ownership_key)
    remaining = [old for old in items if not _owned(old, ownership_key)]
    return {"action": "continue", "modified_kwargs": {**kwargs, "items": [*remaining, item]}}
