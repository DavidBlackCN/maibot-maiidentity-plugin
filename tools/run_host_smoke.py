"""Basic native Host runtime smoke in a NEW explicitly isolated directory."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integration_tests.support import HOST, environment, run_process, stage, verify_source
from tools.package import fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-root", type=Path, required=True)
    args = parser.parse_args()
    work = args.isolated_root.absolute()
    if work.exists() or not args.isolated_root.is_absolute() or work != work.resolve() or work == ROOT or work in ROOT.parents:
        parser.error("new absolute nonredirected isolated-root required")
    lock = verify_source()
    candidate = fingerprint()
    work.mkdir(parents=True)
    (work/"isolated-test.json").write_text(json.dumps({"production_data": False, "platform": False, "models": False}), encoding="utf-8")
    shutil.copyfile(HOST/"pyproject.toml", work/"pyproject.toml")
    stage(work)
    output = run_process([sys.executable, "-m", "integration_tests.host_scenario"], work=work)
    (work/"console.log").write_bytes(output.stdout+output.stderr)
    if output.returncode:
        print(output.stderr.decode("utf-8", errors="replace")[-6500:])
        raise SystemExit(output.returncode)
    report = json.loads((work/"result.json").read_text(encoding="utf-8"))
    report.update(host_commit=lock["host_commit"], host_version=lock["host_version"], sdk_version=lock["sdk_version"], host_files_verified=len(lock["host_files"]))
    assert candidate == fingerprint()
    report.update(candidate_files=candidate, python=sys.version, sdk_files=lock["sdk_files"], command="python tools/run_host_smoke.py --isolated-root <new-isolated-directory>")
    target = ROOT/"evidence/host.json"; target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("candidate_files", "sdk_files")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
