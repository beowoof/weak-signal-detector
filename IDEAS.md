# Strategic Coupling & Weak Signal Fusion: Blueprint for Salvaging the Intent

**Reviewed 2026-09-05.** Research proposals and historical motivation, not the implemented feature list. Current delivery status is in [ROADMAP](ROADMAP.md); evaluation results are in [COUPLING_EVALUATION](COUPLING_EVALUATION.md) and [EWS_EVALUATION](EWS_EVALUATION.md).

This document records the architectural, mathematical, and data-source blueprints for salvaging the core thesis of the **Weak Signal Detector** following the findings in [`FINDINGS.md`](FINDINGS.md).

---

## 1. Executive Summary & Core Shift

The PoC recorded co-movement in selected public indicators before 24 February 2022. The later evaluations do not establish a generally significant preparation detector: the domain-count permutation results are about 0.43, and the rolling-correlation results are mixed. News-event counts do not measure news tone. The proposals below remain hypotheses rather than validated findings.

The failure was not the phenomenon of **strategic coupling**; the failure was the **instrument and structural assumptions**:
1. It evaluated point-in-time marginal thresholds ($z \ge 2.5$) rather than measuring statistical dependence/phase-coupling directly.
2. It created an overhead physical sensor bottleneck (VIIRS/SAR), turning winter cloud cover into the sole determinant of alert status.
3. It searched for mobilization on postage-stamp capital bounding boxes rather than operational frontier corridors.
4. It tried to act as an autonomous binary tripwire rather than an asset-cueing and analyst-triage prioritization filter.

To salvage the project, we shift:
- **From Marginal $z$-Thresholds $\longrightarrow$ Dynamic Covariance / Early Warning Signals (EWS)** (measuring the collapse of independence across systems).
- **From Optical/SAR Imagery $\longrightarrow$ High-Friction Administrative & Market Commitments** (NOTAMs, gazette gap analysis, interbank liquidity hoarding).
- **From Capital Coordinates $\longrightarrow$ Frontier Corridor & Maritime Choke-Point Buffers**.
- **From Binary Alarm Tripwire $\longrightarrow$ Dynamic Sensor-Cueing & Analyst Triage Engine**.

---

## 2. The Four Structural Failure Modes in v1

| Failure Mode | How v1 Worked | Why it Choked |
|---|---|---|
| **1. Marginal Threshold Gating** | Required $k \ge 3$ individual series to independently cross $z \ge 2.5$. | In complex systems, strategic coupling manifests when multiple noisy channels move mildly ($z pprox 1.3 - 1.8$) in phase. Individual thresholding misses coherent weak shifts. |
| **2. Physical Overhead Gate Bottleneck** | Required $k_{\text{costly}} \ge 1$ (VIIRS, SAR, FIRMS) for a Red alert; absence promoted Amber. | Weather made costly unknown 48% of the time. Clear nights with massive soft chorus were vetoed as "cheap talk"; cloudy nights became Amber purely by ignorance. |
| **3. Capital Postage-Stamp Fallacy** | Bounded 3 tiny AOIs: Kremlin, Sheremetyevo Airport, MoD HQ. | Military mobilization and logistics staging take place in border regions, railheads, and dispersed forward bases (Yelnya, Voronezh, Crimea), not inside the capital courtyard. |
| **4. Autonomous Tripwire Framing** | Binary episode detector requiring zero missingness and high persistence. | High-noise OSINT cannot be an autopilot alarm; its true operational value is **cueing expensive collection** (tasking commercial SAR / human review). |

---

## 3. Blueprint A: Accessible, Non-Optical "Costly Signals"

A "costly signal" in international relations and game theory is any action that is difficult to reverse, imposes domestic political or economic friction, or creates severe diplomatic exposure. Overhead satellites are not the only—or even the best—costly meters in open-source data.

### 3.1 Airspace & Maritime Exclusion Friction (NOTAMs & NAVAREA Warnings)
- **Mechanism:** Issuing a Notice to Airmen (NOTAM) closing airspace corridors or publishing a NAVAREA coastal warning for live-fire naval exercises imposes direct commercial rerouting costs, civilian disruption, and diplomatic protests.
- **Data Source:** FAA NOTAM archives, UK Hydrographic Office, US NGA Maritime Safety warnings.
- **Signal:** Rate of temporary danger areas / airspace restrictions declared per week along border frontiers; square kilometers of maritime exclusion zones active concurrently.

### 3.2 Administrative Gazette Gap Analysis (Secret Decree Sequences)
- **Mechanism:** Authoritarian and state bureaucracies publish executive decrees in sequential numbered registries (e.g. `pravo.gov.ru` in Russia, national gazettes in others). Classified or covert mobilization decrees are withheld from the public registry, leaving **missing serial numbers** in the published sequence (e.g., Decrees #101, #102, [gap], #105).
- **Data Source:** Automated daily scraping of official gazette numbering indexes.
- **Signal:** Count of missing sequence integers per 7-day rolling window. A spike in missing decree IDs directly measures covert administrative volume.

### 3.3 Financial & Liquidity Hoarding (Sovereign Spread & Money Market Basis)
- **Mechanism:** A state preparing for sanctions or kinetic operations hoards domestic cash liquidity and foreign exchange. Domestic banks scramble for overnight liquidity, causing money-market rate spikes (e.g. RUONIA basis over central bank policy rate) and short-end yield curve inversions.
- **Data Source:** Central bank statistical releases, exchange money-market fixings, sovereign yield curves.
- **Signal:** Short-end yield slope ($3\text{M} - 2\text{Y}$) inversion; overnight interbank spread anomalies; sudden shifts in domestic FX swap points.

### 3.4 Public Procurement Divergence
- **Mechanism:** Forward preparation requires emergency contracts (blood supply, mobile field hospital supplies, fuel reserves, rail transport contracts) or the abrupt cancellation/deferral of scheduled civilian municipal tenders.
- **Data Source:** State tender platforms (e.g. Russian `zakupki.gov.ru` or equivalent national procurement registries).
- **Signal:** Spike in urgent single-source medical/logistics contracts in border regions; anomalous cancellation rate of standard civil works.

---

## 4. Blueprint B: Dynamic Covariance & Early Warning Signals (EWS)

Instead of applying a static threshold $z \ge 	au$ to each series in isolation, we measure the **collapse of independence** across the system using dynamical systems theory.

### 4.1 Leading Eigenvalue of the Rolling Correlation Matrix ($\lambda_{\max}$)
Given $M$ daily standardized series $\mathbf{x}_t = (x_{1,t}, \dots, x_{M,t})^T$, we compute the rolling correlation matrix $R_t \in \mathbb{R}^{M \times M}$ over window $W \in [14, 30]$ days:

$$R_t = \frac{1}{W} \sum_{s=0}^{W-1} \tilde{\mathbf{x}}_{t-s} \tilde{\mathbf{x}}_{t-s}^T$$

- **Under Null (Independent Fluctuation):** By Random Matrix Theory (Marcenko-Pastur law), eigenvalues of $R_t$ fall within a predictable bounded band:
  $$\lambda_{\max} \le \left(1 + \sqrt{\frac{M}{W}}\right)^2$$
- **Under Strategic Coupling:** As disparate systems (news, attention, money markets, transport) become synchronized, variance condenses into the first principal component:
  $$\lambda_{\max}(R_t) \gg \lambda_{\text{RMT-bound}}$$
- **Advantage:** Detects subtle, simultaneous co-movements across 5 series where no single series breaches $z = 2.5$.

### 4.2 Multi-Information / Total Correlation
Measure total statistical dependency across the $M$ variables:

$$I(\mathbf{X}) = \sum_{i=1}^M H(X_i) - H(X_1, \dots, X_M) = -\frac{1}{2} \ln \det(R_t)$$

When the determinant $\det(R_t) 	o 0$, the system has become tightly coupled.

---

## 5. Blueprint C: Spatial Aggregation (Corridors vs. Stamps)

If remote sensing (VIIRS, SAR) is utilized:
1. **Zonal Boundary Buffers:** Replace 3 postage-stamp capital boxes with a **100km buffer strip along the contested border / staging area**.
2. **Atmospheric Resilience:** Aggregating radiance over a large geographical corridor ($500 \times 100\text{ km}$) averages out localized cloud gaps, preserving continuous time-series continuity.
3. **Transport Choke Points:** Focus spatial AOIs on known rail bottlenecks, bridge crossings, and maritime straits (e.g., Kerch Strait, Bosporus, Suwalki Gap) rather than government office complexes.

---

## 6. Blueprint D: Reframing "Amber" as Sensor Cueing / Analyst Triage

In operational intelligence, a weak-signal detector should not be an autonomous siren. It is an **attention and collection cueing mechanism**:

$$\text{Tasking Trigger} = (\lambda_{\max}(R_t) \ge \tau_{\text{coupled}}) \land (\text{Optical/Physical Coverage Gap})$$

- **When triggered:** The system automatically outputs a high-priority **Collection Tasking Order**:
  > *"Dyad X exhibits statistically significant multi-domain soft coupling ($p < 0.01$), but optical/visible infrared sensors are weather-blocked. Recommended Action: Cue high-resolution commercial SAR (Capella / ICEYE), task RF/SIGINT collectors, and alert the regional desk analyst."*

This converts the "amber evidence gap" from a methodological embarrassment into the **primary high-value operational output of the system**.

---

## 7. Roadmap to Execution

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 1 (Immediate / Low Cost): Mathematical Re-evaluation             │
│ Apply rolling correlation & λ_max to existing 4-case harvested data.   │
│ Verify if coupling separates 2022 from 2021 and hard negatives.        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 2: High-Construct Public Indicators                              │
│ Replace IA crawls and crt.sh with Gazette Gap & NOTAM / Yield curves. │
│ Re-run panel with non-optical costly signals.                          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 3: Spatial Buffers & Sensor-Cueing Pipeline                      │
│ Add frontier corridor aggregation and tasking-request emission.        │
└────────────────────────────────────────────────────────────────────────┘
```
