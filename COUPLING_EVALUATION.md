# Strategic Coupling Re-Evaluation (Option 1)

**Verdict:** not a salvage of the detector. This experiment still applies point-in-time marginal thresholds (now $z \ge 1.5$ instead of $2.5$) and counts domains. That is failure mode 1 in [`IDEAS.md`](IDEAS.md), not Blueprint B. Both mobilisation windows produce $K_{\mathrm{dom}} \ge 3$ warning episodes (Ukraine produces two, rus2021apr produces one), and the hard negatives do not, but permutation $p_{\mathrm{episodes}}$ is not small (~0.43). The actual Phase 1 instrument (rolling $\lambda_{\max}$) is in [`EWS_EVALUATION.md`](EWS_EVALUATION.md).

---

## 1. Executive Comparison Table

| Scenario | Period | Role | Strategic Warning ($K_{\text{dom}} \ge 3$) | Soft Cue ($K_{\text{dom}} \ge 2$) | Sensor Tasking Days | Permutation ($p_{\text{episodes}}$) | Max Domain Energy |
|---|---|---|---|---|---|---|---|
| `ukraine2022` | `incident` | Positive Showcase | **2 (8d)** | 2 (15d) | **8d** | 0.4318 | 21.89 |
| `ukraine2022` | `same-period-prior-year` | Matched Control | 0 (0d) | 0 (3d) | **1d** | 1.0000 | 5.98 |
| `rus2021apr` | `incident` | Reversed Mobilization | **1 (5d)** | 2 (11d) | **3d** | 0.4388 | 10.15 |
| `rus2021apr` | `same-period-prior-year` | Matched Control | 0 (0d) | 0 (2d) | 0d | 1.0000 | 18.08 |
| `deu2018quiet` | `incident` | Quiet Baseline | 0 (1d) | 0 (2d) | 0d | 1.0000 | 11.38 |
| `deu2018quiet` | `same-period-prior-year` | Matched Control | 0 (1d) | 0 (1d) | 0d | 1.0000 | 6.64 |
| `usachn2018trade` | `incident` | Hard Negative (High Talk) | 0 (3d) | 1 (4d) | 0d | 1.0000 | 38.18 |
| `usachn2018trade` | `same-period-prior-year` | Matched Control | 0 (2d) | 0 (4d) | **2d** | 1.0000 | 19.53 |

---

## 2. What the lowered-threshold coincidence detector actually shows

### 2.1 Specificity without statistical rarity
- Ukraine produces 2 $K_{\mathrm{dom}} \ge 3$ episodes (8 days total) at $z \ge 1.5$ with 3-day persistence; rus2021apr produces 1 episode (5 days total). Hard negatives and prior-year controls do not produce a 3-day $K_{\mathrm{dom}} \ge 3$ episode.
- That pattern is **not** statistically rare under independent circular shifts of the same z-calendars: Ukraine $p_{\mathrm{episodes}} \approx 0.4318$; rus2021apr $p_{\mathrm{episodes}} \approx 0.4388$. Lowering $\tau$ from 2.5 to 1.5 makes three-domain days common under unconstrained random shifts once series are noisy.
- `usachn2018trade` isolates the 9/11 Wikipedia spike as a single-domain event at $K_{\mathrm{dom}} \ge 3$, which is the useful property of multi-domain counting. It produces a 4-day $K_{\mathrm{dom}} \ge 2$ soft cue.

### 2.2 Tasking orders are a derived label
Tasking orders are emitted on days when $K_{\mathrm{dom}} \ge 2$ and physical sensors (VIIRS/SAR) are in state unknown (cloud-cover or missing overpass). The count of tasking days is an operational triage rule, not independent evidence of unexpected coupling.

### 2.3 Bidirectional RIPEstat
Taking absolute z for `net.ripe_prefixes` includes the February prefix collapse that FINDINGS.md already flagged as a likely coverage hole. Do not treat that as a recovered digital-infrastructure vote.

---

## 3. Detailed Episode Log

### Scenario `ukraine2022`
#### Period `incident`
- **[STRATEGIC COUPLING WARNING]** `2022-02-10` to `2022-02-12` (3 days)
  - Contributing Causal Domains: `digital_infrastructure, domestic_financial_conditions, information, public_attention`
  - Contributing Series: `attn.wiki_pageviews, market.cbr_funding_spread, net.ripe_prefixes, talk.gdelt_cameo`
  - Mean Energy: 10.38 $\sigma$, Peak Energy: 13.13 $\sigma$
  - Sensor Tasking Orders Emitted: **1 / 3 days**
- **[STRATEGIC COUPLING WARNING]** `2022-02-21` to `2022-02-23` (3 days)
  - Contributing Causal Domains: `domestic_financial_conditions, information, market, public_attention, spatial_restriction`
  - Contributing Series: `attn.wiki_pageviews, dyad.moex_usdrub, market.cbr_funding_spread, nav.spatial_warnings, talk.gdelt_cameo, talk.icews_cameo`
  - Mean Energy: 16.52 $\sigma$, Peak Energy: 21.89 $\sigma$
  - Sensor Tasking Orders Emitted: **3 / 3 days**

#### Period `same-period-prior-year`
- *No coupling episodes observed.*

### Scenario `rus2021apr`
#### Period `incident`
- **[STRATEGIC COUPLING WARNING]** `2021-04-05` to `2021-04-08` (4 days)
  - Contributing Causal Domains: `information, market, public_attention, spatial_restriction`
  - Contributing Series: `attn.wiki_pageviews, dyad.moex_usdrub, nav.spatial_warnings, talk.gdelt_cameo, talk.icews_cameo`
  - Mean Energy: 9.13 $\sigma$, Peak Energy: 10.15 $\sigma$
  - Sensor Tasking Orders Emitted: **2 / 4 days**
- **[SOFT COUPLING CUE]** `2021-03-23` to `2021-03-25` (3 days)
  - Contributing Domains: `digital_infrastructure, information, market`
  - Sensor Tasking Orders: 0 days

#### Period `same-period-prior-year`
- *No coupling episodes observed.*

### Scenario `deu2018quiet`
#### Period `incident`
- *No coupling episodes observed.*

#### Period `same-period-prior-year`
- *No coupling episodes observed.*

### Scenario `usachn2018trade`
#### Period `incident`
- **[SOFT COUPLING CUE]** `2018-09-10` to `2018-09-13` (4 days)
  - Contributing Domains: `digital_infrastructure, public_attention, spatial_restriction`
  - Sensor Tasking Orders: 0 days

#### Period `same-period-prior-year`
- *No coupling episodes observed.*

---

## 4. Conclusion

Lowering the coincidence threshold does not measure statistical dependence and does not survive permutation. The Phase 1 question in IDEAS.md is whether rolling $\lambda_{\max}$ separates these four cases; that result is in [`EWS_EVALUATION.md`](EWS_EVALUATION.md). Blueprint A (non-optical costly series) and Blueprint C (frontier buffers) remain the remaining salvage routes if dependence on the current basket is not enough.