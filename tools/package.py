"""Explicit distribution allowlist; no local config, tests or runtime data."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOP = ("plugin.py", "config.py", "__init__.py", "_manifest.json", "LICENSE", "README.md", "UPDATE_NOTES.md", "config.example.toml", "requirements-tools.txt")
DOCS = ("API.md", "CONTRACTS.md", "SOURCE_LAYOUT.md", "MIGRATION.md", "LIMITATIONS.md", "ROLLBACK.md", "SOURCES.md", "acceptance.json")
TOOLS = ("migrate_config.py",)


def files():
    paths = [ROOT/name for name in TOP]
    paths += [p for p in (ROOT/"maiidentity").rglob("*.py") if "__pycache__" not in p.parts]
    paths += [ROOT/"docs"/name for name in DOCS]
    paths += [ROOT/"tools"/name for name in TOOLS]
    return sorted(paths)


def fingerprint():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted([ROOT/"plugin.py", ROOT/"config.py", ROOT/"_manifest.json", *[p for p in (ROOT/"maiidentity").rglob("*.py") if "__pycache__" not in p.parts]])}


def verify_acceptance():
    report=json.loads((ROOT/"docs/acceptance.json").read_text(encoding="utf-8"))
    assert report.get("candidate_files")==fingerprint(), "stale acceptance: regenerate current gates before packaging"
    assert all(report.get(layer,{}).get("passed") is True for layer in ("T0","T1","T2","migration_cli")), "incomplete acceptance"
    validation={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for directory in ('tools','tests','integration_tests') for p in (ROOT/directory).rglob('*.py')}
    assert report.get('validation_files')==validation, 'stale validation tools/tests: regenerate acceptance'


def verify(path):
    verify_acceptance()
    expected = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files()}
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert set(archive.namelist()) == set(expected), "unexpected or missing package member"
        assert all(archive.read(name) == content for name, content in expected.items()), "package content differs from current source"
    return {"files": len(expected), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "internal_design_documents": 0, "runtime_data": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"dist/MaiIdentity-3.2.2.zip")
    args = parser.parse_args()
    verify_acceptance()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files():
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(json.dumps(verify(args.output), indent=2))
