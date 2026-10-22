from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import tomllib
import uuid

from .. import OLD_PLUGIN_ID, PLUGIN_ID
from ..identity.service import IdentityService
from ..shared.core import AccountKey, Denied, canonical, digest, opaque, qq, require
from ..storage.database import Database, WriterLease


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2))
        handle.flush()
        os.fsync(handle.fileno())


def atomic_json(path, value):
    temp = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    write_json(temp, value)
    os.replace(temp, path)


def legacy_id(value, *, empty=False):
    if empty and value in (None, ""):
        return ""
    require(type(value) in (str, int) and type(value) is not bool, "INVALID_ACCOUNT_ID")
    return qq(str(value))


def preview(source: Path, *, namespace: str, instance: str):
    opaque(namespace)
    opaque(instance)
    source = Path(source).resolve(strict=True)
    raw = tomllib.loads(source.read_text(encoding="utf-8-sig"))
    errors, warnings, rows = [], [], []
    allowed = {"plugin", "non_owner", "owner_auth", "user", "users"}
    unknown = [k for k in raw if k not in allowed and not re.fullmatch(r"user[1-9][0-9]*", k)]
    if unknown:
        errors.append({"code": "UNKNOWN_SECTIONS", "sections": unknown})
    plugin = raw.get("plugin", {})
    owner = raw.get("owner_auth", {})
    if type(plugin) is not dict or type(owner) is not dict:
        raise Denied("INVALID_LEGACY_STRUCTURE")
    count = plugin.get("user_count", owner.get("User"))
    if count is not None and (type(count) is not int or count < 0):
        errors.append({"code": "INVALID_USER_COUNT"})
        count = None
    families = []
    slots = sorted((k for k in raw if re.fullmatch(r"user[1-9][0-9]*", k)), key=lambda k: int(k[4:]))
    if slots:
        families.append("slots")
        rows.extend((k, raw[k], count is not None and int(k[4:]) > count) for k in slots)
    for location, container in (("owner_auth.users", owner.get("users")), ("user", raw.get("user")),
                                ("users.entries", raw.get("users", {}).get("entries") if type(raw.get("users", {})) is dict else None)):
        if container is not None:
            families.append(location)
            entries = [container] if type(container) is dict else container
            if type(entries) is not list:
                errors.append({"code": "INVALID_LEGACY_STRUCTURE", "location": location})
                continue
            rows.extend((f"{location}[{i}]", entry, count is not None and i >= count) for i, entry in enumerate(entries))
    if len(families) > 1:
        errors.append({"code": "MIXED_LEGACY_FORMATS", "formats": families})
    global_enabled = plugin.get("enabled", owner.get("enable_auth", True))
    if type(global_enabled) is not bool:
        errors.append({"code": "INVALID_ENABLED"})
    entries = []
    overlays = {}
    for location, row, excess in rows:
        if type(row) is not dict:
            errors.append({"code": "INVALID_ENTRY", "location": location})
            continue
        ids = [row[k] for k in ("qq", "owner_qq", "user_qq") if row.get(k) not in (None, "")]
        if not ids:
            warnings.append({"code": "EMPTY_ACCOUNT_INACTIVE", "location": location})
            continue
        try:
            normalized = {legacy_id(value) for value in ids}
            require(len(normalized) == 1, "ACCOUNT_FIELD_CONFLICT")
            account = next(iter(normalized))
            group = legacy_id(row.get("group_id"), empty=True)
            enabled = row.get("enabled", True)
            require(type(enabled) is bool, "INVALID_ENABLED")
            entry = {"location": location, "account_id": account, "group_id": group, "enabled": enabled,
                     "active": enabled and global_enabled is True and not excess,
                     "inactive_reason": "over_user_count" if excess else "disabled" if not enabled or global_enabled is not True else None,
                     "nickname": row.get("nickname", row.get("owner_nickname", "")), "original": row,
                     "template_state": "inactive"}
            overlay_key = (account, group)
            comparable = {k: v for k, v in entry.items() if k not in ("location", "original")}
            if overlay_key in overlays and overlays[overlay_key] != comparable:
                errors.append({"code": "OVERLAY_CONFLICT", "location": location})
            overlays[overlay_key] = comparable
            entries.append(entry)
        except Denied as error:
            errors.append({"code": error.code, "location": location})
    return {"source": str(source), "source_sha256": sha(source), "namespace": namespace, "instance": instance,
            "old_plugin_id": OLD_PLUGIN_ID, "new_plugin_id": PLUGIN_ID, "formats": families,
            "errors": errors, "warnings": warnings, "entries": entries, "raw": raw,
            "subjects": len({e["account_id"] for e in entries}), "privileges_created": 0, "relations_created": 0}


def public_report(plan, target):
    return {k: v for k, v in plan.items() if k not in ("entries", "raw")} | {
        "target": str(Path(target).absolute()), "entries": [{k: v for k, v in e.items() if k not in ("original", "account_id", "nickname")}
            | {"account_ref": digest(e["account_id"])[:12]} for e in plan["entries"]]}


def apply(plan, target: Path, *, old_data_root: Path | None = None, fault=None):
    """Offline staging only. No source overwrite, activation or Host startup."""
    require(not plan["errors"], "MIGRATION_REVIEW_REQUIRED")
    target = Path(target).absolute()
    require(target == target.resolve(), "REDIRECTED_TARGET")
    source = Path(plan["source"])
    require(target != source and target not in source.parents and sha(source) == plan["source_sha256"], "SOURCE_CHANGED")
    migration_id = digest([plan["source_sha256"], plan["namespace"], plan["instance"], str(old_data_root)])[:32]
    if target.exists():
        manifest_path = target/"migration.json"
        require(manifest_path.is_file(), "TARGET_EXISTS")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest.get("migration_id") == migration_id and manifest.get("state") in ("prepared", "activated"), "TARGET_EXISTS")
        if manifest["state"] == "prepared":
            require(all(sha(target/path) == expected for path, expected in manifest["files"].items()), "TARGET_CHANGED")
        return manifest
    target.mkdir(parents=True, exist_ok=False)
    initial = {"state": "preparing", "migration_id": migration_id, "plugin_id": PLUGIN_ID}
    write_json(target/"migration.json", initial)
    if fault:
        fault("created")
    backup = target/"backup"
    backup.mkdir()
    shutil.copyfile(source, backup/"config.toml")
    require(sha(backup/"config.toml") == plan["source_sha256"], "SOURCE_CHANGED")
    if old_data_root is not None:
        root = Path(old_data_root).resolve(strict=True)
        require(root.is_dir() and root != target and root not in target.parents and target not in root.parents, "OVERLAPPING_PATHS")
        for path in root.rglob("*"):
            require(not path.is_symlink() and not path.is_junction(), "REDIRECTED_SOURCE")
            if path.is_file():
                dest = backup/"old-data"/path.relative_to(root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
                require(sha(path) == sha(dest), "SOURCE_CHANGED")
    data = target/"data"
    data.mkdir()
    db = Database(data/"identity.db", create=True)
    accounts = {}
    try:
        identity = IdentityService(db)
        for entry in plan["entries"]:
            account = AccountKey("qq", plan["namespace"], entry["account_id"])
            if account.key not in accounts:
                accounts[account.key] = identity.bind_operator(account, key="migration:"+digest(account.key))
            with db.transaction():
                db.put("legacy_overlay", entry["location"], entry | {"subject_ref": accounts[account.key]["subject_id"]})
        # Disabled/inactive accounts remain archived, not authenticated.
        active = {AccountKey("qq", plan["namespace"], e["account_id"]).key for e in plan["entries"] if e["active"]}
        with db.transaction():
            for account in accounts:
                if account not in active:
                    db.conn.execute("UPDATE bindings SET status='inactive' WHERE account=?", (account,))
            db.conn.execute("INSERT INTO metadata VALUES('migration_id',?)", (migration_id,))
            db.conn.execute("INSERT INTO metadata VALUES('migration_state','prepared')")
            db.put("legacy_archive", "original", {"data": plan["raw"], "template_state": "inactive"})
    finally:
        db.close()
    config = {"plugin": {"enabled": False, "config_version": "3", "acknowledgement": "", "instance_id": plan["instance"],
                         "writer_lock": "", "migration_id": migration_id},
              "identity": {"adapter_namespace": plan["namespace"], "route_scope": "", "accounts": []}}
    # Group-only legacy identity overlays must not become instance-wide binding
    # authority. Bindings identify accounts; the original group preference lives
    # in the inactive display archive and creates no capabilities.
    for account_id in sorted({e["account_id"] for e in plan["entries"]}):
        config["identity"]["accounts"].append({"platform": "qq", "adapter_namespace": plan["namespace"], "account_id": account_id,
            "enabled": any(e["active"] for e in plan["entries"] if e["account_id"] == account_id)})
    import tomli_w
    (target/"config.toml").write_text(tomli_w.dumps(config), encoding="utf-8")
    write_json(target/"report.json", public_report(plan, target))
    write_json(data/"activation.json", initial | {"state": "prepared"})
    if fault:
        fault("prepared_files")
    files = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob("*") if p.is_file() and p.name != "migration.json"}
    manifest = initial | {"state": "prepared", "source_sha256": plan["source_sha256"], "files": files}
    atomic_json(target/"migration.json", manifest)
    return manifest


def activate(target, *, writer_lock: Path, route_scope: str, bootstrap_config: Path | None = None, fault=None):
    """Explicit offline local review: finalize paired config/DB; never start Host."""
    from ..host.config import MaiIdentityConfig
    target = Path(target).resolve(strict=True)
    manifest = json.loads((target/"migration.json").read_text(encoding="utf-8"))
    require(manifest["state"] == "prepared", "MIGRATION_INCOMPLETE")
    require(all(sha(target/path) == expected for path, expected in manifest["files"].items()), "TARGET_CHANGED")
    require(Path(writer_lock).is_absolute(), "INVALID_LOCK")
    lease = WriterLease(Path(writer_lock))
    lease.acquire()
    try:
        config = tomllib.loads((target/"config.toml").read_text(encoding="utf-8"))
        config["identity"]["route_scope"] = opaque(route_scope)
        bootstrap_hash = None
        if bootstrap_config is not None:
            from ..host.config import AccountEntry
            bootstrap_config = Path(bootstrap_config)
            require(bootstrap_config.is_absolute() and bootstrap_config.is_file(), "INVALID_BOOTSTRAP")
            bootstrap = tomllib.loads(bootstrap_config.read_text(encoding="utf-8"))
            require(set(bootstrap) <= {"identity", "roles"}, "INVALID_BOOTSTRAP")
            identities = bootstrap.get("identity", {})
            require(type(identities) is dict and set(identities) <= {"accounts"}, "INVALID_BOOTSTRAP")
            current = {AccountKey(e["platform"], e["adapter_namespace"], e["account_id"]).key: e for e in config["identity"]["accounts"]}
            for raw in identities.get("accounts", []):
                entry = AccountEntry.model_validate(raw).model_dump()
                account = AccountKey(entry["platform"], entry["adapter_namespace"], entry["account_id"])
                require(account.key not in current or current[account.key] == entry, "BOOTSTRAP_ACCOUNT_CONFLICT")
                current[account.key] = entry
            config["identity"]["accounts"] = list(current.values())
            if "roles" in bootstrap:
                config["roles"] = bootstrap["roles"]
            bootstrap_hash = sha(bootstrap_config)
        config["plugin"].update(enabled=True, acknowledgement="local-operator-reviewed", writer_lock=str(writer_lock))
        validated = MaiIdentityConfig.model_validate(config).model_dump()
        # Write a blocking marker first: a crash at any point refuses startup.
        marker = {"state": "activating", "plugin_id": PLUGIN_ID, "migration_id": manifest["migration_id"], "bootstrap_sha256": bootstrap_hash}
        atomic_json(target/"data/activation.json", marker)
        if fault:
            fault("activating_marker")
        import tomli_w
        temp = target/"config.activating.toml"
        with temp.open("x", encoding="utf-8") as stream:
            stream.write(tomli_w.dumps(validated))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target/"config.toml")
        if fault:
            fault("config_written")
        db = Database(target/"data/identity.db")
        try:
            with db.transaction():
                db.conn.execute("UPDATE metadata SET value='activated' WHERE key='migration_state'")
                if bootstrap_hash is not None:
                    db.audit("activation.bootstrap_config", manifest["migration_id"], {"source_sha256": bootstrap_hash})
        finally:
            db.close()
        if fault:
            fault("db_activated")
        atomic_json(target/"data/activation.json", marker | {"state": "activated", "config_hash": digest(validated)})
        atomic_json(target/"migration.json", manifest | {"state": "activated"})
        return {"state": "activated", "migration_id": manifest["migration_id"]}
    finally:
        lease.release()


def rollback_snapshot(target, destination):
    """Restore only the old snapshot into a new directory; retain new DB/audit."""
    target, destination = Path(target).resolve(strict=True), Path(destination).absolute()
    require(not destination.exists() and destination == destination.resolve(), "TARGET_EXISTS")
    require(target != destination and target not in destination.parents and destination not in target.parents, "OVERLAPPING_PATHS")
    manifest = json.loads((target/"migration.json").read_text(encoding="utf-8"))
    require(sha(target/"backup/config.toml") == manifest["source_sha256"], "BACKUP_CHANGED")
    expected = {name: value for name, value in manifest["files"].items() if name.startswith("backup/")}
    actual = {p.relative_to(target).as_posix() for p in (target/"backup").rglob("*") if p.is_file()}
    require(set(expected) == actual, "BACKUP_CHANGED")
    for name, value in expected.items():
        path = target/name
        require(not path.is_symlink() and not path.is_junction() and sha(path) == value, "BACKUP_CHANGED")
    shutil.copytree(target/"backup", destination)
    return {"restored": str(destination), "new_data_preserved": True, "side_effects_replayed": False}
