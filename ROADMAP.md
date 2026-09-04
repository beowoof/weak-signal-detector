# Analyst-desk roadmap

**Product:** a regional collection cueing desk. It does not determine intent or predict that a state will act within a specified number of days.

Product language is not inherited from file names. The chain is:

```text
anomaly  →  notice  →  packet  →  report
look here   alert      brief      send up the chain
```

| Object | User meaning | Not |
|---|---|---|
| **Anomaly** | The machine saw unusual co-movement. Look here. Coupling episode / `coincidence_v1` flag. | Not an alert. Not a brief. |
| **Notice** | An alert in the inbox. A human is being told to look. Immutable trigger + mutable workflow. | Not the brief. Restating z-scores is still the alert. |
| **Packet** | A brief: the anomaly, plus information environment, plus geopolitical/official context, cutoff-safe. | Not an alert with extra JSON. Not a judgement. |
| **Report** | What you send up the chain. Analyst-owned assessment. | Not a model transcript. Not the packet. |

A packet that only copies the notice’s series-days is still a notice. It becomes a brief when the information-environment snapshot and posture-bounded context are in the same object.

This is a proof of concept for a multipart analytical workflow. **Weak-signal detection opens the analysis; it does not complete it.** Frozen `coincidence_v1` stays frozen. Any broader cueing rule is named, versioned, and reported separately as a heuristic notice policy.

Three things that must stay unentangled:

```text
detection of change  ≠  collection decision  ≠  assessment of meaning
```

Anomaly is the first. Notice plus posture is the second. Packet plus report is the third.

All inputs are open-source information: lawfully and publicly obtainable data, documents, reporting, maps, and imagery. Public registration or an API key is an access mechanism, not a disqualifier.

The quantitative detector is largely finished infrastructure. The next research object is a **packet that is actually a brief** (environment + context), then a report.

---

## The wrong bar

The staging restage (`measure-20260902T203316Z-f05cf7`) shows this is **not a collection failure**. VIIRS is valid on 21/21 scored nights. The 22 February energy spike is convergent on the desk heuristic (K ≥ 3 at z ≥ 1.5). Frozen `coincidence_v1` still does not emit a red episode.

The error is the success test we inherited:

| Wrong bar | Why it is wrong for this product |
|---|---|
| Did `coincidence_v1` fire red? | That rule waits for z ≥ 2.5, a costly flag, and 3-day persistence. It is a confirmation architecture. |
| Did energy peak the day before the invasion? | 21 Feb is recognition of the “republics”; 22 Feb is the world paying attention. That is no longer a weak signal. |
| Did physical join the chorus? | Staging lights and FIRMS are corroboration or a gap, not the thing that makes a cue valid. |

The right bar for `notice_v0`:

- Open a cue when independent public channels become unusual **together in the preparatory window**, not when the information environment saturates on the eve of a known event.
- For Ukraine, that is the **10–15 February** shape (CBR flags, talk/attention climbing, VIIRS present and quiet on the 15th), not the 22 February attention mountain.
- A notice on 21–23 Feb is still legitimate (the heuristic did fire). It is a **late, information-saturated** notice. Do not treat catching it as proof the desk works, and do not treat missing `coincidence_v1` red as proof the desk failed.
- Specificity still matters: hard negatives must not produce the same preparatory-window notice. Rarity under permutation is a diagnostic, not the product requirement.

Do not retune `coincidence_v1` on Ukraine to pass the old bar. Name the cueing rule separately. Evaluate it on whether a sitting analyst would have been told to collect more *before* the story was already on every front page.

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

### Two times

Every observation, document, and packet item carries both clocks. A document published at 09:00 and retrieved at 16:00 must not silently appear in a 10:00 replay. A later-corrected source preserves what was knowable at the time.

| Clock | Meaning |
|---|---|
| `evidence_time` | when the underlying thing happened or was published |
| `knowledge_time` | when this desk could reasonably have obtained it (`available_at` / `retrieved_at`) |

This is the same cutoff machinery as the historical work. The packet layer makes it mandatory on qualitative items, not only on time series.

---

## Analyst loop (target)

1. **Scenario / region.** A theatre declares the focal actor, counterparts, AOIs, quantitative sources, contextual sources, and historical windows.
2. **Information-environment baseline.** Maintain the contemporary public context: reporting volume, tone/intensity, originating-source diversity, official posture, narrative concentration, geographic focus, and change over time.
3. **Watch.** Daily observations and derived scores land. The desk waits for configured convergence across causal domains rather than staring at raw z-plots.
4. **Notice.** A versioned heuristic opens an **immutable event**: what moved, which domains contributed, what was unknown, what physical or administrative sources did or did not corroborate, and the prevailing information environment. Workflow state (`new` / `acked` / `in_packet` / `closed`) is mutable; the triggering facts are not.
5. **Collection posture.** The notice recommends how much additional public-source collection is justified. The analyst may accept or change it. Posture is effort, not threat.
6. **Context harvest.** Collect bounded, cutoff-safe news/RIMA, official statements, maps, public EO catalogues, and other public sources allowed by the posture. That material is stored outside the trigger namespace.
7. **Evidence packet.** Align hard statistics with cited qualitative evidence, dependencies, counterevidence, missingness, assumptions, and both clocks.
8. **Assessment and report.** Compare competing hypotheses. A model may draft; the analyst edits, owns, and signs the conclusion.

Competing hypotheses (already in `config/interpretation_protocol.yaml`):

- routine variation
- exercise or demonstration
- defensive readiness
- reversible mobilisation
- preparation for overt action
- collection or measurement artifact

The LLM is an optional packet drafter, not the authority. It may not create observations, alter measurements, open notices, resolve intent, omit a hypothesis, or remove alternative hypotheses.

---

## Notice: immutable event plus mutable workflow

`notice_v0` is two objects that share an id:

**Frozen at creation (never edited):**

- notice id, scenario, window, measurement id, policy id and parameters;
- `created_at` (knowledge_time of the notice);
- episode start/end (`evidence_time` span);
- observed, derived, and heuristic facts, kept in separate maps;
- contributing domains and series, peak energy, source states, coverage holes, unknowns;
- information-environment snapshot id (if present at open);
- recommended collection posture.

**Mutable workflow only:**

- state (`new` / `acked` / `watching` / `context_requested` / `in_packet` / `dismissed` / `rejected` / `closed`);
- operator actions: mark as read, re-examine signal, request more information, ignore, flag incorrect signal;
- append-only event log;
- analyst-selected posture (may differ from recommended);
- comments, packet id, report id, closure rationale.

This is a human state machine on the notice. It is not an LLM graph. Requesting more information records intent and may later enqueue a collector; it does not search the live web.

If later data change the interpretation, write a subsequent assessment or a new notice. Do not rewrite history. A later measurement is a different measurement id.

Do not require a costly physical flag to open a notice. Cloudy plus a chorus is a cue to collect more. Clear and quiet physical data alongside a chorus is also a cue, with a different next action.

`heightened` (rhetoric/environment shifted without a quantitative chorus) is a **second notice-policy id**, not the same rule as cross-domain co-movement.

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

GDELT Events CAMEO counts (`talk.gdelt_cameo`) are not this baseline. Volume, tone, source diversity, and geographic focus belong in GKG / Media Cloud / RIMA / official publications. They describe the environment; they do not create extra independent votes because many articles repeat the same claim.

The baseline should explain rather than silently reweight a cue. For example: the information, attention, and market series are elevated, but the environment is already saturated by coordinated public warnings, so the convergence may be media-amplified.

### Declared dependency graph

Contextual items carry enough provenance that “five datasets rose” cannot pass for five processes:

| Field | Purpose |
|---|---|
| `originating_source_id` | the outlet or issuer, not the aggregator |
| `syndication_cluster_id` | obvious reprints / wire copies |
| `measurement_family` | e.g. coder-events, pageviews, official-text, market-print |
| `shared_information_substrate` | e.g. `public_reporting`, `official_communique`, `exchange_fixing` |

Perfect causal provenance is not required. The packet must make endogenous corroboration obvious.

---

## Collection posture

The analogue of a public warning level is a **collection setting**, not a threat estimate. Posture is **non-monotonic**: `surge_review` means greater expenditure of analytical effort, not greater concern than `focused`. An analyst may choose `surge_review` because the evidence is contradictory and significance is unclear.

| Posture | Meaning | Additional collection |
|---|---|---|
| `routine` | normal geopolitical background | fixed quantitative basket only |
| `heightened` | public rhetoric or reporting environment has materially shifted | broader official and source-balanced news collection |
| `focused` | a quantitative cue exists or attention has become geographically specific | AOI maps, public EO catalogue search, regional reporting, and relevant maritime/aviation context |
| `surge_review` | the analyst judges the configuration worth concentrated examination | refresh every relevant public source and produce a full evidence packet |

Triggered sources contextualise a notice but cannot retroactively strengthen the rule that opened it. Encode that in storage, not convention: context harvest writes to `interpretation/<packet-id>/`, never into the measurement that the notice cites. Anything with `knowledge_time` after `notice.created_at` is incapable of appearing in the trigger calculation.

If a contextual source later deserves a quantitative vote, it must be qualified and baselined separately, then used only by a later measurement id.

Potential posture-dependent sources include:

- OpenStreetMap infrastructure layers for railheads, roads, airfields, ports, and border crossings;
- Copernicus catalogue searches and public imagery over relevant AOIs;
- FIRMS/VIIRS/Sentinel revisits and coverage status;
- public maritime presence or SAR vessel-detection datasets where geographically relevant;
- NAVAREA, NOTAM, gazette, central-bank, parliamentary, and official-statement sources;
- RIMA, GDELT GKG, Media Cloud, and bounded regional-news queries.

These are not all justified as continuous detector inputs. The collection posture is what makes their selective use proportionate and legible.

---

## Evidence packet

The sitting product is an intelligence brief organised around what changed, why it is on the watchlist, what the evidence can and cannot support, competing explanations, and what to collect next. The audit record (series-days, z-scores, reconstructed latency, missingness, shared substrates) is preserved behind that product; it is not the front door.

Three epistemic levels stay distinct:

```text
observation  →  analytic implication  →  assessment
```

The compiler lives in the middle. It may say “CBR funding spread reached 3.72σ” and “this is an unusually large move in domestic financial conditions.” It may not say “this is Russian preparation for military action.” Competing explanations carry PHIA Probability Yardstick likelihoods (at watch, typically `realistic possibility`; nothing is selected). Analytical confidence uses the AnCR scale (Low / Moderate / High) and states why. “What would discriminate?” turns the hypothesis set into a collection requirement.

Analytic state is an observable-system label, not adversary intent:

```text
quiet → anomaly → watch → preparatory pattern → escalation
```

For the Ukraine preparatory window (10–12 February 2022) the playback is **watch: broadening multi-domain anomaly**. Absence of VIIRS at cutoff is a prominent availability warning, not a quiet physical panel.

The packet is aggressively boring about assessment. The builder creates objects; it does **not** assign analytical significance. Support / contradict / contextualise on evidence items is filled by the analyst, or later by the interpretation layer — never by the first model pass inventing classifications.

```text
notice
measurement_snapshot
information_environment
collected_evidence[]
counterevidence[]
unknowns[]
dependencies[]
hypotheses[]          # present, empty of assessments until the analyst (or later model) fills them
collection_log[]
```

Each evidence item carries:

- `evidence_time`, `knowledge_time`
- source, geographic scope
- relationship to the cue (which series/domain/AOI, or “environment”)
- `significance`: unset at build time (`unassigned` | later `supports` | `contradicts` | `contextualises`)

Output: `scenarios/<id>/interpretation/<packet-id>/evidence.json` plus stable cited snippets. The packet is complete and useful without a model, without the raw repository, and without recollection of why an indicator was configured as it was. If it cannot support a sitting analyst’s judgement on those terms, a fluent model will only conceal the deficiency.

---

## What exists today

| Piece | Status |
|---|---|
| Region = scenario (`scenario.json`, AOIs, sources) | Built for retrospective PoC cases |
| Immutable observations, provenance, availability, coverage, and source health | Built (`available_at` / `retrieved_at` already exist on observations) |
| Daily z, costly unknown versus flagged, and frozen `coincidence_v1` | Built (`wsd measure`) |
| Multi-domain lowered-threshold coupling and “collect more” annotations | Built as an exploratory heuristic (`src/wsf/analysis/coupling.py`, dashboard coupling tab) |
| Frontier/staging RUS AOIs and current physical restage | `ukraine2022` restaged and measured (`collection-20260902T172316Z-3a7030` / `measure-20260902T203316Z-f05cf7`, exploratory). `rus2021apr` restaged (`collection-20260904T095246Z-6a1a2a` / `measure-20260904T095423Z-ceca4f`): coincidence_v1 0 alerts; one K≥3 coupling notice 5–8 Apr (`notice-1e8be533f571`). DEU/USA emit 0 notices. |
| CBR, NAVAREA, DEU/USA gazette as live costly/admin series | Built (RUS gazette and NOTAM still out) |
| Information-environment baseline | Missing; existing series provide partial proxies only |
| Collection posture | Missing |
| Anomaly (coupling / coincidence) | Built. K≥3 episodes are the “look here” in the data. |
| Notice (alert) | Built (`notice_v0`, inbox). Immutable trigger + workflow. |
| Packet (brief) | Model-free product compiler. Default playback is assessment / watchlist / competing explanations / collection priorities. Analytic state `quiet → anomaly → watch → preparatory_pattern → escalation` describes observable system state, not intent. z-scores and reconstructed-latency machinery sit in an evidence drawer. |
| Report (send up the chain) | Dump-in working assessment on the notice (`report_v0`). Template of what a sitting analyst would cover; human-owned. Not a finished send-up product. |
| Dashboard as **inbox of notices** | Notices are the home surface (alerts). Anomaly charts are a drill-down. |
| On-cue context harvest | Chronology / physical refresh / official pack as packet-scoped jobs. Physical and Official jobs carry a plan (sources, AOIs, admissible dates, discriminators). Official pack harvests **declared UK/US posture**. Physical posture harvests Copernicus S1/S2 catalogue pointers (no scene download, no vote). OSM, RIMA, GKG, and live search remain analyst-search rows. |
| LLM assessment | Contract only (`intent_triage_v0`, `enabled: false`) |

The measurement layer already emits `analyst_action: review_soft_correlation_and_resolve_costly_source_gap`. Nothing yet turns that into a persisted analyst object or a complete contextual workflow.

---

## Phases

### 0. Preserve the current analytical state

- Treat the September 2026 restaged measurements as exploratory PoC inputs, not a scientific freeze.
- Pin the observed layer the notices cite (`scenarios/ukraine2022/desk_pin.json`). Do not run `wsd scenario freeze`: that locks collection behind a GO review this showcase has not earned, and it would block later harvests. Do not recollect `ukraine2022` until the first packet exists.
- Keep `coincidence_v1` unchanged. Do not retune it into a cueing product.
- Keep the lowered-threshold coupling experiment separate. It may open heuristic cues, but it is not a renamed scientific alert.
- Keep DEU/USA hard negatives geographically appropriate to their hypotheses rather than turning them into simulated mobilisation desks.

### 1. Define and persist the notice

Promote a coupling or evidence-gap episode into a persisted notice. Dashboard is an inbox over those objects, not the calculator.

See [Notice: immutable event plus mutable workflow](#notice-immutable-event-plus-mutable-workflow).

### 2. Build the information-environment snapshot

For each notice date, materialise a cutoff-safe contextual baseline. Record the frozen query, source set, both clocks, source diversity, tone/intensity measures, official posture, geographic focus, dependency-graph fields, and caveats.

This snapshot is explanatory context. It neither edits the underlying scores nor adds votes to the notice after the fact.

### 3. Harvest context and build the evidence packet

Triggered by the notice, bounded by selected posture, written only into the packet namespace. See [Evidence packet](#evidence-packet).

Outcome-encoded source selection and post-cutoff knowledge are forbidden in historical replay. Genuinely pre-cutoff public language is retained even if it later resembles the known outcome.

### 4. Exercise the human workflow without an LLM

Replay notices across `ukraine2022`, `rus2021apr`, `deu2018quiet`, and `usachn2018trade`. Resist opening the model the moment `evidence.json` exists.

Ask:

- does the same input produce the same notice and packet?
- does the notice distinguish observation, derivation, heuristic, context, and assessment?
- does additional collection explain, corroborate, contradict, or leave the cue unresolved?
- can an analyst sit with the packet alone — no repo, notebooks, or dashboard internals — and form a judgement?
- can they document “interesting but not significant” without fighting the product?
- is notice volume manageable?

This is a workflow and usefulness gate, not an invasion-prediction accuracy test. If the packet fails it, more feeds will not fix it.

### 5. Add the draft assessment (LLM)

Fill the empty interpretation layer only after the packet works for a human.

- Inputs: only the immutable packet. No post-cutoff material or uncited model-memory claims.
- The model does not invent evidence items or their `significance` on first pass if the packet still has `unassigned`.
- Output schema **requires every hypothesis**, each with:

  ```text
  hypothesis
  supporting_evidence[]
  contradicting_evidence[]
  unknowns[]
  dependency_cautions[]
  assessment
  confidence
  ```

  `confidence` is confidence in the assessment **relative to the packet**, not a probability that a state will act. The model may not omit `routine_variation` because another hypothesis is more interesting.
- Local Ollama (`qwen3.8:27b-mlx`) matches the existing methods contract. A hosted model is optional later and is not required to prove the loop.
- Repeats and conditions in `intent_triage_v0` remain a methods experiment. The desk product is one analyst-owned report, not five hidden samples.
- Preserve the raw model draft separately from analyst edits.

### 6. Produce the analyst report

`scenarios/<id>/reports/<report-id>/` as the thing an analyst would actually send:

1. cue: what converged, for how long, under which heuristic;
2. observations and derivations: hard statistics, baselines, geography, coverage, and permutation context;
3. information environment: prevailing public posture and likely amplification/dependency;
4. contextual evidence and counterevidence: cited, dated, both clocks;
5. assessment: competing hypotheses, packet-relative confidence, and what would change the judgement;
6. recommended public-source collection: wait, broaden news/official sources, inspect maps/catalogues, or enter focused review.

The report says: “these public channels changed together; here is the context we collected; here is how I assess it.” It never turns that configuration into a countdown prediction.

### 7. Watch loop, only after phases 1–6 work retrospectively

Daily score the live desk and open notices without a human running `wsd measure` by hand. This is later PoC operations, not a claim that the underlying scientific detector has been validated.

---

## PoC success criteria

1. The same inputs and configuration produce the same observations, derivations, notice, and initial packet.
2. Notice trigger facts are immutable; later collection cannot appear in the trigger calculation.
3. Every notice states what moved, what stayed quiet, what was unavailable, and which sources share an information substrate.
4. The information-environment baseline provides useful context without becoming a hidden extra vote.
5. Posture-dependent collection retrieves relevant public evidence without retroactively changing the trigger, and `surge_review` is usable for contradictory/unclear cases, not only for “worse.”
6. The packet keeps observations, assumptions, heuristics, contextual evidence, and analyst judgement distinct, and can be assessed without the rest of the repository.
7. An analyst can document routine variation, unresolved significance, or elevated concern without the interface pushing toward an alarming conclusion.
8. Notice volume and context-harvest cost remain manageable for a single desk.

---

## What we will not do

- Retune `z`, `k`, persistence, AOIs, or baselines on Ukraine to manufacture a better historical result.
- Call a heuristic notice a statistically validated detector alert.
- Treat sentiment, article count, or repeated headlines as independent corroboration.
- Let triggered contextual sources retroactively strengthen the notice that caused their collection.
- Let the LLM vote in the combiner, alter evidence, open a notice, omit a hypothesis, or own the assessment.
- Treat VIIRS, SAR, CBR, NAVAREA, or any single source as a smoking gun.
- Score `GRC-TUR-2020` as if a freeze existed.
- Apply a source because it is available when it has no geographic or causal relevance, such as US Federal Register volume on a Russia desk.
- Jump to a model because `evidence.json` exists.

---

## Near-term order

The quantitative layer is infrastructure. Spend the next effort on notice → packet → report.

1. Define `notice_v0` (immutable event + workflow), clocks, information-environment snapshot, dependency-graph fields, and collection-posture contracts. Give `heightened` its own policy id.
2. Persist notices from the existing retrospective measurements and make the dashboard an inbox over them. Pin `ukraine2022` collection/measure in `desk_pin.json` (not a scientific freeze).
3. Build **one** deterministic, model-free Ukraine packet (`evidence.json`) from the existing RIMA/official corpus plus an information-environment snapshot. If that packet cannot explain why the notice existed, what was known, what was missing, what context found, what contradicted it, and how an analyst could conclude, stop and fix the packet. Do not add connectors.
4. Replay the notice-to-packet workflow across the other positive and hard-negative cases.
5. Have a human write one complete assessment and report from a packet, sitting with the packet alone.
6. Add one local-model draft (mandatory hypotheses, packet-relative confidence) and compare it with the human-only workflow.
7. Then decide whether additional contextual connectors, a hosted model, or a daily watch loop are worth implementing.
