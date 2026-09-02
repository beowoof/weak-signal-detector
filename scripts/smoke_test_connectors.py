#!/usr/bin/env python3
"""Smoke test live working connectors (CBR, NAVAREA, Gazette Cadence)."""

from types import SimpleNamespace
from datetime import date
from wsf.connectors.base import PullRequest
from wsf.connectors.cbr import CbrConnector
from wsf.connectors.gazette_cadence import GazetteCadenceConnector
from wsf.connectors.http import UrllibTransport
from wsf.connectors.navarea import NavareaConnector


def smoke_test_cbr() -> None:
    print("Testing CbrConnector (Bank of Russia RUONIA spread)...")
    transport = UrllibTransport()
    connector = CbrConnector(transport)
    req = PullRequest(
        source="cbr",
        series_id="market.cbr_funding_spread",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 28),
        queries=SimpleNamespace(cameo_actor="RUS", facility_actor="RUS"),
    )
    res = connector.pull(req)
    non_zero = [obs for obs in res.observations if obs.value is not None and obs.value != 0.0]
    print(f"  Total days: {len(res.observations)}, non-zero spread days: {len(non_zero)}")
    for obs in res.observations[:5]:
        print(f"  {obs.event_time.date()}: spread {obs.value} bps")
    assert len(non_zero) > 10, f"Expected non-zero CBR spread values, got {len(non_zero)}"
    print("  ✓ CBR smoke test PASSED\n")


def smoke_test_navarea() -> None:
    print("Testing NavareaConnector (NGA NAVAREA broadcast warnings)...")
    transport = UrllibTransport()
    connector = NavareaConnector(transport)
    req = PullRequest(
        source="navarea",
        series_id="nav.spatial_warnings",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 28),
        queries=SimpleNamespace(cameo_actor="RUS", facility_actor="RUS"),
    )
    res = connector.pull(req)
    non_zero = [obs for obs in res.observations if obs.value is not None and obs.value > 0]
    print(f"  Total days: {len(res.observations)}, days with warnings: {len(non_zero)}")
    for obs in res.observations[:5]:
        print(f"  {obs.event_time.date()}: count {obs.value}")
    assert len(non_zero) > 10, f"Expected active NAVAREA warnings, got {len(non_zero)}"
    print("  ✓ NAVAREA smoke test PASSED\n")


def smoke_test_gazette_cadence() -> None:
    print("Testing GazetteCadenceConnector (Federal Register publication cadence)...")
    transport = UrllibTransport()
    connector = GazetteCadenceConnector(transport)
    req = PullRequest(
        source="gazette_cadence",
        series_id="official.gazette_cadence",
        scenario_id="usachn2018trade",
        window_id="incident",
        start=date(2018, 9, 1),
        end=date(2018, 9, 30),
        queries=SimpleNamespace(cameo_actor="USA", facility_actor="USA"),
    )
    res = connector.pull(req)
    non_zero = [obs for obs in res.observations if obs.value is not None and obs.value > 0]
    print(f"  Total days: {len(res.observations)}, days with publications: {len(non_zero)}")
    for obs in res.observations[:5]:
        print(f"  {obs.event_time.date()}: docs {obs.value}")
    assert len(non_zero) > 10, f"Expected active Federal Register publications, got {len(non_zero)}"
    print("  ✓ Gazette Cadence smoke test PASSED\n")


def main() -> None:
    smoke_test_cbr()
    smoke_test_navarea()
    smoke_test_gazette_cadence()
    print("ALL 3 CONNECTORS SMOKE TESTED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
