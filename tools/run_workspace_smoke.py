"""Native workspace + existing Host regression, in a new isolated instance.

Requires the Host dependencies, SDK, Playwright and an installed Chromium browser.
No external network, production configuration or real QQ/model service is used.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integration_tests.support import stage
from tools.package import fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-source", type=Path, required=True)
    parser.add_argument("--isolated-root", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    args = parser.parse_args()
    work = args.isolated_root.resolve()
    host = args.host_source.resolve()
    if work.exists() or not args.browser.is_file():
        parser.error("Provide a new isolated-root and an existing Chromium executable")
    version = tomllib.loads((host / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    candidate = fingerprint()
    work.mkdir(parents=True)
    stage(work)
    shutil.copyfile(host / "pyproject.toml", work / "pyproject.toml")
    safety = work / "safety"; safety.mkdir()
    (safety / "sitecustomize.py").write_text(
        "import sys\ndef audit(event,args):\n"
        " if event=='socket.connect':\n"
        "  a=args[1]\n"
        "  if not isinstance(a,tuple) or a[0] not in ('127.0.0.1','::1'): raise PermissionError('TEST_NETWORK_DENIED')\n"
        "sys.addaudithook(audit)\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS")}
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
        PYTHONPATH=os.pathsep.join((str(safety), str(ROOT), str(host))), MAIBOT_INSTANCE_DIR=str(work),
        MAIBOT_HOST_VERSION=version, TEMP=str(work), TMP=str(work), USERPROFILE=str(work),
        MAIIDENTITY_BROWSER=str(args.browser.resolve()))
    if os.name == "nt":
        env["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    with (work / "console.log").open("wb") as output:
        process = subprocess.Popen([sys.executable, "-m", "integration_tests.workspace_scenario"],
            cwd=work, env=env, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            code = process.wait(timeout=180)
        except BaseException:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            else:
                process.kill()
            process.wait()
            raise
    if code:
        print((work / "console.log").read_text(encoding="utf-8", errors="replace")[-9000:])
        raise SystemExit(code)
    assert candidate == fingerprint(), "source changed while testing"
    report = json.loads((work / "result.json").read_text(encoding="utf-8"))
    report.update(host=version, sdk=importlib.metadata.version("maibot-plugin-sdk"),
        dashboard=importlib.metadata.version("maibot-dashboard"), candidate_files=candidate,
        host_source_hashes={p.relative_to(host).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (host / "src").rglob("*.py")},
        real_model_requests=0, real_qq_sends=0)
    (work / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]), "report": str(work / "result.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
