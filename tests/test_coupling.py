from __future__ import annotations

import pytest
from datetime import date
from wsf.analysis.coupling import evaluate_window_coupling, DailyCouplingState, CouplingEpisode

def test_evaluate_window_coupling_basic():
    # Synthetic feature rows
    # 5 days: days 1-2 quiet, days 3-5 multi-domain elevation (3 domains: attention, market, info)
    days = ["2022-02-01", "2022-02-02", "2022-02-03", "2022-02-04", "2022-02-05"]
    features = []
    for d in days:
        is_elev = d >= "2022-02-03"
        features.append({
            "window_id": "test_win",
            "series_id": "attn.wiki_pageviews",
            "event_day": d,
            "z": 3.0 if is_elev else 0.2,
            "state": "flagged" if is_elev else "normal",
        })
        features.append({
            "window_id": "test_win",
            "series_id": "dyad.moex_usdrub",
            "event_day": d,
            "z": 2.5 if is_elev else 0.1,
            "state": "flagged" if is_elev else "normal",
        })
        features.append({
            "window_id": "test_win",
            "series_id": "talk.gdelt_cameo",
            "event_day": d,
            "z": 2.8 if is_elev else -0.5,
            "state": "flagged" if is_elev else "normal",
        })
        features.append({
            "window_id": "test_win",
            "series_id": "tempo.viirs_aoi",
            "event_day": d,
            "z": None,
            "state": "unknown",
        })

    res = evaluate_window_coupling(
        "test_scenario",
        "test_win",
        features,
        threshold_z=1.5,
        persistence_days=3,
        run_permutation=False,
    )
    assert len(res.daily_states) == 5
    assert res.days_ge3_domains_z15 == 3
    assert len(res.episodes_k3) == 1
    assert res.episodes_k3[0].start_date == "2022-02-03"
    assert res.episodes_k3[0].end_date == "2022-02-05"
    assert res.episodes_k3[0].duration_days == 3
    assert res.tasking_order_days == 3

def test_single_domain_spike_no_strategic_warning():
    # Only 1 domain spikes to z=30 (e.g. 9/11 anniversary on Wikipedia)
    days = ["2018-09-10", "2018-09-11", "2018-09-12"]
    features = []
    for d in days:
        features.append({
            "window_id": "trade_win",
            "series_id": "attn.wiki_pageviews",
            "event_day": d,
            "z": 30.0 if d == "2018-09-11" else 0.5,
            "state": "flagged" if d == "2018-09-11" else "normal",
        })
        features.append({
            "window_id": "trade_win",
            "series_id": "talk.gdelt_cameo",
            "event_day": d,
            "z": 0.1,
            "state": "normal",
        })
        features.append({
            "window_id": "trade_win",
            "series_id": "dyad.fx",
            "event_day": d,
            "z": 0.0,
            "state": "normal",
        })

    res = evaluate_window_coupling(
        "usachn_test",
        "trade_win",
        features,
        threshold_z=1.5,
        persistence_days=3,
        run_permutation=False,
    )
    assert len(res.episodes_k3) == 0
    assert len(res.episodes_k2) == 0
    assert res.days_ge3_domains_z15 == 0
    assert res.tasking_order_days == 0
