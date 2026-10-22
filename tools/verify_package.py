from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.package import verify

if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))
