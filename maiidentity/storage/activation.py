from pathlib import Path
import json

from .. import PLUGIN_ID
from ..shared.core import digest, require


def validate_activation(data_root: Path, config: dict):
    migration_id = config["plugin"]["migration_id"]
    marker_path = data_root / "activation.json"
    if not migration_id:
        require(not marker_path.exists(), "MIGRATION_MISMATCH")
        if (data_root / "identity.db").exists():
            import sqlite3
            connection = sqlite3.connect(f"file:{(data_root/'identity.db').as_posix()}?mode=ro", uri=True)
            try:
                row = connection.execute("SELECT value FROM metadata WHERE key='migration_id'").fetchone()
                require(row is None, "MIGRATION_MISMATCH")
            finally:
                connection.close()
        return
    require(marker_path.is_file() and (data_root/"identity.db").is_file(), "MIGRATION_INCOMPLETE")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    require(marker.get("state") == "activated" and marker.get("plugin_id") == PLUGIN_ID
            and marker.get("migration_id") == migration_id and marker.get("config_hash") == digest(config), "MIGRATION_MISMATCH")
    import sqlite3
    connection = sqlite3.connect(f"file:{(data_root/'identity.db').as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute("SELECT value FROM metadata WHERE key='migration_id'").fetchone()
        require(row is not None and row[0] == migration_id, "MIGRATION_MISMATCH")
        state = connection.execute("SELECT value FROM metadata WHERE key='migration_state'").fetchone()
        require(state is not None and state[0] == "activated", "MIGRATION_INCOMPLETE")
    finally:
        connection.close()
