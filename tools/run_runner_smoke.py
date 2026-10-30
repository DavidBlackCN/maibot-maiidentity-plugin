from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workspace_paths import EVIDENCE
from integration_tests.support import environment, run_process, stage, verify_source
from tools.package import fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-lock", type=Path, default=ROOT/"tests/fixtures/source-lock.json")
    args = parser.parse_args()
    lock = verify_source()
    candidate = fingerprint()
    assert args.source_lock.resolve() == (ROOT/"tests/fixtures/source-lock.json").resolve()
    with tempfile.TemporaryDirectory(prefix="maiidentity-runner-") as directory:
        work = Path(directory)
        stage(work)
        output = run_process([sys.executable, "-m", "integration_tests.runner_scenario"], work=work)
        if output.returncode:
            print(output.stdout.decode("utf-8", errors="replace")[-4000:]); print(output.stderr.decode("utf-8", errors="replace")[-6000:])
            raise SystemExit(output.returncode)
        report = json.loads((work/"result.json").read_text(encoding="utf-8"))
        report.update(host_commit=lock["host_commit"], host_files_verified=len(lock["host_files"]))
        assert candidate == fingerprint()
        report.update(candidate_files=candidate, python=sys.version, sdk_files=lock["sdk_files"], command="python tools/run_runner_smoke.py")
    target = EVIDENCE/'runner.json'; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("candidate_files", "sdk_files")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
