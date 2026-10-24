from pathlib import Path
import os
os.environ.setdefault('MAIBOT_HOST_VERSION','1.3.12')  # isolated Host fixture
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

from maiidentity.identity.service import IdentityService
from maiidentity.policy.service import PolicyService
from maiidentity.relations.service import Relations
from maiidentity.shared.core import AccountKey, Clock, Scope
from maiidentity.storage.database import Database


class FakeClock(Clock):
    value = 1000.0

    def now(self):
        return self.value

    def monotonic(self):
        return self.value


@pytest.fixture
def domain(tmp_path):
    clock = FakeClock()
    db = Database(tmp_path/"identity.db", create=True, clock=clock)
    identity = IdentityService(db)
    policy = PolicyService(identity)
    accounts = [AccountKey("qq", "adapter", str(i)) for i in (10001, 10002, 10003)]
    subjects = [identity.bind_operator(a, key=f"seed:{i}")["subject_id"] for i, a in enumerate(accounts)]
    yield db, identity, policy, Relations(policy), accounts, subjects, clock
    db.close()


def scope(stream="stream-A", resource="default", kind="stream", subject=None):
    return Scope(kind, "instance", "default", "qq", "adapter", "context", resource,
                 stream if kind != "instance" else None, subject)
