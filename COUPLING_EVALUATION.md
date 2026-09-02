# Strategic Coupling Re-Evaluation (Option 1)

**Verdict:** not a salvage of the detector. This experiment still applies point-in-time marginal thresholds (now $z \ge 1.5$ instead of $2.5$) and counts domains. That is failure mode 1 in [`IDEAS.md`](IDEAS.md), not Blueprint B. Both mobilisation windows produce a 3-day $K_{\mathrm{dom}} \ge 3$ episode, and the hard negatives do not, but permutation $p_{\mathrm{episodes}}$ is not small. The actual Phase 1 instrument (rolling $\lambda_{\max}$) is in [`EWS_EVALUATION.md`](EWS_EVALUATION.md).

---

## 1. Executive Comparison Table

| Scenario | Period | Role | Strategic Warning ($K_{\text{dom}} \ge 3$) | Soft Cue ($K_{\text{dom}} \ge 2$) | Sensor Tasking Days | Permutation ($p_{\text{episodes}}$) | Max Domain Energy |
|---|---|---|---|---|---|---|---|
| `ukraine2022` | `incident` | Positive Showcase | **1 (6d)** | 2 (15d) | **8d** | 0.8676 | 18.44 |
| `ukraine2022` | `same-period-prior-year` | Matched Control | 0 (0d) | 0 (0d) | 0d | 1.0000 | 5.09 |
| `rus2021apr` | `incident` | Reversed Mobilization | **1 (4d)** | 2 (11d) | **3d** | 0.4073 | 10.04 |
| `rus2021apr` | `same-period-prior-year` | Matched Control | 0 (0d) | 0 (0d) | 0d | 1.0000 | 17.18 |
| `deu2018quiet` | `incident` | Quiet Baseline | 0 (0d) | 0 (0d) | 0d | 1.0000 | 6.54 |
| `deu2018quiet` | `same-period-prior-year` | Matched Control | 0 (0d) | 0 (0d) | 0d | 1.0000 | 3.54 |
| `usachn2018trade` | `incident` | Hard Negative (High Talk) | 0 (0d) | 1 (4d) | 0d | 1.0000 | 35.47 |
| `usachn2018trade` | `same-period-prior-year` | Matched Control | 0 (0d) | 0 (0d) | **1d** | 1.0000 | 16.60 |

---

## 2. What the lowered-threshold coincidence detector actually shows

### 2.1 Specificity without rarity
- Both mobilisation windows produce one $K_{\mathrm{dom}} \ge 3$ episode at $z \ge 1.5$ with 3-day persistence. Hard negatives and prior-year controls do not produce a $K_{\mathrm{dom}} \ge 3$ episode.
- That pattern is **not** rare under independent circular shifts of the same z-calendars. Ukraine $p_{\mathrm{episodes}} \approx 0.88$; rus2021apr $p_{\mathrm{episodes}} \approx 0.43$. Lowering $\tau$ from 2.5 to 1.5 makes three-domain days common once any series is noisy.
- `usachn2018trade` still isolates the 9/11 Wikipedia spike as a single-domain event at $K_{\mathrm{dom}} \ge 3$, which is the one useful property of domain counting. It also produces a 4-day $K_{\mathrm{dom}} \ge 2$ soft cue.

### 2.2 Tasking orders are not a free lunch
Tasking is emitted when $K_{\mathrm{dom}} \ge 2$ and imaging (VIIRS/SAR) is unknown. FIRMS zeros on capital stamps must not be treated as a clear night; that was the postage-stamp leak. Even after restricting the gate to imaging series, the count of tasking days is a derived label, not evidence that coupling is unusual. Read the table, not a narrative that disagrees with it.

### 2.3 Bidirectional RIPEstat
Taking absolute z for `net.ripe_prefixes` includes the February prefix collapse that FINDINGS.md already flagged as a likely coverage hole. Do not treat that as a recovered digital-infrastructure vote.

---

## 3. Detailed Episode Log

### Scenario `ukraine2022`
#### Period `incident`
- **[STRATEGIC COUPLING WARNING]** `2022-02-21` to `2022-02-23` (3 days)
  - Contributing Causal Domains: `information, market, public_attention`
  - Contributing Series: `attn.wiki_pageviews, dyad.moex_usdrub, talk.gdelt_cameo, talk.icews_cameo`
  - Mean Energy: 14.41 $\sigma$, Peak Energy: 18.44 $\sigma$
  - Sensor Tasking Orders Emitted: **3 / 3 days**
- **[SOFT COUPLING CUE]** `2022-02-10` to `2022-02-18` (9 days)
  - Contributing Domains: `digital_infrastructure, information, public_attention`
  - Sensor Tasking Orders: 4 days

#### Period `same-period-prior-year`
- *No coupling episodes observed.*

### Scenario `rus2021apr`
#### Period `incident`
- **[STRATEGIC COUPLING WARNING]** `2021-04-06` to `2021-04-08` (3 days)
  - Contributing Causal Domains: `information, market, public_attention`
  - Contributing Series: `attn.wiki_pageviews, dyad.moex_usdrub, talk.gdelt_cameo, talk.icews_cameo`
  - Mean Energy: 9.00 $\sigma$, Peak Energy: 10.04 $\sigma$
  - Sensor Tasking Orders Emitted: **2 / 3 days**
- **[SOFT COUPLING CUE]** `2021-03-23` to `2021-03-25` (3 days)
  - Contributing Domains: `digital_infrastructure, information, market`
  - Sensor Tasking Orders: 0 days
- **[SOFT COUPLING CUE]** `2021-04-05` to `2021-04-08` (4 days)
  - Contributing Domains: `information, market, public_attention`
  - Sensor Tasking Orders: 2 days

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
  - Contributing Domains: `digital_infrastructure, public_attention`
  - Sensor Tasking Orders: 0 days

#### Period `same-period-prior-year`
- *No coupling episodes observed.*

---

## 4. Conclusion

Lowering the coincidence threshold does not measure statistical dependence and does not survive permutation. The Phase 1 question in IDEAS.md is whether rolling $\lambda_{\max}$ separates these four cases; that result is in [`EWS_EVALUATION.md`](EWS_EVALUATION.md). Blueprint A (non-optical costly series) and Blueprint C (frontier buffers) remain the remaining salvage routes if dependence on the current basket is not enough.