import json
import sys
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wsf.analysis.coupling import evaluate_window_coupling, WindowCouplingResult

SCENARIOS = ["ukraine2022", "rus2021apr", "deu2018quiet", "usachn2018trade"]

def load_scenario_features(project_root: Path, scenario_name: str) -> list[dict]:
    p = project_root / "scenarios" / scenario_name
    status = json.loads((p / "status.json").read_text(encoding="utf-8"))
    meas_id = status.get("active_measurement_id")
    if not meas_id:
        raise ValueError(f"Scenario {scenario_name} has no active measurement")
    features_file = p / "measurement" / meas_id / "features.jsonl"
    return [json.loads(line) for line in features_file.read_text(encoding="utf-8").splitlines() if line.strip()]

def main():
    root = Path(__file__).parent.parent
    all_results: dict[str, dict[str, WindowCouplingResult]] = {}
    
    for s in SCENARIOS:
        feats = load_scenario_features(root, s)
        windows = sorted({r["window_id"] for r in feats})
        all_results[s] = {}
        for w in windows:
            res = evaluate_window_coupling(s, w, feats, threshold_z=1.5, persistence_days=3, run_permutation=True, n_perm=2000)
            all_results[s][w] = res
            
    # Print formatted output
    print("=" * 110)
    print("STRATEGIC COUPLING & DYNAMIC CUEING RE-EVALUATION (OPTION 1 RESULTS)")
    print("=" * 110)
    print(f"{'Scenario':<16} | {'Period':<22} | {'K>=3 Ep (Warning)':<18} | {'K>=2 Ep (Cue)':<15} | {'Tasking Orders':<15} | {'Mean/Max Energy':<15}")
    print("-" * 110)
    
    for s in SCENARIOS:
        for w in ["incident", "same-period-prior-year"]:
            if w not in all_results[s]: continue
            r = all_results[s][w]
            k3_str = f"{len(r.episodes_k3)} ep ({r.days_ge3_domains_z15}d, p={r.permutation.get('k3_strategic', {}).get('p_episodes', 1.0):.3f})"
            k2_str = f"{len(r.episodes_k2)} ep ({r.days_ge2_domains_z15}d)"
            task_str = f"{r.tasking_order_days} days"
            energy_str = f"{r.mean_energy:.2f} / {r.max_energy:.2f}"
            print(f"{s:<16} | {w:<22} | {k3_str:<18} | {k2_str:<15} | {task_str:<15} | {energy_str:<15}")
            
    print("=" * 110)
    
    # Generate COUPLING_EVALUATION.md
    md_lines = [
        "# Strategic Coupling Re-Evaluation (Option 1)",
        "",
        "**Verdict:** not a salvage of the detector. This experiment still applies "
        "point-in-time marginal thresholds (now $z \\ge 1.5$ instead of $2.5$) and "
        "counts domains. That is failure mode 1 in [`IDEAS.md`](IDEAS.md), not "
        "Blueprint B. Both mobilisation windows produce $K_{\\mathrm{dom}} \\ge 3$ "
        "warning episodes (Ukraine produces two, rus2021apr produces one), and the "
        "hard negatives do not, but permutation $p_{\\mathrm{episodes}}$ is not small (~0.43). "
        "The actual Phase 1 instrument (rolling $\\lambda_{\\max}$) is in [`EWS_EVALUATION.md`](EWS_EVALUATION.md).",
        "",
        "---",
        "",
        "## 1. Executive Comparison Table",
        "",
        "| Scenario | Period | Role | Strategic Warning ($K_{\\text{dom}} \\ge 3$) | Soft Cue ($K_{\\text{dom}} \\ge 2$) | Sensor Tasking Days | Permutation ($p_{\\text{episodes}}$) | Max Domain Energy |",
        "|---|---|---|---|---|---|---|---|",
    ]
    
    for s in SCENARIOS:
        for w in ["incident", "same-period-prior-year"]:
            if w not in all_results[s]: continue
            r = all_results[s][w]
            role = "Positive Showcase" if s == "ukraine2022" and w == "incident" else (
                "Reversed Mobilization" if s == "rus2021apr" and w == "incident" else (
                    "Hard Negative (High Talk)" if s == "usachn2018trade" and w == "incident" else (
                        "Quiet Baseline" if s == "deu2018quiet" and w == "incident" else "Matched Control"
                    )
                )
            )
            k3_disp = f"**{len(r.episodes_k3)} ({r.days_ge3_domains_z15}d)**" if r.episodes_k3 else f"0 ({r.days_ge3_domains_z15}d)"
            k2_disp = f"{len(r.episodes_k2)} ({r.days_ge2_domains_z15}d)" if r.episodes_k2 else f"0 ({r.days_ge2_domains_z15}d)"
            task_disp = f"**{r.tasking_order_days}d**" if r.tasking_order_days > 0 else "0d"
            p_val = r.permutation.get("k3_strategic", {}).get("p_episodes", 1.0)
            p_disp = f"{p_val:.4f}" if r.episodes_k3 else "1.0000"
            md_lines.append(f"| `{s}` | `{w}` | {role} | {k3_disp} | {k2_disp} | {task_disp} | {p_disp} | {r.max_energy:.2f} |")

    ukr_inc = all_results["ukraine2022"]["incident"]
    rus_inc = all_results["rus2021apr"]["incident"]
    ukr_p = ukr_inc.permutation.get("k3_strategic", {}).get("p_episodes", 1.0)
    rus_p = rus_inc.permutation.get("k3_strategic", {}).get("p_episodes", 1.0)

    md_lines.extend([
        "",
        "---",
        "",
        "## 2. What the lowered-threshold coincidence detector actually shows",
        "",
        "### 2.1 Specificity without statistical rarity",
        f"- Ukraine produces {len(ukr_inc.episodes_k3)} $K_{{\\mathrm{{dom}}}} \\ge 3$ episodes "
        f"({ukr_inc.days_ge3_domains_z15} days total) at $z \\ge 1.5$ with 3-day persistence; "
        f"rus2021apr produces {len(rus_inc.episodes_k3)} episode ({rus_inc.days_ge3_domains_z15} days total). "
        "Hard negatives and prior-year controls do not produce a 3-day $K_{\\mathrm{dom}} \\ge 3$ episode.",
        f"- That pattern is **not** statistically rare under independent circular shifts of the "
        f"same z-calendars: Ukraine $p_{{\\mathrm{{episodes}}}} \\approx {ukr_p:.4f}$; "
        f"rus2021apr $p_{{\\mathrm{{episodes}}}} \\approx {rus_p:.4f}$. Lowering $\\tau$ from "
        "2.5 to 1.5 makes three-domain days common under unconstrained random shifts once series are noisy.",
        "- `usachn2018trade` isolates the 9/11 Wikipedia spike as a single-domain "
        "event at $K_{\\mathrm{dom}} \\ge 3$, which is the useful property of "
        "multi-domain counting. It produces a 4-day $K_{\\mathrm{dom}} \\ge 2$ soft cue.",
        "",
        "### 2.2 Tasking orders are a derived label",
        "Tasking orders are emitted on days when $K_{\\mathrm{dom}} \\ge 2$ and physical "
        "sensors (VIIRS/SAR) are in state unknown (cloud-cover or missing overpass). "
        "The count of tasking days is an operational triage rule, not independent "
        "evidence of unexpected coupling.",
        "",
        "### 2.3 Bidirectional RIPEstat",
        "Taking absolute z for `net.ripe_prefixes` includes the February prefix "
        "collapse that FINDINGS.md already flagged as a likely coverage hole. "
        "Do not treat that as a recovered digital-infrastructure vote.",
        "",
        "---",
        "",
        "## 3. Detailed Episode Log",
        "",
    ])
    
    for s in SCENARIOS:
        md_lines.append(f"### Scenario `{s}`")
        for w in ["incident", "same-period-prior-year"]:
            r = all_results[s][w]
            md_lines.append(f"#### Period `{w}`")
            if not r.episodes_k3 and not r.episodes_k2:
                md_lines.append("- *No coupling episodes observed.*")
            else:
                for ep in r.episodes_k3:
                    dom_str = ", ".join(ep.contributing_domains)
                    ser_str = ", ".join(ep.contributing_series)
                    md_lines.append(f"- **[STRATEGIC COUPLING WARNING]** `{ep.start_date}` to `{ep.end_date}` ({ep.duration_days} days)")
                    md_lines.append(f"  - Contributing Causal Domains: `{dom_str}`")
                    md_lines.append(f"  - Contributing Series: `{ser_str}`")
                    md_lines.append(f"  - Mean Energy: {ep.mean_energy:.2f} $\\sigma$, Peak Energy: {ep.max_energy:.2f} $\\sigma$")
                    md_lines.append(f"  - Sensor Tasking Orders Emitted: **{ep.tasking_order_days} / {ep.duration_days} days**")
                for ep in r.episodes_k2:
                    if not any(ep.start_date == k3_ep.start_date for k3_ep in r.episodes_k3):
                        dom_str = ", ".join(ep.contributing_domains)
                        md_lines.append(f"- **[SOFT COUPLING CUE]** `{ep.start_date}` to `{ep.end_date}` ({ep.duration_days} days)")
                        md_lines.append(f"  - Contributing Domains: `{dom_str}`")
                        md_lines.append(f"  - Sensor Tasking Orders: {ep.tasking_order_days} days")
            md_lines.append("")
            
    md_lines.extend([
        "---",
        "",
        "## 4. Conclusion",
        "",
        "Lowering the coincidence threshold does not measure statistical dependence "
        "and does not survive permutation. The Phase 1 question in IDEAS.md is "
        "whether rolling $\\lambda_{\\max}$ separates these four cases; that result "
        "is in [`EWS_EVALUATION.md`](EWS_EVALUATION.md). Blueprint A (non-optical "
        "costly series) and Blueprint C (frontier buffers) remain the remaining "
        "salvage routes if dependence on the current basket is not enough.",
    ])
    
    out_md = root / "COUPLING_EVALUATION.md"
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nWrote detailed report to {out_md}")

if __name__ == "__main__":
    main()
