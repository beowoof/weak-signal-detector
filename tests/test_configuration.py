from pathlib import Path

from wsf.register import validate_configuration

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_frozen_configuration_contracts_are_valid() -> None:
    result = validate_configuration(PROJECT_ROOT / "config")
    assert result["indicator_count"] == 9
    assert result["period_count"] == 5
    assert len(result["config_hashes"]) == 9
