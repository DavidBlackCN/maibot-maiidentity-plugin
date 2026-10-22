"""Exercise the actual CLI end-to-end using only bundled synthetic input."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    def command(*args):
        output = subprocess.run([sys.executable, str(ROOT/"tools/migrate_config.py"), *args], capture_output=True,
                                env=dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1"), timeout=15)
        assert output.returncode == 0, output.stderr.decode("utf-8", errors="replace")
        return json.loads(output.stdout)
    source = ROOT/"tests/fixtures/legacy-v21.toml"
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="maiidentity-migration-") as directory:
        work = Path(directory).resolve()
        target = work/"stage"
        base = ["--source", str(source), "--target", str(target), "--namespace", "synthetic-adapter", "--instance", "synthetic-instance"]
        preview = command("--dry-run", *base)
        assert not target.exists() and not preview["errors"]
        staged = command("--apply", *base, "--reviewed-source-sha256", preview["source_sha256"])
        assert command("--apply", *base, "--reviewed-source-sha256", preview["source_sha256"]) == staged
        assert command("--activate", "--target", str(target), "--route-scope", "default", "--writer-lock", str(work/"writer.lock"))["state"] == "activated"
        restored = work/"restored"
        assert command("--rollback-snapshot", "--target", str(target), "--restore-to", str(restored))["side_effects_replayed"] is False
        assert hashlib.sha256((restored/"config.toml").read_bytes()).hexdigest() == original
        assert (target/"data/identity.db").is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    report = {"passed": True, "source_sha256": original, "synthetic_only": True, "source_unchanged": True,
              "dry_run_no_write": True, "idempotent_apply": True, "paired_activation": True,
              "rollback_preserves_new_data": True, "command": "python tools/rehearse_migration.py"}
    target = ROOT/"evidence/migration-cli.json"; target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
