from pathlib import Path
import os
import subprocess
import sys
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.package import fingerprint

if __name__ == "__main__":
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    target = ROOT/"evidence"; target.mkdir(exist_ok=True)
    candidate = fingerprint()
    result = subprocess.call([sys.executable, "-m", "pytest", "-p", "pytest_asyncio.plugin", "tests", "-q",
                              "--junitxml="+str(target/"unit.xml"), *sys.argv[1:]], cwd=ROOT, env=env)
    if result == 0:
        suites = list(ET.parse(target/"unit.xml").getroot().iter("testsuite"))
        assert candidate == fingerprint()
        report = {"passed": True, "layer": "T0", "tests": sum(int(s.get("tests", 0)) for s in suites),
                  "failures": sum(int(s.get("failures", 0))+int(s.get("errors", 0)) for s in suites),
                  "skipped": sum(int(s.get("skipped", 0)) for s in suites), "python": sys.version,
                  "candidate_files": candidate, "command": "python tools/run_tests.py"}
        (target/"unit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SystemExit(result)
