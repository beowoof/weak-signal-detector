import shutil
from pathlib import Path

import pytest

from wsf.run import ensure_manifest, new_run_id

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_run_id_has_requested_prefix() -> None:
    assert new_run_id("test").startswith("test-")


def test_manifest_refuses_changed_scientific_configuration(tmp_path: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "config", tmp_path / "config")
    _, first = ensure_manifest(tmp_path, "test-fixed")
    _, second = ensure_manifest(tmp_path, "test-fixed")
    assert first["protocol_hash"] == second["protocol_hash"]

    protocol = tmp_path / "config/protocol.yaml"
    protocol.write_text(protocol.read_text().replace("z_threshold: 2.5", "z_threshold: 3.0"))
    with pytest.raises(ValueError, match="scientific configuration changed"):
        ensure_manifest(tmp_path, "test-fixed")
