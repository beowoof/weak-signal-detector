import json
from datetime import date
from pathlib import Path

from pydantic import TypeAdapter

from wsf.features.cutoff import as_of_value, select_expected_current
from wsf.types import Observation

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fixture_versions() -> list[Observation]:
    data = json.loads((PROJECT_ROOT / "data/fixtures/cutoff_versions.json").read_text())
    return TypeAdapter(list[Observation]).validate_python(data)


def test_future_revision_cannot_replace_visible_version() -> None:
    selected = as_of_value(fixture_versions(), date(2021, 1, 1))
    assert selected is not None
    assert selected.version_id == "visible-v1"
    assert selected.value == 10.0


def test_expected_current_does_not_fall_back_to_stale_observation() -> None:
    selected = select_expected_current(
        fixture_versions(),
        date(2021, 1, 2),
        expected_lag_days=0,
    )
    assert selected is None


def test_declared_lag_selects_exact_event_date() -> None:
    selected = select_expected_current(
        fixture_versions(),
        date(2021, 1, 2),
        expected_lag_days=1,
    )
    assert selected is not None
    assert selected.version_id == "future-v2"
