"""Prepare the fixed public Host source only, without starting or modifying it."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import io
import json
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="optional offline public Host tar.gz")
    args = parser.parse_args()
    lock = json.loads((ROOT/"tests/fixtures/source-lock.json").read_text(encoding="utf-8"))
    if args.archive:
        data = args.archive.read_bytes()
    else:
        with urllib.request.urlopen("https://codeload.github.com/Mai-with-u/MaiBot/tar.gz/"+lock["host_commit"], timeout=30) as response:
            data = response.read(20_000_001)
    assert len(data) <= 20_000_000 and hashlib.sha256(data).hexdigest() == lock["host_archive_sha256"]
    host = ROOT/".integration/host"
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for entry in archive.getmembers():
            relative = PurePosixPath(*PurePosixPath(entry.name).parts[1:]).as_posix()
            if relative not in lock["host_files"]:
                continue
            assert entry.isfile() and not entry.issym() and not entry.islnk()
            assert ".." not in PurePosixPath(relative).parts and not PurePosixPath(relative).is_absolute()
            payload = archive.extractfile(entry).read()
            assert hashlib.sha256(payload).hexdigest() == lock["host_files"][relative]
            target = host/relative
            assert target.absolute() == target.resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == payload, "refusing changed Host source"
            else:
                target.write_bytes(payload)
            count += 1
    assert count == len(lock["host_files"])
    print("Host source verified:", count, lock["host_commit"])
