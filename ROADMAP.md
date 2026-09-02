# Analyst-desk roadmap

**Product:** a regional collection indicator. It reproducibly identifies changes in public information and measurements, opens a cue when a configured heuristic is met, gathers additional context, and produces an evidence packet an analyst can argue with. It does not determine intent or predict that a state will act within a specified number of days.

This is a proof of concept for a multipart analytical workflow. Weak-signal detection opens the analysis; it does not complete it. Frozen `coincidence_v1` stays frozen. Any broader cueing rule is named, versioned, and reported separately as a heuristic notice policy.

All inputs are open-source information: lawfully and publicly obtainable data, documents, reporting, maps, and imagery. Public registration or an API key is an access mechanism, not a disqualifier.

---

## Epistemic model

“Deterministic” means reproducible given the same inputs and configuration. It does not mean context-free truth. A baseline is path dependent, an AOI encodes a geographic hypothesis, and several apparently independent series may share the same information environment.

The product must preserve these layers rather than flattening them into one score:

| Layer | Example | Status |
|---|---|---|
| **Observed** | luminance, event count, exchange rate, document count, missing observation | immutable evidence with provenance and source health |
| **Derived** | baseline, z-score, change, coverage, spatial aggregation | reproducible but dependent on declared history, geography, transformations, and availability |
| **Heuristic** | persistent cross-domain convergence, evidence-gap cue, recommended collection posture | versioned analytical rule; useful without being a finding of intent |
| **Contextual** | official warnings, news environment, maps, public imagery, contemporary qualitative reporting | bounded evidence that may explain, amplify, corroborate, or contradict the cue |
| **Assessed** | competing hypotheses, uncertainty, significance, recommended next step | analyst-owned judgement |

Every packet should make the lineage visible:

```text
observed value
→ baseline and geographic frame
→ derived unusualness
→ heuristic cue
→ contextual evidence
→ analyst assessment
```

The human is not a safety approval at the end. Human judgement is an epistemically necessary part of the method.

---

## Analyst loop (target)

1. **Scenario / region.** A theatre declares the focal actor, counterparts, AOIs, quantitative sources, contextual sources, and historical windows.
2. **Information-environment baseline.** Maintain the contemporary public context: reporting volume, tone/intensity, originating-source diversity, official posture, narrative concentration, geographic focus, and change over time.
3. **Watch.** Daily observations and derived scores land. The desk waits for configured convergence across causal domains rather than staring at raw z-plots.
4. **Notice.** A versioned heuristic opens a cue: what moved, which domains contributed, what was unknown, what physical or administrative sources did or did not corroborate, and the prevailing information environment.
5. **Collection posture.** The notice recommends how much additional public-source collection is justified. The analyst may accept or change it.
6. **Context harvest.** Collect bounded, cutoff-safe news/RIMA, official statements, maps, public EO catalogues, and other public sources allowed by the posture.
7. **Evidence packet.** Align hard statistics with cited qualitative evidence, dependencies, counterevidence, missingness, assumptions, and collection timing.
8. **Assessment and report.** Compare competing hypotheses. A model may draft; the analyst edits, owns, and signs the conclusion.

Competing hypotheses (already in `config/interpretation_protocol.yaml`):

- routine variation
- exercise or demonstration
- defensive readiness
- reversible mobilisation
- preparation for overt action
- collection or measurement artifact

The LLM is an optional packet drafter, not the authority. It may not create observations, alter measurements, open notices, resolve intent, or remove alternative hypotheses.

---

## Information-environment baseline

The existing basket proxies parts of the public information environment through GDELT, ICEWS, Wikipedia, and markets, but it does not describe that environment explicitly. Add a contextual baseline with multiple dimensions rather than a single sentiment number:

- relevant reporting volume relative to the actor/dyad’s own history;
- negative tone, emotional polarity, and intensity;
- originating-source diversity after obvious repetition and syndication;
- official warnings, statements, sanctions language, and diplomatic activity;
- narrative concentration versus competing explanations;
- movement from general geopolitical rhetoric toward particular regions, ports, corridors, or facilities;
- level, direction, and acceleration of each dimension.

Candidate contextual sources include GDELT GKG, Media Cloud, RIMA, official government/NATO/EU/UN publications, and contemporary regional reporting. These describe the information environment; they do not create extra independent votes merely because many articles repeat the same claim.

The baseline should explain rather than silently reweight a cue. For example: the information, attention, and market series are elevated, but the environment is already saturated by coordinated public warnings, so the convergence may be media-amplified.

---

## Collection posture

The analogue of a public warning level is a **collection setting**, not a threat estimate:

| Posture | Meaning | Additional collection |
|---|---|---|
| `routine` | normal geopolitical background | fixed quantitative basket only |
| `heightened` | public rhetoric or reporting environment has materially shifted | broader official and source-balanced news collection |
| `focused` | a quantitative cue exists or attention has become geographically specific | AOI maps, public EO catalogue search, regional reporting, and relevant maritime/aviation context |
| `surge_review` | the analyst judges the configuration worth concentrated examination | refresh every relevant public source and produce a full evidence packet |

Triggered sources contextualise a notice but cannot retroactively strengthen the rule that opened it. If a contextual source later deserves a quantitative vote, it must be qualified and baselined separately.

Potential posture-dependent sources include:

- OpenStreetMap infrastructure layers for railheads, roads, airfields, ports, and border crossings;
- Copernicus catalogue searches and public imagery over relevant AOIs;
- FIRMS/VIIRS/Sentinel revisits and coverage status;
- public maritime presence or SAR vessel-detection datasets where geographically relevant;
- NAVAREA, NOTAM, gazette, central-bank, parliamentary, and official-statement sources;
- RIMA, GDELT GKG, Media Cloud, and bounded regional-news queries.

These are not all justified as continuous detector inputs. The collection posture is what makes their selective use proportionate and legible.

---

## What exists today

| Piece | Status |
|---|---|
| Region = scenario (`scenario.json`, AOIs, sources) | Built for retrospective PoC cases |
| Immutable observations, provenance, availability, coverage, and source health | Built |
| Daily z, costly unknown versus flagged, and frozen `coincidence_v1` | Built (`wsd measure`) |
| Multi-domain lowered-threshold coupling and “collect more” annotations | Built as an exploratory heuristic (`src/wsf/analysis/coupling.py`, dashboard coupling tab) |
| Frontier/staging RUS AOIs and current physical restage | Configured. `ukraine2022` VIIRS/FIRMS/SAR re-harvest is in flight on the staging boxes (not yet a new active measure). `rus2021apr` restage not started. |
| CBR, NAVAREA, DEU/USA gazette as live costly/admin series | Built (RUS gazette and NOTAM still out) |
| Information-environment baseline | Missing; existing series provide partial proxies only |
| Collection posture | Missing |
| Dashboard as **inbox of notices** | Missing; it remains a retrospective results viewer |
| On-cue context harvest | Missing; RIMA is a corpus, not triggered by a notice |
| Evidence packet | Missing; `interpretation/` directories are empty |
| LLM assessment | Contract only (`intent_triage_v0`, `enabled: false`) |
| Analyst report | Missing; `reports/` directories are empty |

The measurement layer already emits `analyst_action: review_soft_correlation_and_resolve_costly_source_gap`. Nothing yet turns that into a persisted analyst object or a complete contextual workflow.

---

## Phases

### 0. Preserve the current analytical state

- Treat the September 2026 restaged measurements as exploratory PoC inputs, not a scientific freeze.
- Keep `coincidence_v1` unchanged.
- Keep the lowered-threshold coupling experiment separate. It may open heuristic cues, but it is not a renamed scientific alert.
- Keep DEU/USA hard negatives geographically appropriate to their hypotheses rather than turning them into simulated mobilisation desks.

### 1. Define and persist the notice

Promote a coupling or evidence-gap episode into a persisted notice, not just a chart annotation.

Minimum fields:

- notice id, scenario, window, score/measurement id, and creation time;
- notice-policy id and parameters;
- start/end, contributing domains and series, and peak energy;
- observed, derived, and heuristic facts kept separately;
- optical/SAR, CBR/NAVAREA, and other relevant source status;
- coverage holes and explicit unknowns;
- information-environment snapshot;
- recommended and analyst-selected collection posture;
- state (`new` / `acked` / `in_packet` / `closed`) and closure rationale.

Do not require a costly physical flag to open a notice. Cloudy plus a chorus is a cue to collect more. Clear and quiet physical data alongside a chorus is also a cue, with a different next action. The dashboard becomes an inbox over persisted notices rather than the system that calculates them.

### 2. Build the information-environment snapshot

For each notice date, materialise a cutoff-safe contextual baseline. Record the frozen query, source set, dates, source diversity, tone/intensity measures, official posture, geographic focus, and caveats.

This snapshot is explanatory context. It neither edits the underlying scores nor adds votes to the notice after the fact.

### 3. Harvest context and build the evidence packet

Triggered by the notice and bounded by its selected collection posture:

- contributing-series excerpts: raw values, derivations, baselines, z, missingness, and provenance;
- contemporary qualitative material already on disk, including RIMA and official text;
- posture-dependent public news, maps, EO catalogues, and relevant movement/administrative sources;
- explicit counterevidence and “what we did not see”;
- source-dependency notes: reporting, coders, articles, sensors, and administrative systems must not masquerade as independent corroboration;
- retrieval and publication times that distinguish pre-notice evidence from context gathered afterward.

Outcome-encoded source selection and post-cutoff knowledge are forbidden in historical replay. Genuinely pre-cutoff public language is retained even if it later resembles the known outcome.

Output: `scenarios/<id>/interpretation/<packet-id>/evidence.json` plus stable cited snippets. The packet is complete and useful without a model.

### 4. Exercise the human workflow without an LLM

Replay notices across `ukraine2022`, `rus2021apr`, `deu2018quiet`, and `usachn2018trade`.

Ask:

- does the same input produce the same notice and packet?
- does the notice accurately distinguish observation, derivation, heuristic, context, and assessment?
- does the additional collection explain, corroborate, contradict, or leave the cue unresolved?
- can an analyst reach and document “interesting but not significant” without fighting the product?
- is notice volume manageable?

This is a workflow and usefulness gate, not an invasion-prediction accuracy test.

### 5. Add the draft assessment (LLM)

Fill the empty interpretation layer only after the packet works for a human.

- Inputs: only the immutable packet. No post-cutoff material or uncited model-memory claims.
- Output: structured draft containing a statistics recap, cited qualitative evidence, support/contradict/unknown for every hypothesis, dependencies, uncertainty, and recommended public-source collection.
- Local Ollama (`qwen3.8:27b-mlx`) matches the existing methods contract. A hosted model is optional later and is not required to prove the loop.
- Repeats and conditions in `intent_triage_v0` remain a methods experiment. The desk product is one analyst-owned report, not five hidden samples.
- Preserve the raw model draft separately from analyst edits.

### 6. Produce the analyst report

`scenarios/<id>/reports/<report-id>/` as the thing an analyst would actually send:

1. cue: what converged, for how long, under which heuristic;
2. observations and derivations: hard statistics, baselines, geography, coverage, and permutation context;
3. information environment: prevailing public posture and likely amplification/dependency;
4. contextual evidence and counterevidence: cited and dated;
5. assessment: competing hypotheses, uncertainty, and what would change the judgement;
6. recommended public-source collection: wait, broaden news/official sources, inspect maps/catalogues, or enter focused review.

The report says: “these public channels changed together; here is the context we collected; here is how I assess it.” It never turns that configuration into a countdown prediction.

### 7. Watch loop, only after phases 1–6 work retrospectively

Daily score the live desk and open notices without a human running `wsd measure` by hand. This is later PoC operations, not a claim that the underlying scientific detector has been validated.

---

## PoC success criteria

1. The same inputs and configuration produce the same observations, derivations, notice, and initial packet.
2. Every notice accurately states what moved, what stayed quiet, what was unavailable, and which sources share an information substrate.
3. The information-environment baseline provides useful context without becoming a hidden extra vote.
4. Posture-dependent collection retrieves relevant public evidence without retroactively changing the trigger.
5. The packet keeps observations, assumptions, heuristics, contextual evidence, and analyst judgement distinct.
6. An analyst can document routine variation, unresolved significance, or elevated concern without the interface pushing toward an alarming conclusion.
7. Notice volume and context-harvest cost remain manageable for a single desk.

---

## What we will not do

- Retune `z`, `k`, persistence, AOIs, or baselines on Ukraine to manufacture a better historical result.
- Call a heuristic notice a statistically validated detector alert.
- Treat sentiment, article count, or repeated headlines as independent corroboration.
- Let triggered contextual sources retroactively strengthen the notice that caused their collection.
- Let the LLM vote in the combiner, alter evidence, open a notice, or own the assessment.
- Treat VIIRS, SAR, CBR, NAVAREA, or any single source as a smoking gun.
- Score `GRC-TUR-2020` as if a freeze existed.
- Apply a source because it is available when it has no geographic or causal relevance, such as US Federal Register volume on a Russia desk.

---

## Near-term order

1. Define `notice_v0`, the information-environment snapshot, and collection-posture contracts.
2. Persist notices from the existing retrospective measurements and make the dashboard an inbox over them.
3. Build one deterministic, model-free packet from the existing Ukraine RIMA/official corpus plus an information-environment snapshot.
4. Replay the notice-to-packet workflow across the other positive and hard-negative cases.
5. Have a human write one complete assessment and report from a packet.
6. Add one local-model draft and compare it with the human-only workflow.
7. Then decide whether additional contextual connectors, a hosted model, or a daily watch loop are worth implementing.
