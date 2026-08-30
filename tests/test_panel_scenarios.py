from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from wsf.scenario import load_scenario, require_collection_ready

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PANEL = (
    "deu2018quiet",
    "usachn2018trade",
    "rus2021apr",
)


@pytest.mark.parametrize("scenario_id", PANEL)
def test_panel_scenarios_are_collection_ready(scenario_id: str) -> None:
    scenario = load_scenario(PROJECT_ROOT, scenario_id)
    require_collection_ready(scenario)
    assert scenario.purpose == "development_showcase"
    assert scenario.incident.lookback_days == 120
    assert scenario.controls[0].lookback_days == 120
    scored_days = (scenario.incident.end - scenario.incident.start).days + 1
    assert scored_days == 21
    assert scenario.sources["sar"].enabled is False
    assert scenario.sources["wiki_edits"].enabled is False
    assert scenario.sources["osm"].enabled is False
    assert scenario.sources["brent"].enabled is False


def test_2018_cases_do_not_use_noaa20_firms_or_moex() -> None:
    for scenario_id in ("deu2018quiet", "usachn2018trade"):
        scenario = load_scenario(PROJECT_ROOT, scenario_id)
        assert scenario.sources["firms"].enabled is False
        assert scenario.sources["moex"].enabled is False
        assert scenario.queries.fred_series is not None


def test_rus2021apr_keeps_the_ukraine_source_set_and_declared_target() -> None:
    scenario = load_scenario(PROJECT_ROOT, scenario_id="rus2021apr")
    assert scenario.actors.focal == "RUS"
    assert scenario.sources["firms"].enabled is True
    assert scenario.sources["moex"].enabled is True
    assert scenario.queries.fred_series is None
    assert scenario.incident.target_start == date(2021, 3, 25)
    assert scenario.incident.target_end == date(2021, 4, 8)
