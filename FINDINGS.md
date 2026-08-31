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

## Stop

Do not add sources. Do not retune \(z\), \(k\), or persistence on Ukraine. Do not score `GRC-TUR-2020` as if a freeze existed. Do not describe the 21–23 Feb amber episode as a validated detector.

The honest artefact is a negative methods result: **weak public series do move; this stack cannot say what that movement is.** That is sufficient to stop. It is not sufficient to prove the fusion claim.
