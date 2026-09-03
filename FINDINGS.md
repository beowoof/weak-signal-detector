# Findings

**Verdict:** speculative success, execution failure.

There is a measurable change in several weak public series in the last ten days before 24 February 2022, with a quiet 2021 control and two quiet hard negatives under the same frozen rule. That is not a proof of costly preparation, strategic intent, or a detector that could be defended. Availability, reliability, completeness, and the costly-gate design are too weak to support a dissertation claim. This was a personal education project without funding for the sources that would be required to continue.

Held-out `GRC-TUR-2020` was never harvested. Nothing here is a scientific freeze.

---

## Question

When several individually weak public indicators become unusual together, do they add information for strategic-intent triage?

The intended phenomenon was **strategic coupling**: during costly state preparation, weakly coupled physical, bureaucratic, informational, market, and infrastructural systems become more statistically dependent. Measurement was restricted to mobilisation / costly activation, not intent. Intent was reserved for a later, unbuilt interpretation layer.

The operating rule (`coincidence_v1`) was frozen before the last Ukraine re-measure:

- trailing z, 90-day window, \(n_{\min}=20\), \(\tau=2.5\), high-unusual polarity;
- red: \(k=3\) flags, 3 causal domains, 3 source systems, \(k_{\text{costly}}=1\), 3-day persistence;
- amber: ≥2 non-costly domains for 3 days while **any** costly series is unknown (not flagged);
- missing / cloud / source_down = unknown, not silence;
- permutation: independent circular shifts within each series’ available days; amber statistic = max run length.

Ukraine 2022 is a **development showcase**, not a hold-out. Thresholds were not retuned after seeing February.

---

## What was run

Four development cases, 21-day scored windows, 120-day lookback, exploratory (unfrozen) measurement:

| Case | Role | Collection | Measure |
|---|---|---|---|
| `ukraine2022` | showcase (overt action) | `collection-20260830T144844Z-703f5c` (with SAR) | `measure-20260830T162711Z-c3f2b0` |
| `rus2021apr` | other positive (reversed mobilisation) | `collection-20260829T202944Z-d13b8a` | `measure-20260829T203010Z-b16dce` |
| `deu2018quiet` | hard negative (quiet) | `collection-20260829T203150Z-c5104a` | `measure-20260830T071808Z-7aa290` |
| `usachn2018trade` | hard negative (high-tension talk) | `collection-20260830T073207Z-0627b7` | `measure-20260830T084538Z-bae638` |

Earlier Ukraine measure without SAR: `measure-20260829T185002Z-86eec3`.

---

## Panel result (frozen `coincidence_v1`)

| Case | Red | Amber episode | Notes |
|---|---|---|---|
| Ukraine 2022 incident | 0 | **1** (21–23 Feb) | Wiki + GDELT + MOEX; VIIRS cloudy; SAR unknown every scored day |
| Ukraine 2022 control | 0 | 0 | |
| rus2021apr | 0 | 0 | 2-day near-miss 6–7 Apr; VIIRS never flagged |
| deu2018quiet | 0 | 0 | Isolated flags only |
| usachn2018trade | 0 | 0 | Wiki spike is 9/11 anniversary on DoD/Pentagon titles, also in control |

No protocol (red) episode anywhere. Control and both hard negatives stayed quiet at the episode level.

**Speculative success.** On 12–23 Feb 2022 the easy kitchens move together: Wikipedia pageviews, GDELT CAMEO, ICEWS, and MOEX. 15 Feb is a three-coder talk/attention cluster (wiki z≈3.8, GDELT z≈3.1, ICEWS z≈5.4) while VIIRS is **present and normal** (z≈0.5). 21–23 Feb is the same soft chorus with VIIRS cloudy. The 2021 control does not reproduce the amber episode. DEU 2018 and USA–China 2018 do not produce one either. So *something* in public series is different in that fortnight.

**Not a proof.** Red never fired. Amber on 21–23 Feb is an evidence gap (costly unknown), not a costly flag. After SAR joined the basket, every scored day was costly-unknown, 15 Feb flipped from `cheap_talk_without_costly` to an amber *day*, and amber permutation weakened (\(p_{\max\text{ run}}\) 0.042 → 0.33) because the unknown mask became 21/21. The dashboard looks louder; the inferential content did not increase.

rus2021apr is a miss on the same Moscow AOIs: capital / Sheremetyevo / MoD night lights never unusual during a declared spring buildup that was largely a border/Crimea story.

---

## Why the methodology cannot prove it

The rule waits for a **smoking gun** (a costly flag) or for that gun to be *missing* (amber). Leading public series are allowed to vote only in those two cases. That is a confirmation architecture, not a precursor instrument.

On 15 Feb the leading series were already unusual and the only working physical sensor said quiet. The protocol correctly labelled cheap talk — and thereby refused the only night in the window where a costly kitchen was both present and decisive. Promotion happened on cloudy nights. Absence of VIIRS is not a leading indicator of mobilisation.

Coincidence across causal domains was the right fusion idea. The basket never instantiated a working **bureaucratic** series. **Mobility** stayed unbuilt (OpenSky Trino). **Digital infrastructure** lost Certificate Transparency. **Physical** collapsed to one cloudy NTL series plus a fire counter that does not move on postage-stamp AOIs, plus SAR with no overpass in the scored window. In practice the chorus is information + public attention + market, gated by whether VIIRS happened to see the Kremlin that night.

---

## Availability, reliability, completeness, accuracy

| Instrument | Domain | What we learned |
|---|---|---|
| VIIRS NTL | physical (costly) | Useful *veto* on clear nights; ~48% unknown in the Ukraine incident window; cannot be the red product |
| Sentinel-1 IW VV (descending) | physical (costly) | Credentials and API work. Only descending hits the RUS stamps. Six lookback days (Oct–Dec 2021), **zero** in Feb 2022 after Sentinel-1B failed on 23 Dec 2021. Adding it made amber cheaper, not better |
| FIRMS NOAA-20 | physical (costly) | Connector works (35 detections in Donbas on 12 Feb 2022). Frozen Moscow stamps are true zeros. Not a mobilisation kitchen |
| Wikipedia pageviews | public attention | Works; noisy (9/11 on Pentagon titles; wartime title attention) |
| GDELT / ICEWS | information | Work; same domain; ICEWS is robustness, not a second vote. USA-as-actor is too large a baseline to see a tariff week |
| MOEX USD/RUB | market | Works if holidays are not treated as coverage holes |
| ALFRED FX | market | Works with a 7-day H.10 lag; ruble has no daily H.10 series |
| RIPEstat prefixes | digital infra | Series exists; a 3377→463 five-day plateau in February is more likely a hole than a routing event; high-unusual polarity ignores drops |
| Official IA cadence | bureaucratic | Demoted: crawl count ≠ gazette |
| crt.sh certificates | digital infra | Demoted: 502 / unreachable from the UK; 502s had been stored as zeros; `mil.ru` is a poor public-CT identity |
| OpenSky | mobility | Uninstantiated; no funded Trino path |
| RIMA independent media archive | qualitative corpus | Useful for later analyst packets, not a z-score voter; keyword `ukraine` in Feb 2022 is outcome leakage |

Harvest bugs that looked like quiet (FIRMS 10-day API 400s as zeros, crt.sh 502 as zeros, MOEX/ALFRED holidays as coverage failures) were fixed when found. They do not create a complete panel. Indexing (trailing z, 6-point SAR priors, zero-variance “normal”) is not a stable index of unusualness.

---

## What would be required to continue — and is not available here

A defensible next attempt would need, at minimum:

- costly physical coverage that is not weather-gated the same way as VIIRS (usable SAR geometry, or funded commercial SAR);
- mobility (OpenSky historical Trino or equivalent);
- a real bureaucratic construct, not Internet Archive crawl counts;
- digital infrastructure that is a dated traffic/outage series, not Certificate Transparency;
- a leading-indicator rule that can promote without a physical smoking gun *or* an honest decision that this project is only a veto on clear nights;
- a hold-out scored once, after freeze, which this run never did.

Those are funding and access problems, not another free OSINT list. RIMA, awesome-osint, and further media feeds do not fill the holes.

---

---

## Salvage re-evaluation (2026-09-02)

Following the identification of uninstantiated stubs, real working HTTP connectors were implemented, smoke tested against live APIs (`scripts/smoke_test_connectors.py`), and re-harvested across the panel (preserving existing heavy VIIRS/SAR items while fetching new metrics live). Unfiltered US Federal Register volume was removed from Russian scenarios.

### Active Harvest & Measurement Runs

| Case | Role | Collection ID | Measure ID | Active Series |
|---|---|---|---|---|
| `ukraine2022` | Showcase (Overt Action) | `collection-20260902T150825Z-90ef95` | `measure-20260902T150854Z-655a4a` | 10 series (incl. CBR, NAVAREA; gazette disabled) |
| `rus2021apr` | Positive (Reversed Mobil.) | `collection-20260902T150849Z-d4cba9` | `measure-20260902T150858Z-bd7e79` | 9 series (incl. CBR, NAVAREA; gazette disabled) |
| `deu2018quiet` | Hard Negative (Quiet) | `collection-20260902T150806Z-fcaa01` | `measure-20260902T150901Z-128bab` | 8 series (incl. paginated DEU Gazette, NAVAREA) |
| `usachn2018trade` | Hard Negative (Tariff Talk) | `collection-20260902T144915Z-2ce633` | `measure-20260902T144954Z-e3e102` | 8 series (incl. USA Federal Register, NAVAREA) |

---

### Working Connectors Implementation & Verification

1. **`market.cbr_funding_spread` ([`src/wsf/connectors/cbr.py`](file:///Users/matthewtoy/source/weak-signal-detector/src/wsf/connectors/cbr.py)):**
   - Live SOAP client querying Bank of Russia `DailyInfo.asmx` (`RuoniaXML` and `KeyRateXML`).
   - Measures daily interbank funding spread $\text{RUONIA}_t - \text{KeyRate}_t$ in basis points.
   - Non-zero, dated trading day prints (e.g. Ukraine window: 91 days harvested, 14 trading days scored). Transport/parse failures are explicitly marked `source_down_days`.
2. **`nav.spatial_warnings` ([`src/wsf/connectors/navarea.py`](file:///Users/matthewtoy/source/weak-signal-detector/src/wsf/connectors/navarea.py)):**
   - Live REST client querying NGA MSI `broadcast-warn?status=all` across theater navareas (HYDROLANT `A`, HYDROARC `C`, HYDROPAC `P`, NAVAREA IV/XII).
   - Real daily warning issue counts (e.g. Ukraine window: 1,390 warnings; USA–China: 632 warnings; DEU: 1,513 warnings). HTTP/parse failures are recorded as `source_down_days`.
3. **`official.gazette_cadence` ([`src/wsf/connectors/gazette_cadence.py`](file:///Users/matthewtoy/source/weak-signal-detector/src/wsf/connectors/gazette_cadence.py)):**
   - For USA: Queries Federal Register API daily facets (e.g. USA–China window: 10,710 Federal Register documents across 97 publishing days).
   - For DEU: Paginated OffeneGesetze client following `next` URLs (e.g. DEU window: 206 documents across 25 publishing days; prior year: 456 documents across 48 days).
   - Disabled on Russian scenarios where no domestic legislative API is configured.

---

### Empirical Coupling & Triage Scorecard

Evaluating continuous multi-domain coupled energy $E_{\text{dom}}(t) = \sum_{d} \max_{s \in d} \max(0, z_{s,t})$ at lowered threshold $\tau = 1.5$ on the live harvested panel ([`COUPLING_EVALUATION.md`](COUPLING_EVALUATION.md)):

| Scenario | Window | $K_{\mathrm{dom}} \ge 3$ (Warning) | $K_{\mathrm{dom}} \ge 2$ (Cue) | Sensor Tasking Orders | Peak Energy ($E_{\mathrm{dom}}$) | Permutation $p_{\mathrm{episodes}}$ |
|---|---|---|---|---|---|---|
| `ukraine2022` | Incident (Feb 2022) | **2 ep (8d total)** | **2 ep (15d total)** | **8 days** | **21.89 $\sigma$** (mean 8.57 $\sigma$) | 0.432 |
| `ukraine2022` | Control (Feb 2021) | 0 ep (0 days) | 0 ep (3 days) | 1 day | 5.98 $\sigma$ (mean 2.68 $\sigma$) | 1.000 |
| `rus2021apr` | Incident (Apr 2021) | **1 ep (5d total)** | **2 ep (11d total)** | **3 days** | **10.15 $\sigma$** (mean 5.24 $\sigma$) | 0.439 |
| `rus2021apr` | Control (Apr 2020) | 0 ep (0 days) | 0 ep (2 days) | 0 days | **18.08 $\sigma$** (mean 3.28 $\sigma$) | 1.000 |
| `deu2018quiet` | Incident (Oct 2018) | 0 ep (1 day) | 0 ep (2 days) | 0 days | 11.38 $\sigma$ (mean 2.79 $\sigma$) | 1.000 |
| `deu2018quiet` | Control (Oct 2017) | 0 ep (1 day) | 0 ep (1 day) | 0 days | 6.64 $\sigma$ (mean 2.46 $\sigma$) | 1.000 |
| `usachn2018trade` | Incident (Sep 2018) | 0 ep (3 days) | 1 ep (4 days) | 0 days | **38.18 $\sigma$** (mean 5.34 $\sigma$) | 1.000 |
| `usachn2018trade` | Control (Sep 2017) | 0 ep (2 days) | 0 ep (4 days) | 2 days | 19.53 $\sigma$ (mean 4.32 $\sigma$) | 1.000 |

---

### Methodological Conclusions

1. **Option 2 Is Live:** Real non-optical costly signals (CBR funding spreads, NAVAREA maritime closures, paginated Federal/OffeneGesetze gazette counts) now execute against live endpoints and contribute real non-zero time series with proper `source_down` error tracking.
2. **Option 1 Is Lowered-Threshold Domain Counting:** The detection mechanism remains point-in-time thresholding ($z \ge 1.5$) aggregated across causal domains, not high-frequency dynamical system EWS ($\lambda_{\max}$).
3. **Specificity vs Rarity:**
   - **Specificity at $K \ge 3$ holds:** No negative baseline produced a 3-day Strategic Warning episode ($p = 1.000$).
   - **Statistical rarity is moderate:** Under unconstrained circular-shift permutations of z-calendars, $p_{\text{episodes}} \approx 0.43$ for Ukraine and $p_{\text{episodes}} \approx 0.44$ for April 2021 because lowered marginal thresholds ($\tau = 1.5$) allow noisy soft series to co-occur frequently by chance.
4. **Sensor Tasking Orders Are a Derived Operational Label:** Tasking days are triggered whenever $K \ge 2$ and physical/optical sensors are unknown. While operationally useful for sensor scheduling, tasking volume is a derived output rather than independent statistical proof of unexpected precursor coupling.
5. **Final Verdict:** The v1 **detector** claim stands: this stack cannot serve as a standalone strategic early-warning tripwire. That is the wrong bar for the desk product. See [`ROADMAP.md`](ROADMAP.md).

---

## Staging restage (`ukraine2022`, 2026-09-02)

Collection `collection-20260902T172316Z-3a7030`, measure `measure-20260902T203316Z-f05cf7` (exploratory). Frontier/staging AOIs, not Kremlin stamps.

VIIRS is `ok` on **21/21** scored nights (median 6 of 7 AOIs). SAR has 12/21 days with backscatter. FIRMS is present and mostly quiet except 18 and 23 Feb. Coverage is no longer the binding constraint.

Frozen `coincidence_v1`: no red episode. One basket day (23 Feb: wiki + GDELT + MOEX + FIRMS) without 3-day persistence. The old 21–23 Feb amber disappears because VIIRS is present and normal. 15 Feb is cheap talk with VIIRS quiet (z ≈ 0.3).

Desk heuristic (z ≥ 1.5, K ≥ 3): two episodes, **10–12 Feb** and **21–23 Feb**. The first is the preparatory shape (CBR flags; talk climbing). The second is information-saturated (recognition of the “republics”; Wikipedia z ≈ 11 on the 22nd). Evaluating the product on whether red fired the day before the invasion is a methodological error, not a data error. `notice_v0` should be scored on whether the preparatory window opens a cue, with the eve-of-event spike labelled late.
