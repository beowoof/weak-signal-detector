from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Causal Domain Map from indicator_register.yaml
CAUSAL_DOMAINS: dict[str, str] = {
    "tempo.viirs_aoi": "physical_activity",
    "tempo.s1_backscatter": "physical_activity",
    "tempo.firms_thermal": "physical_activity",
    "talk.gdelt_cameo": "information",
    "talk.icews_cameo": "information",
    "attn.wiki_pageviews": "public_attention",
    "attn.wiki_edits": "public_attention",
    "attn.osm_changesets": "public_attention",
    "dyad.fx": "market",
    "dyad.moex_usdrub": "market",
    "info.brent": "market",
    "net.ripe_prefixes": "digital_infrastructure",
    "official.ct_certs": "digital_infrastructure",
    "official.gazette": "bureaucratic",
    "official.gazette_cadence": "bureaucratic",
    "nav.spatial_warnings": "spatial_restriction",
    "air.notam_restrictions": "spatial_restriction",
    "market.cbr_funding_spread": "domestic_financial_conditions",
    "mobility.opensky": "mobility",
}

# Series where negative anomalies (e.g. routing prefix drops) indicate disruption
BIDIRECTIONAL_SERIES = {"net.ripe_prefixes"}

PHYSICAL_DOMAINS = {"physical_activity"}

# Overhead imaging / remote sensing sensors susceptible to atmospheric or orbit gaps
IMAGING_PHYSICAL_SERIES = {"tempo.viirs_aoi", "tempo.s1_backscatter"}


@dataclass(frozen=True)
class DailyCouplingState:
    date: str
    window_id: str
    domain_energies: dict[str, float]
    total_energy: float
    active_domains_z15: list[str]
    active_domains_z20: list[str]
    n_domains_z15: int
    n_domains_z20: int
    costly_status: str  # "normal", "flagged", "unknown"
    verdict: str
    sensor_tasking_order: bool
    series_z: dict[str, float]


@dataclass
class CouplingEpisode:
    window_id: str
    level: str  # "strategic_coupling_warning" (k>=3) or "soft_coupling_cue" (k>=2)
    start_date: str
    end_date: str
    duration_days: int
    contributing_domains: list[str]
    contributing_series: list[str]
    tasking_order_days: int
    mean_energy: float
    max_energy: float


@dataclass
class WindowCouplingResult:
    scenario_id: str
    window_id: str
    dates: list[str]
    daily_states: list[DailyCouplingState]
    episodes_k3: list[CouplingEpisode]
    episodes_k2: list[CouplingEpisode]
    max_energy: float
    mean_energy: float
    days_ge3_domains_z15: int
    days_ge2_domains_z15: int
    days_ge1_domain_z15: int
    tasking_order_days: int
    permutation: dict[str, Any] = field(default_factory=dict)


def evaluate_window_coupling(
    scenario_id: str,
    window_id: str,
    features_rows: list[dict[str, Any]],
    *,
    threshold_z: float = 1.5,
    persistence_days: int = 3,
    run_permutation: bool = True,
    n_perm: int = 2000,
    seed: int = 42,
) -> WindowCouplingResult:
    """Evaluates multi-domain coupling and dynamic cueing on a window of features."""
    # Filter features for this window
    window_feats = [
        r for r in features_rows if r.get("window_id") == window_id and (r.get("z") is not None or r.get("state") == "normal")
    ]
    if not window_feats:
        raise ValueError(f"No valid feature rows for scenario {scenario_id} window {window_id}")

    series_ids = sorted({r["series_id"] for r in window_feats})
    all_dates = sorted({r["event_day"] for r in window_feats})

    # Group by series and date
    z_lookup: dict[tuple[str, str], float] = {}
    for r in window_feats:
        s_id = r["series_id"]
        d = r["event_day"]
        z_raw = r.get("z")
        z_val = float(z_raw) if z_raw is not None else 0.0
        if s_id in BIDIRECTIONAL_SERIES and z_val < 0:
            z_lookup[(s_id, d)] = abs(z_val)
        else:
            z_lookup[(s_id, d)] = z_val

    # Costly status lookup from imaging sensors (VIIRS, SAR)
    costly_status_by_day: dict[str, str] = {}
    active_imaging = [s for s in series_ids if s in IMAGING_PHYSICAL_SERIES]
    for d in all_dates:
        day_imaging_states = [
            r.get("state", "unknown")
            for r in window_feats
            if r["event_day"] == d and r["series_id"] in active_imaging
        ]
        if any(st == "flagged" for st in day_imaging_states):
            costly_status_by_day[d] = "flagged"
        elif (
            all(st in {"unknown", "insufficient_baseline"} for st in day_imaging_states)
            or not day_imaging_states
        ):
            costly_status_by_day[d] = "unknown"
        else:
            costly_status_by_day[d] = "normal"

    # Exclude physical series from soft-coupling energy calculation
    soft_series = [s for s in series_ids if CAUSAL_DOMAINS.get(s) not in PHYSICAL_DOMAINS]
    domains_present = sorted({CAUSAL_DOMAINS[s] for s in soft_series if s in CAUSAL_DOMAINS})

    daily_states: list[DailyCouplingState] = []
    z_mat = np.zeros((len(all_dates), len(soft_series)))
    for j, s_id in enumerate(soft_series):
        for i, d in enumerate(all_dates):
            z_mat[i, j] = max(0.0, z_lookup.get((s_id, d), 0.0))

    for i, d in enumerate(all_dates):
        domain_energies: dict[str, float] = {}
        for dom in domains_present:
            dom_s_indices = [j for j, s in enumerate(soft_series) if CAUSAL_DOMAINS.get(s) == dom]
            domain_energies[dom] = float(np.max(z_mat[i, dom_s_indices])) if dom_s_indices else 0.0

        tot_energy = sum(domain_energies.values())
        act_15 = [dom for dom, e in domain_energies.items() if e >= 1.5]
        act_20 = [dom for dom, e in domain_energies.items() if e >= 2.0]
        c_status = costly_status_by_day.get(d, "unknown")

        if len(act_15) >= 3:
            verdict = "strategic_coupling_warning"
        elif len(act_15) >= 2:
            verdict = "soft_coupling_cue"
        elif len(act_15) == 1:
            verdict = "single_domain_spike"
        else:
            verdict = "quiet"

        # Tasking: elevated soft coupling while imaging sensors are blinded.
        tasking = (len(act_15) >= 2 and c_status == "unknown")

        s_z_map = {s: z_lookup.get((s, d), 0.0) for s in series_ids}
        daily_states.append(
            DailyCouplingState(
                date=d,
                window_id=window_id,
                domain_energies=domain_energies,
                total_energy=tot_energy,
                active_domains_z15=act_15,
                active_domains_z20=act_20,
                n_domains_z15=len(act_15),
                n_domains_z20=len(act_20),
                costly_status=c_status,
                verdict=verdict,
                sensor_tasking_order=tasking,
                series_z=s_z_map,
            )
        )

    # Extract episodes
    episodes_k3 = _extract_episodes(
        daily_states,
        min_domains=3,
        min_len=persistence_days,
        level="strategic_coupling_warning",
    )
    episodes_k2 = _extract_episodes(
        daily_states,
        min_domains=2,
        min_len=persistence_days,
        level="soft_coupling_cue",
    )

    # Compute summary stats
    tot_energies = [st.total_energy for st in daily_states]
    max_e = float(max(tot_energies)) if tot_energies else 0.0
    mean_e = float(np.mean(tot_energies)) if tot_energies else 0.0
    d_ge3 = sum(1 for st in daily_states if st.n_domains_z15 >= 3)
    d_ge2 = sum(1 for st in daily_states if st.n_domains_z15 >= 2)
    d_ge1 = sum(1 for st in daily_states if st.n_domains_z15 >= 1)
    tasking_days = sum(1 for st in daily_states if st.sensor_tasking_order)

    perm_results: dict[str, Any] = {}
    if run_permutation and len(all_dates) >= 10:
        perm_results = _run_permutation_test(
            z_mat=z_mat,
            soft_series=soft_series,
            domains_present=domains_present,
            all_dates=all_dates,
            threshold_z=threshold_z,
            persistence_days=persistence_days,
            n_perm=n_perm,
            seed=seed,
            obs_episodes_k3=episodes_k3,
            obs_episodes_k2=episodes_k2,
        )

    return WindowCouplingResult(
        scenario_id=scenario_id,
        window_id=window_id,
        dates=all_dates,
        daily_states=daily_states,
        episodes_k3=episodes_k3,
        episodes_k2=episodes_k2,
        max_energy=max_e,
        mean_energy=mean_e,
        days_ge3_domains_z15=d_ge3,
        days_ge2_domains_z15=d_ge2,
        days_ge1_domain_z15=d_ge1,
        tasking_order_days=tasking_days,
        permutation=perm_results,
    )


def _extract_episodes(
    daily_states: list[DailyCouplingState],
    min_domains: int,
    min_len: int,
    level: str,
) -> list[CouplingEpisode]:
    episodes: list[CouplingEpisode] = []
    current_run: list[DailyCouplingState] = []

    for st in daily_states:
        if st.n_domains_z15 >= min_domains:
            current_run.append(st)
        else:
            if len(current_run) >= min_len:
                episodes.append(_make_episode(current_run, level))
            current_run = []
    if len(current_run) >= min_len:
        episodes.append(_make_episode(current_run, level))
    return episodes


def _make_episode(run: list[DailyCouplingState], level: str) -> CouplingEpisode:
    window_id = run[0].window_id
    start_d = run[0].date
    end_d = run[-1].date
    dur = len(run)
    all_doms = sorted({dom for st in run for dom in st.active_domains_z15})
    all_series = sorted({s for st in run for s, z in st.series_z.items() if z >= 1.5})
    tasking_cnt = sum(1 for st in run if st.sensor_tasking_order)
    energies = [st.total_energy for st in run]
    return CouplingEpisode(
        window_id=window_id,
        level=level,
        start_date=start_d,
        end_date=end_d,
        duration_days=dur,
        contributing_domains=all_doms,
        contributing_series=all_series,
        tasking_order_days=tasking_cnt,
        mean_energy=float(np.mean(energies)),
        max_energy=float(max(energies)),
    )


def _run_permutation_test(
    z_mat: np.ndarray,
    soft_series: list[str],
    domains_present: list[str],
    all_dates: list[str],
    threshold_z: float,
    persistence_days: int,
    n_perm: int,
    seed: int,
    obs_episodes_k3: list[CouplingEpisode],
    obs_episodes_k2: list[CouplingEpisode],
) -> dict[str, Any]:
    n_days, n_series = z_mat.shape
    rng = np.random.default_rng(seed)

    dom_indices = [
        [j for j, s in enumerate(soft_series) if CAUSAL_DOMAINS.get(s) == dom]
        for dom in domains_present
    ]

    null_k3_counts = []
    null_k3_max_runs = []
    null_k2_counts = []
    null_k2_max_runs = []

    obs_k3_count = len(obs_episodes_k3)
    obs_k3_max_run = max([ep.duration_days for ep in obs_episodes_k3], default=0)
    obs_k2_count = len(obs_episodes_k2)
    obs_k2_max_run = max([ep.duration_days for ep in obs_episodes_k2], default=0)

    for _ in range(n_perm):
        perm_mat = np.zeros_like(z_mat)
        for j in range(n_series):
            shift = rng.integers(0, n_days)
            perm_mat[:, j] = np.roll(z_mat[:, j], shift)

        perm_dom_energies = np.zeros((n_days, len(dom_indices)))
        for u_idx, s_idx_list in enumerate(dom_indices):
            perm_dom_energies[:, u_idx] = np.max(perm_mat[:, s_idx_list], axis=1)

        perm_act_15 = (perm_dom_energies >= threshold_z)
        k3_active = (np.sum(perm_act_15, axis=1) >= 3)
        k2_active = (np.sum(perm_act_15, axis=1) >= 2)

        k3_runs = _find_runs(k3_active, persistence_days)
        k2_runs = _find_runs(k2_active, persistence_days)

        null_k3_counts.append(len(k3_runs))
        null_k3_max_runs.append(max(k3_runs, default=0))
        null_k2_counts.append(len(k2_runs))
        null_k2_max_runs.append(max(k2_runs, default=0))

    p_k3_episodes = float(
        (np.sum(np.array(null_k3_counts) >= obs_k3_count) + 1) / (n_perm + 1)
    )
    p_k3_max_run = (
        float((np.sum(np.array(null_k3_max_runs) >= obs_k3_max_run) + 1) / (n_perm + 1))
        if obs_k3_max_run > 0
        else 1.0
    )
    p_k2_episodes = float(
        (np.sum(np.array(null_k2_counts) >= obs_k2_count) + 1) / (n_perm + 1)
    )
    p_k2_max_run = (
        float((np.sum(np.array(null_k2_max_runs) >= obs_k2_max_run) + 1) / (n_perm + 1))
        if obs_k2_max_run > 0
        else 1.0
    )

    return {
        "n_perm": n_perm,
        "k3_strategic": {
            "observed_episodes": obs_k3_count,
            "observed_max_run": obs_k3_max_run,
            "null_mean_episodes": float(np.mean(null_k3_counts)),
            "null_mean_max_run": float(np.mean(null_k3_max_runs)),
            "p_episodes": p_k3_episodes,
            "p_max_run": p_k3_max_run,
        },
        "k2_soft": {
            "observed_episodes": obs_k2_count,
            "observed_max_run": obs_k2_max_run,
            "null_mean_episodes": float(np.mean(null_k2_counts)),
            "null_mean_max_run": float(np.mean(null_k2_max_runs)),
            "p_episodes": p_k2_episodes,
            "p_max_run": p_k2_max_run,
        },
    }


def _find_runs(binary_arr: np.ndarray, min_len: int) -> list[int]:
    runs: list[int] = []
    cur = 0
    for val in binary_arr:
        if val:
            cur += 1
        else:
            if cur >= min_len:
                runs.append(cur)
            cur = 0
    if cur >= min_len:
        runs.append(cur)
    return runs
