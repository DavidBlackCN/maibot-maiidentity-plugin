import tomllib

import pytest

from maiidentity.compatibility.migration import activate, apply, preview, rollback_snapshot
from maiidentity.host.config import MaiIdentityConfig
from maiidentity.shared.core import Denied
from maiidentity.storage.activation import validate_activation


@pytest.mark.parametrize("point", ["activating_marker", "config_written", "db_activated"])
def test_cross_file_activation_crash_refuses_to_guess(tmp_path, point):
    source = tmp_path/"source.toml"; source.write_text('[user1]\nqq="10001"', encoding="utf-8")
    target = tmp_path/"target"
    apply(preview(source, namespace="adapter", instance="instance"), target)
    def fault(actual):
        if actual == point:
            raise OSError("synthetic crash")
    with pytest.raises(OSError):
        activate(target, writer_lock=tmp_path/"writer.lock", route_scope="route", fault=fault)
    cfg = MaiIdentityConfig.model_validate(tomllib.loads((target/"config.toml").read_text(encoding="utf-8")))
    with pytest.raises(Denied):
        validate_activation(target/"data", cfg.model_dump())
    with pytest.raises(Denied):
        activate(target, writer_lock=tmp_path/"writer.lock", route_scope="route")


def test_backup_data_integrity_and_overlap(tmp_path):
    source = tmp_path/"source.toml"; source.write_text('[user1]\nqq="10001"', encoding="utf-8")
    old_data = tmp_path/"old-data"; old_data.mkdir(); (old_data/"retained.txt").write_text("snapshot")
    target = tmp_path/"target"
    apply(preview(source, namespace="adapter", instance="instance"), target, old_data_root=old_data)
    with pytest.raises(Denied, match="OVERLAPPING_PATHS"):
        rollback_snapshot(target, target/"backup/nested")
    (target/"backup/old-data/retained.txt").write_text("changed")
    with pytest.raises(Denied, match="BACKUP_CHANGED"):
        rollback_snapshot(target, tmp_path/"restored")
