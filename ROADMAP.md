# Analyst-desk roadmap

**Reviewed 2026-09-05.** Current delivery plan. The local collection/review/brief path is implemented; retrospective product qualification and continuous live orchestration remain outstanding.

## Implementation checkpoint — 2026-09-05

The local path now includes a dedicated secondary-collection entry point with source selection/results, adjustable bounded document research with streamed progress and explicit outcomes, machine proposals, durable analyst review, saved assessment, editorial synthesis/amendment, versioning, sign-off and export. Collection outcomes reach both model drafting and editorial synthesis. Historical records remain snapshots. See [DOCUMENTATION_STATUS.md](DOCUMENTATION_STATUS.md).

Still outstanding: owner-reviewed substantive quality across cases; reliable pre-cutoff retrieval for sources without usable archives; adaptive follow-up; public PDF/imagery handling where required; and the continuous scheduled/event-driven pilot. Passing fixture and browser checks does not close these product qualification gates or validate detector intent claims.

**Product:** an automated public-source intelligence workflow: detect a reason to investigate, do the searching and evidence assembly, develop a draft assessment, incorporate analyst judgement, and produce a decision-ready intelligence brief for review and sending up the chain. Collection cueing is its entry point, not its finished product.

**Working proposition:** states leave public traces of preparations, constraints and possible strategic intent. Assembling those traces across domains may support useful, timely assessments within public-source means. Backtested scenarios must demonstrate where this works, where it fails and where the explanation remains unresolved; the proposition is not an established result.

The intended output has the concise, decision-focused ambition of a President's Daily Brief or UK senior-leadership intelligence assessment. This is a product reference, not a claim to reproduce those institutions' access, methods, coverage or capability, including GCHQ's. All collection uses lawfully and publicly obtainable information, including public subscriptions, commercial data and publicly obtainable API keys. Existing public imagery and reporting are in scope; commissioning military satellites, drone flyovers or privileged intelligence collection is not.

```text
watch → notice → investigate → evidence packet → draft assessment
      → analyst contributions and review → finished intelligence brief
```

| Object | User meaning | Completion boundary |
|---|---|---|
| **Anomaly** | Public channels changed in a way worth examining. | A cue, not an explanation of intent. |
| **Notice** | A persisted investigation entry with immutable trigger facts and mutable workflow. | Opens and tracks the work. |
| **Evidence packet** | Search results developed into attributable findings, passages, counterevidence and gaps. | Research foundations, not the finished brief. |
| **Working assessment** | Proposed key judgements, alternatives, confidence and implications, developed from the evidence and revised with analyst views. | Review decisions materially shape a saved assessment. |
| **Finished intelligence brief** | A concise, versioned assessment for a decision-maker, with a supporting evidence annex. | Ready for sign-off and export; external delivery is a separate authorised action. |

Existing `packet` and `report_v0` names are implementation history: a current packet may display a watch brief, and `report_v0` stores working notes. Neither establishes that the final briefing stage is complete.

**Automation is the destination for the whole production pipeline through the brief.** The analyst should add judgement, challenge conclusions and direct exceptions, rather than routinely find, copy and assemble the foundations. During development, manual detours establish examples, diagnose failures and teach or configure the missing capability. They are not permanent substitutes for unfinished automation. Preparing a brief automatically does not imply automatically distributing it.

Detection of change, collection decisions and assessment of meaning remain separate attributable stages. A model can propose interpretations of intent and revise their relative plausibility from evidence; it cannot turn an inference into an observed fact or rewrite the trigger. Frozen `coincidence_v1` remains unchanged; broader cueing policies are versioned separately.

### Delivery priorities and proportionate validation

This roadmap governs product delivery. Earlier scientific experiment gates govern claims made about those experiments, not permission to build the analyst workflow. The quantitative detector is supporting infrastructure. Prioritise complete investigation-to-brief paths over additional detector experiments, feeds or diagnostic dashboards.

Keep the checks that protect useful intelligence: sources and passages, temporal availability in replay, distinction between fact and inference, counterevidence, source dependencies, recoverable jobs and visible uncertainty. Do not require a red coincidence alert, a permutation threshold, a scientific freeze, perfect source coverage or an open-ended methods programme to finish the product. Missing evidence limits the judgement and prompts a bounded collection task; it must not silently become evidence of absence.

Backtesting assesses timely analytical usefulness, substantive source support, correction effort and the ability to produce a defensible brief, including a justified low-concern or unresolved conclusion. Research metrics support that decision; they do not replace it.

---

## Two operating modes

The desk has two runtimes. They share contracts (observations, both clocks, notices, packets). They do not share a control loop.

| | **Backtest (now)** | **Live (later)** |
|---|---|---|
| Command | `wsd run workflow --scenario <id>` | Not a morning command. The process stays up. |
| What it is | Replay a closed historical window | A sitting watch over calendar time |
| How time moves | The operator starts a job; lookback + score window are harvested, scored, and emitted once | Time passes; sources arrive when they arrive |
| Driver | Batch CLI | **Schedules** (per-source cadence) and **events** (observation arrived, day closed, notice opened, harvest due, source_down) |
| Collect | One full harvest of the declared windows | Incremental append; pull only what that source is due to publish |
| Measure / emit | Once, at the end of the harvest | On the new edge of time, when a day or series updates |
| Notice | Opens from a finished measurement | Opens as coupling appears in the rolling present |
| Packet cutoff | `--replay`: episode end | Live: `now`, `available_at` and `retrieved_at` |

`wsd run workflow` is the **backtest operator path**. It is how we restage `rus2021apr`, `deu2018quiet`, and `usachn2018trade`. It is not a prototype of how a live desk is started each day, and it should not grow into a daemon.

The [analyst loop](#analyst-loop-target) below is the live product. Today we **replay** that loop on frozen windows so a human can sit with the packet. Phase 7 is when the same objects are driven continuously.

Do not confuse “we ran the pipeline without typing five commands” with “the desk is live.” Batch convenience is for backtesting. Live operations are event-driven over time.

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

During development, analyst judgement supplies review, corrections and worked examples throughout the pipeline. The target automates assessment and brief preparation while preserving attribution, uncertainty and an explicit opportunity for analyst contribution and sign-off. Human intervention should become exception-led as capability is demonstrated.

### Two times

Every observation, document, and packet item carries both clocks. A document published at 09:00 and retrieved at 16:00 must not silently appear in a 10:00 replay. A later-corrected source preserves what was knowable at the time.

| Clock | Meaning |
|---|---|
| `evidence_time` | when the underlying thing happened or was published |
| `knowledge_time` | when this desk could reasonably have obtained it (`available_at` / `retrieved_at`) |

This is the same cutoff machinery as the historical work. The packet layer makes it mandatory on qualitative items, not only on time series.

---

## Analyst loop (target)

This is the **live** loop. Backtesting (`wsd run workflow`) replays it on a closed window so the packet can be judged. It does not replace schedules and events.

1. **Scenario / region.** A theatre declares the focal actor, counterparts, AOIs, quantitative sources, contextual sources, and historical windows.
2. **Information-environment baseline.** Maintain the contemporary public context: reporting volume, tone/intensity, originating-source diversity, official posture, narrative concentration, geographic focus, and change over time.
3. **Watch.** Daily observations and derived scores land as sources publish (not because an operator re-ran collect). The desk waits for configured convergence across causal domains rather than staring at raw z-plots.
4. **Notice.** A versioned heuristic opens an **immutable event**: what moved, which domains contributed, what was unknown, what physical or administrative sources did or did not corroborate, and the prevailing information environment. Workflow state (`new` / `acked` / `in_packet` / `closed`) is mutable; the triggering facts are not.
5. **Collection posture.** The notice recommends how much additional public-source collection is justified. The analyst may accept or change it. Posture is effort, not threat.
6. **Context harvest.** Collect bounded, cutoff-safe news/RIMA, official statements, maps, public EO catalogues, and other public sources allowed by the posture. That material is stored outside the trigger namespace.
7. **Evidence packet.** Align hard statistics with cited qualitative evidence, dependencies, counterevidence, missingness, assumptions, and both clocks.
8. **Draft assessment.** Automatically compare hypotheses against the collected evidence, explain changes, state key judgements and uncertainty, and propose implications and next actions.
9. **Analyst contribution.** Persist acceptance, rejection and edits; incorporate the analyst's views into a versioned working assessment without overwriting their writing. Route specific unresolved questions back to bounded collection.
10. **Finished brief.** Generate a concise decision-facing brief and evidence annex from the assessment, carry through material caveats, and expose revision, sign-off and export. Track readiness separately from delivery.

Competing hypotheses (already in `config/interpretation_protocol.yaml`):

- routine variation
- exercise or demonstration
- defensive readiness
- reversible mobilisation
- preparation for overt action
- collection or measurement artifact

The interpretation model is a planned part of the automated investigation, assessment and brief workflow. It may propose and revise judgements about possible intent, with supporting evidence and uncertainty. It may not fabricate observations, alter measurements or deterministic notice triggers, or silently discard competing explanations. Downweighted hypotheses retain their rationale and evidence in the audit record.

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

Current notice actions record workflow intent; requesting more information does not itself execute research. The target connects that action to a scoped, budgeted, resumable public-source collection job, whose findings return to the assessment. Automated orchestration records its actions separately from analyst decisions.

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

The current packet presentation is a watch summary organised around what changed, why it is on the watchlist, what the evidence can and cannot support, competing explanations, and what to collect next. The audit record (series-days, z-scores, reconstructed latency, missingness, shared substrates) is preserved behind that product; it is not the front door.

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

The deterministic packet builder assembles evidence without deciding intent. The interpretation stage proposes support / contradiction / context relationships and analytical significance with source-linked rationale. Those proposals are reviewable and versioned separately from source facts; this separation must enable assessment automation rather than defer it indefinitely.

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
| Collection posture | Persisted notice posture and focused packet jobs exist; a complete posture-budgeted collection controller is not built. |
| Anomaly (coupling / coincidence) | Built. K≥3 episodes are the “look here” in the data. |
| Notice (alert) | Built (`notice_v0`, inbox). Immutable trigger + workflow. |
| Evidence packet / watch summary | Model-free product compiler. Default playback is assessment / watchlist / competing explanations / collection priorities. Analytic state `quiet → anomaly → watch → preparatory_pattern → escalation` describes observable system state, not intent. z-scores and reconstructed-latency machinery sit in an evidence drawer. |
| Report (send up the chain) | Dump-in working assessment on the notice (`report_v0`). Template of what a sitting analyst would cover; human-owned. Not a finished send-up product. |
| Dashboard as **inbox of notices** | Notices are the home surface (alerts). Anomaly charts are a drill-down. |
| On-cue context harvest | Chronology / physical refresh / official pack as packet-scoped jobs. Physical and Official jobs carry a plan (sources, AOIs, admissible dates, discriminators). Official pack harvests **declared UK/US posture**. Physical posture harvests Copernicus S1/S2 catalogue pointers (no scene download, no vote). Standalone Tavily collection uses fixed contextual searches; drafting now has bounded requirement-led research. OSM, RIMA, GKG, direct imagery interpretation and independent geolocation remain unbuilt. |
| Batch backtest CLI | Built (`wsd run workflow`: validate → collect → review → measure → emit). Retrospective only. |
| Continuous live watch | Missing. Phase 7: schedules per source plus event-driven measure/emit. Do not grow the batch command into this. |
| LLM assessment | Sitting desk: bounded `desk_draft_v0` (Tavily + Ollama, no vote). Host CLI delegates to Docker API with streamed stage feedback; model output is validated and structured sections normalised. New drafts use versioned evidence and reference review; original replay-contaminated artefacts remain as audit history. Frozen experiment: `intent_triage_v0` still `enabled: false`. |
| Evidence-building / revised assessment | First engineering slice built: versioned evidence bundle, bounded requirement-led search/archive text retrieval, claim-reference checks, proposed hypothesis changes and source-linked review. Live model/search qualification, semantic/source verification and measured analyst time savings remain outstanding. |

The measurement layer already emits `analyst_action: review_soft_correlation_and_resolve_costly_source_gap`. Notices, collection tasks and human reports now persist parts of that workflow; the complete contextual investigation remains the gap.

### 4 September 2026 checkpoint: engineering progress, not assessment completeness

The owner completed a real `wsd packet draft --replay --no-search` through the Docker API to local Ollama in about 78 seconds. It reused saved Tavily results, wrote a draft with three citation entries, and left human notes and detector votes unchanged. This confirms the execution path, not citation validity, historical admissibility or analyst time saved.

Comparison with the owner's manual 10–12 February assessment found:

- Cue assembly and draft formatting are mostly automated; operational evidence discovery, provenance review and corroboration remain largely manual.
- Six saved Tavily results reached the model. Three were undated official-source hits, including a January 2024 map despite the 12 February 2022 cutoff. `date_unverified` currently does not exclude a hit. Existing artefact wording such as “cutoff-safe” overstates the guarantee; retain those artefacts as the audit record, not a clean replay baseline.
- The packet's collection has ten dated UK/US posture events and seventeen catalogue granules marked knowable, but `_user_payload` supplies official summary notes and search snippets, not the detailed official/physical collection items. Catalogue availability is not imagery interpretation or proof of deployment.
- The prompt holds causal explanations at “realistic possibility” unless the initial packet ranked them. The interpretive layer needs to propose evidence-backed revisions without changing the original trigger or measurement.
- No measured percentage of manual work saved has been established. The manual assessment is a workflow reference, not independently verified ground truth or a target verdict to reproduce.

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

### 4. Use manual walkthroughs to specify and improve automation

Use bounded walkthroughs across `ukraine2022`, `rus2021apr`, `deu2018quiet`, and `usachn2018trade` to establish what useful investigation and assessment require. Run model-assisted development alongside these examples; completing an extensive model-free programme is not a prerequisite.

Ask:

- does the same input produce the same notice and packet?
- does the notice distinguish observation, derivation, heuristic, context, and assessment?
- does additional collection explain, corroborate, contradict, or leave the cue unresolved?
- can an analyst sit with the packet alone — no repo, notebooks, or dashboard internals — and form a judgement?
- can they document “interesting but not significant” without fighting the product?
- is notice volume manageable?

Every manual detour records the missing capability, the analyst's steps and corrections, and a concrete exit check. Convert useful examples into retrieval rules, prompts, evaluation fixtures or, if justified by repeated failures, model training data. Keep development examples separate from qualification cases; a model's prior knowledge of a historical outcome is also a replay limitation, even when its input documents obey the cutoff. Training or fine-tuning is an option, not a prerequisite or a substitute for missing evidence.

Exit the detour when the pipeline reproduces the useful work with reviewable sources and manageable correction effort on another case. Record remaining manual dependencies explicitly; do not call that stage automated.

### 5. Add the draft assessment (LLM)

The sitting desk now has a **bounded** drafter (`desk_draft_v0`): optional requirement-led research against the packet cutoff, then Ollama using server-side `OLLAMA_MODEL` and `OLLAMA_BASE_URL` fills the working-assessment template from a versioned evidence bundle. `--no-search` uses collected records and cached admitted documents, not unverified snippets or a signals-only ablation. The revised admission path is fixture-tested; a fresh owner-run historical assessment remains necessary to qualify it. Frozen `intent_triage_v0` (Ollama, four conditions) stays disabled and separate.

The current implementation is a first investigative slice, not a demonstrated 70–80% reduction in analyst work. The analyst reviews source-linked findings, explicitly chooses whether to use a machine draft, edits and owns the save. Phase 5a tracks the remaining investigation and qualification work.

- Inputs: a versioned snapshot of admitted item-level evidence with explicit exclusions and whole-record context-budget omissions. Exact model input is retained. Legacy collector timestamps remain labelled as collector assertions, not independently verified content versions; uncited model-memory claims are not evidence.
- The model must not invent observations. Proposed evidence significance and hypothesis updates belong in a separate, attributable interpretation layer for analyst review, not in the immutable detector facts.
- Target output schema **requires every hypothesis**, each with the fields below. Current reference review flags missing hypotheses and evidence IDs, and validates revision direction/rationale; it does not yet enforce every analytic field or verify semantic support:

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

### 5a. Evidence-building and analyst labour reduction

**Outcome:** automate finding, organising and comparing evidence so the analyst operates at the top of the information pyramid. Do not optimise for a more alarming conclusion or force the machine to match the manual “send up” decision.

**Implementation checkpoint:** the first engineering slice across the three milestones below is now present, tested with offline fixtures. The original 4 September artefacts above are retained and are not retroactively cleaned or presented as a new result.

| Milestone | Implemented now | Still to qualify / extend |
|---|---|---|
| Trustworthy evidence input | `desk_evidence_v1` includes item-level observations, collector-dated official events, physical observations, catalogue pointers and chronology. Cached search snippets and derived context summaries cannot bypass document-version admission. Exact inputs, hashes, exclusions and budget omissions are persisted. | Legacy official events retain collector provenance, not independent primary-source verification. Catalogue availability can be reconstructed and is not imagery interpretation. Broader source-version qualification remains necessary. |
| Requirement-led investigation | Up to six Tavily queries, including physical corroboration and counterevidence, and six document attempts within a 180-second scheduling budget. Replay uses exact pre-cutoff Wayback captures for HTML/text; failed, empty and uncertain requests are checkpointed, not blindly retried. Normalized requests and content-checksummed results are indexed project-wide, with verified cache hits excluded from new-call counts. Search snippets never enter the model prompt. Admitted documents are stored in full and retrieved as offset-addressed passages (`mxbai-embed-large` via Ollama, lexical fallback). | Public imagery/PDF interpretation, independent geolocation verification, semantic syndication detection, adaptive multi-round investigation and measured search cost are not built. Archive availability and real source relevance have not been live-qualified in this implementation turn. |
| Source-linked analyst review | Model proposals include a compact summary, claims, quotations, evidence IDs, all hypotheses and a collection decision. Missing/invalid references are flagged; Markdown is rendered deterministically rather than generated repeatedly. The UI persists accept/reject/edit/unresolved decisions for findings, hypothesis proposals and next actions against the exact review version; retained material can be merged into the saved assessment. CLI reports bundle and review status. | Quote/ID checks do not establish entailment, source truth, full prose grounding or independence. Instrumented analyst-time comparisons remain future work. Review decisions record analyst judgement rather than certify evidence truth. |

The specification and acceptance work below remain the target; this first slice is not a claim that all acceptance checks or analyst-labour savings have been established.

Implementation / qualification order:

1. **Repair replay admission first.** Undated or version-unverified sources, including official domains, remain leads outside the assessment input until their pre-cutoff content is established. Exclude later maps and revised pages. Separate event, publication, retrieval and archive/version times; a date in a URL is not proof that the retrieved text existed at cutoff. Record exclusion reasons, revalidate cached hits on input, and prevent contaminated summaries from carrying excluded claims forward. Preserve original artefacts and issue a new evidence/input version rather than silently cleaning history. Retain genuinely contemporaneous warnings; forbidden-word matching alone is not temporal verification.
2. **Use the evidence already collected.** Build an addressable input snapshot from dated official events, physical observations, catalogue availability, chronology and admitted search material. Preserve the distinction between catalogue pointers, reported imagery interpretation and directly inspected imagery. Record included/omitted item IDs, truncation and reasons so context-budget selection is visible. Persist the exact model input, hash and source versions.
3. **Investigate collection requirements.** Turn each requirement and discriminator into bounded source/AOI/date-specific searches. Include publicly released commercial imagery reporting, geolocated movement reporting, official statements and contradictory or de-escalatory evidence where relevant. Fetch underlying documents and supporting passages when accessible; snippets are leads, not a claim of full-document review. Follow up unresolved questions within declared query, document, time and cost limits; cache results and record failed/empty searches. All inputs remain publicly obtainable OSINT; registration and API keys are allowed.
4. **Build a claim-and-evidence ledger.** Store claims with stable IDs, source URLs, exact supporting passages/locations, clocks, geographic attribution, provenance and verification status. Link corroboration and contradiction; distinguish independently originated evidence from syndication or repetition. Represent geolocation as reported versus independently checked. Missing FIRMS attribution or unavailable imagery remains unknown, not fabricated detail.
5. **Propose an updated interpretation.** For every retained hypothesis, show supporting and contradicting evidence IDs, dependencies, unknowns and discriminators. Explain what changed since the initial packet and why a hypothesis or confidence should rise, fall or remain unresolved. Permit proposed downweighting of routine variation and other evidence-backed revisions; do not freeze the interpretation at the original packet's likelihoods. Propose wait / collect more / send up / close, without changing detector scores, trigger facts or the human-owned report automatically.
6. **Make review the analyst's main task.** Present the initial cue beside new findings and proposed assessment changes, with passage-level source drill-down and explicit unresolved questions. Let the analyst accept, reject or edit proposals and own escalation/sign-off. Show collection stages, sources examined, gaps, limits reached and failures; support bounded restart/resume without blindly repeating paid search or uncertain generation. Preserve rejected model output as a diagnostic artefact separate from accepted drafts.

Acceptance checks before calling this analyst-work automation:

- A frozen-fixture replay excludes the observed undated/2024 material while retaining legitimate pre-cutoff warnings. Cached hits and derived summaries obey the same admission rules.
- The model receives admitted official/physical evidence or an explicit omission record, not only generic summary notes. Missing imagery is not described as inspected.
- Each material factual assertion and proposed hypothesis change traces to an admitted source passage or declared deterministic observation. Invented or unsupported citations fail validation or remain visibly unresolved.
- An analyst can inspect what was found, what disagrees, what was not found and why the proposed judgement changed without reopening a general web search for every foundation.
- Compare the same research tasks with the manual workflow: active analyst minutes, manual searches/document openings, source corrections, unsupported claims and unresolved gaps. Record model/search elapsed time and cost separately; do not claim a labour-saving percentage until measured.
- Use the Ukraine assessment to define the work to cover (physical posture, official actions, alternative explanations, judgement and next discriminators), not to tune toward a known outcome. Check independent cases, including quiet/contradictory examples and applicable hard negatives, before broader claims.
- Human edits survive retries and navigation; model proposals never change a notice trigger or automatically send a report up the chain.

### 5b. Complete review-to-assessment handoff

**Engineering checkpoint (5 September):** persistent review history, version invalidation, explicit assessment merge, model-backed editorial brief synthesis, sign-off and Markdown/printable HTML export are implemented. Backend lifecycle tests and browser checks cover the path. Owner UI review and substantive qualification remain outstanding. Requirement-specific automatic follow-up collection is still a gap; current collection recommendations use the existing Collection jobs and draft action.

The acceptance contract for this stage is:

- Persist accept / reject / edit / unresolved against scenario, notice, evidence bundle version and stable claim ID, with time, attribution and rationale. Keep original proposals and decision history; changed evidence makes affected decisions visibly stale and requires renewed review.
- Accept retains a finding for assessment, with citations; it does not endorse the overall hypothesis. Reject excludes that proposal from assessment assembly while preserving its history. Retain material counterevidence and disclose unresolved disagreement rather than allowing rejection to erase an inconvenient source fact.
- Show retained findings, rejected proposals, unresolved issues and their effects. Assemble or explicitly merge reviewed findings into the working draft; never silently replace analyst prose. Retrying, navigating or reopening must preserve decisions and edits, and repeated acceptance must not duplicate content.
- Apply the same review mechanism to proposed hypothesis revisions and next actions. A request to collect more creates a specific bounded job and returns its findings for reassessment; acceptance of a finding does not itself launch an unbounded search.
- Expose actual states: research in progress / draft ready / under review / assessment agreed / brief ready. Failed saves, incomplete collection and unresolved material issues are visible. Completion means the persisted assessment and subsequent brief reflect the decisions, not just the button label.

### 6. Produce the finished intelligence brief

Generate the brief from the versioned working assessment and its evidence ledger, under `scenarios/<id>/reports/<report-id>/`. Working notes alone do not complete this phase. Preparation is automated; the analyst can add views, revise and sign off before export or sending up the chain.

The main brief leads with the decision-maker's question and the assessed answer:

1. title, region, assessment date and information cutoff;
2. concise key judgements, with likelihood and confidence distinguished and reasons for uncertainty;
3. what changed, why it matters, and implications within the evidence's limits;
4. strongest supporting evidence, material counterevidence and credible alternative explanations;
5. outlook or scenarios where supportable, indicators that would change the judgement, and priority remaining collection;
6. assessment status, analyst contributions and review/sign-off record.

Keep detector diagnostics, detailed chronology, sources, passages, source dependencies, search failures and collection costs in an accessible evidence annex. The brief must stand alone without the dashboard or repository. An unresolved or low-concern assessment is a valid finished product; neither an alarming conclusion nor an exact event prediction is required.

Acceptance: generate a readable export from the agreed assessment; verify that key judgements and citations match it, rejected proposals have not resurfaced, caveats survive summarisation, and analyst amendments persist. Regeneration creates a new version and invalidates prior sign-off rather than silently changing an approved brief. Preserve machine proposals, working assessment and final brief separately. Delivery status is separate from readiness; do not imply that export sent anything.

### 7. Continuous watch, only after phases 1–6 work retrospectively

The live desk is not `wsd run workflow` on a cron. It is a process that stays up and is driven by **time**.

- **Schedules** per source: weekday CBR prints, next-day Wikimedia, 3-day VIIRS reconstructed latency, FIRMS daily, NAVAREA as published. Each source is pulled when it is due, not when a scenario job starts.
- **Events** over time: observation arrived, expected day closed missing, source_down, coupling episode opened, notice workflow asked for context, posture harvest due. Measure and emit run on those edges.
- **Incremental corpus:** append new days; do not re-harvest the 120-day lookback unless a revision is required.
- **Rolling present:** notices open as coupling appears, not from a finished whole-window measurement. Packet cutoff is `now`.
- Collection jobs already have the live shape (Physical / Official on a notice). The missing piece is the watch itself, not more batch stages.

Move to a bounded live pilot after the retrospective readiness gate below is met. Carry the same evidence, assessment and brief contracts into scheduled/event-driven orchestration, with per-source budgets, retries, source-health handling, resumable jobs and visible failures. First run with analyst review of every brief; reduce manual interventions only where recorded performance supports it. Keep the batch CLI as the backtest tool. Scientific detector validation remains a separate claim.

---

## Retrospective readiness gate for a live pilot

Before qualification, record the scenario set, cutoffs, pipeline/model versions, collection budgets and acceptable limits for analyst effort, unsupported claims, missed material evidence and notice burden. The owner sets practical limits before inspecting qualification outputs; no arbitrary universal accuracy or labour-saving percentage is assumed.

Complete the whole path through an exported brief on a development case, then on separate positive, quiet and contradictory/hard-negative cases. Judge against what was publicly knowable at the cutoff, not simply whether the eventual outcome was guessed. Record timeliness, evidence coverage, substantive errors, alternative explanations, active analyst minutes, manual interventions, elapsed time and cost. Check for retrospective knowledge leaking through model prose as well as through sources.

Readiness requires source-supported material judgements, visible unresolved gaps, durable review and edits, a faithful finished brief, recoverable bounded execution, and acceptable correction effort and notice volume against those predeclared limits. Document residual manual steps and the owner's go/no-go decision. Failed cases drive specific repairs and rechecks; passing this gate authorises a bounded live pilot, not a claim of intelligence-service equivalence or universal predictive validity.

## PoC success criteria

1. The same inputs and configuration produce the same observations, derivations, notice, and initial packet.
2. Notice trigger facts are immutable; later collection cannot appear in the trigger calculation.
3. Every notice states what moved, what stayed quiet, what was unavailable, and which sources share an information substrate.
4. The information-environment baseline provides useful context without becoming a hidden extra vote.
5. Posture-dependent collection retrieves relevant public evidence without retroactively changing the trigger, and `surge_review` is usable for contradictory/unclear cases, not only for “worse.”
6. The packet keeps observations, assumptions, heuristics, contextual evidence, and analyst judgement distinct, and can be assessed without the rest of the repository.
7. An analyst can document routine variation, unresolved significance, or elevated concern without the interface pushing toward an alarming conclusion.
8. Notice volume and context-harvest cost remain manageable for a single desk.
9. The evidence-building workflow reduces measured analyst collection/assembly effort while retaining source traceability and surfacing contradictions; fluency and agreement with a retrospective conclusion are not substitutes.
10. Review decisions survive reopening and materially shape the assessment and brief; no action ends at a decorative status label.
11. The pipeline produces a standalone, versioned intelligence brief with faithful citations, analyst contributions and a clear readiness/sign-off state.
12. Each manual detour has a recorded automation gap and exit check; the retrospective gate leads to a bounded live pilot rather than an indefinite research programme.

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
- Treat fluent model prose as completion when investigation, durable review or the finished brief is missing.
- Treat `wsd run workflow` (or a cron of it) as the live desk. Batch is backtesting; live is continuous, scheduled, and event-driven.

---

## UX review and delivery backlog — 2026-09-07

**Review status:** completed a read-only walkthrough of the running React desk at `localhost:5173` (notice overview, assessment/brief entry, Operations and Scenarios), including desktop visual inspection at 1280 × 720, and inspected the command, artefact, collection, review, export and styling implementations. Findings below distinguish observed behaviour from source-inspected gaps and further validation. No collection, model generation, sign-off or destructive action was executed. This is a heuristic UX review, not a completed accessibility audit or an observed analyst usability study. Item status and verification are recorded in the checkpoint table below.

**Overall finding:** substantial functionality exists, but the user still has to understand the implementation to connect configuration, execution, evidence, assessment and a finished brief. Prioritise clear action outcomes and continuity before adding more screens. Existing assessment previews, latest-brief rendering, artefact tables/plots, local draft retention, review persistence and generation-stage feedback are foundations to extend, not missing features to rebuild.

Priority: **P1** prevents a coherent or trustworthy task flow; **P2** materially improves clarity, efficiency or presentation. These priorities concern product usability, not detector severity.

### Implementation checkpoints

Branch: `codex/ux-fixes`. Each item is implemented, tested and committed separately. “Done” records engineering acceptance; owner usability qualification remains separate. The backlog descriptions below retain the original findings for traceability.

| Item | Status | Verification / remaining limits |
|---|---|---|
| UX-N01 | Done | Direct Intelligence brief destination, state-aware overview journey and prerequisite guidance. 17 frontend tests and production build passed; browser verified empty assessment guidance and direct brief navigation. First-time owner walkthrough remains to qualify ease of use. |
| UX-N05 | Done | Watch packet availability no longer implies review readiness; overview separately shows proposal review, assessment and brief states, including stale precedence. Cue interpretation and source/purpose labels clarified. 18 frontend tests and build passed; browser verified packet-only notice has no proposals/assessment/brief. |
| UX-F01 | Done | Backtest run-plan UI, individual stage ranges, source/options selection, scenario creation, stale-plan rejection and linked command results. 10 operator/workflow fixture tests passed (synthetic collection only); production build and browser plan preview passed. Durable history/reconnect is F02/F07; realtime remains phase 7. Concurrent external CLI changes during execution remain unsupported: do not run CLI and UI mutations together. |
| UX-F02 | Done | Atomic command receipts for backtests, notice emission and packet builds; scenario-filtered history, exact result links, reconnect by saved job ID and raw details. Four operator tests include restart, failure isolation and non-regression of terminal state; frontend build passed. Older unrecorded commands remain artefacts, not invented history. Interrupted prior sessions show unknown, never auto-retry. |
| UX-F03 | Done | Operations now names packet construction correctly; overview routes by actual readiness (N01), and evidence tools link to the direct brief destination. Build and 18 frontend tests passed; browser verified packet-building label. |
| UX-F04 | Done | Selected-version reading, comparison with latest, annex reading, saved-assessment PDF preview and exact selected-version PDF preview without download. Markdown artefacts/retained findings render an inert readable subset with originals retained. 18 tests/build passed; browser opened retained v7, compared with v8 and loaded v7 PDF preview. PDF rendering requires browser PDF support (separate-tab fallback provided). |
| UX-F05 | Done | Notice/scenario context follows navigation; backtest initial scenario follows current context; scenario artefact tab/path/filter/run/page position are URL-backed and clear on scenario changes. Explicit missing scenarios no longer silently select another. 19 tests/build passed; browser verified Ukraine notice → Ukraine artefacts and filter/path retention after reload. |
| UX-F06 | Done | Review questions/discriminators create bounded follow-up jobs pinned to review version, packet and cutoff; question/source preference passes into the actual research plan and receipt. Completion opens new findings for renewed review, preserving saved assessment. 63 follow-up/draft/workflow tests passed with mocked generation; browser inspected current questions and budgets without launching research. Source preferences are query terms, not hard domain filters; automatic multi-round investigation remains future work. |
| UX-F07 | Done | UI research/secondary collection use persisted reconnectable jobs and request IDs; duplicate requests reuse receipts. Follow-up shares the launcher; brief preparation is recorded. Backtests checkpoint completed stages and support stop-after-stage; history offers explicit new plans, never automatic re-execution. 38 targeted tests and build passed, including duplicate request/restart and stage-boundary stop. Prior API sessions remain unknown until outputs are inspected; in-flight source/model cancellation and concurrent external CLI mutations are unsupported and disclosed. |
| UX-F08 | Done | Human-readable artefact titles retain paths; source reader shows recorded text, source-version link, clocks, dependencies and original data; review timeline shows actions, reasons, wording and current/earlier review status. 19 frontend tests/build passed; browser inspected the 88-event timeline and a retained source document without leaving the desk. Source text is displayed as recorded; publication boilerplate is not silently removed. |

### 1. Functional gaps

| ID / priority | Finding and evidence | Required change and acceptance |
|---|---|---|
| UX-F01 · P1 | **Incomplete command coverage.** Operations exposes notice emission and packet building. Scenarios edits/validates existing contracts, but does not provide the full corpus collection → review → measurement → notice workflow. CLI functions remain necessary for ordinary replay execution. The Operations claim that day-to-day work is buttons overstates coverage. Evidence: `OperationsView.jsx`, `ScenariosView.jsx`, `src/wsf/cli.py`. | Inventory each supported CLI operation against its UI entry point, parameters, prerequisites, output and recovery path. Provide a bounded replay runner and stage actions for normal operator tasks, plus scenario creation. Explicitly identify maintenance/developer-only commands rather than copying every CLI flag into the desk. Acceptance: configure a scenario, run the supported retrospective path and open its results without a terminal; show mode, cutoff, source selection and limits before execution. |
| UX-F02 · P1 | **Command results lack a durable, navigable home.** Emit/build responses are assigned to the single in-memory `opsLog` and rendered as raw JSON under “Last run”; reloading loses that UI record. Existing collection and model progress are separate mechanisms. Evidence: `App.jsx`, `OperationsView.jsx`. | Add a persisted job history scoped to scenario/notice/run, showing requested action and inputs, start/end/elapsed time, actual stage, outcome, warnings, errors and output links. Present a readable summary first, with raw logs/details available. Acceptance: after navigation and reload, reopen a completed or failed job and go directly to the exact measurement, notice, evidence packet or draft it produced; never display a previous success as the latest failed action's output. |
| UX-F03 · P1 | **Action labels promise the wrong product or readiness.** In the live walkthrough, Operations “Build brief” assembles a packet. “Open the intelligence brief and PDF” from an “Evidence ready” notice led to “Write and save an assessment first.” Evidence: `OperationsView.jsx`, `NoticesView.jsx`, `AnalystWorkflow.jsx`. | Use “Build watch packet” for packet creation and “Prepare intelligence brief” for editorial synthesis. Make the overview action state-aware: start assessment, continue review, prepare brief, or open version. Distinguish evidence available, assessment saved, draft brief ready, stale and signed off. Acceptance: every primary action names its actual result and lands on the next usable step with unmet prerequisites explained. |
| UX-F04 · P1 | **Preview support is inconsistent, rather than absent.** Assessment and latest brief have inline views; retained findings and annex use preformatted text. Older brief versions offer Download and Remove but no in-app Open/Compare. Markdown artefacts open as raw source, and current screen views do not establish final PDF pagination. Evidence: `ReportView.jsx`, `AnalystWorkflow.jsx`, `ArtifactsView.jsx`. | Offer explicit Preview / Edit / Download actions where applicable. Open any retained brief version and its annex in the desk; add version comparison and an export-layout preview for the selected version. Render Markdown safely while retaining raw source. Acceptance: inspect assessment, current/prior brief and annex without downloading; selected version, draft/sign-off/stale status and preview truncation remain visible; exporting uses that same version. |
| UX-F05 · P1 | **Context does not travel consistently across surfaces.** Moving from the Russia notice/Operations to Scenarios in the walkthrough selected `deu2018quiet`. Scenario selection, notice selection and measurement selection have separate state. Operations' notice selector invokes navigation back to Desk. Evidence: live navigation, `App.jsx`, `ScenariosView.jsx`. | Carry scenario, notice and run context through explicit “Open scenario”, “Open outputs” and “Open evidence” links. Make deliberate context switches visible; choosing an Operations input must not unexpectedly leave the form. Preserve artefact path, filters and pagination in navigation where useful. Acceptance: move from a notice to its configuration, job and evidence and back without silently inspecting a different scenario or losing position. |
| UX-F06 · P1 | **Follow-up intent remains separate from execution.** Notice actions and review recommendations do not provide a complete requirement-specific collection handoff. Generic bounded collection/drafting controls exist, but the analyst must translate the unresolved question into the next run. Evidence: notice workflow contract above and collection/review components. | Turn an accepted collection requirement into a prefilled, bounded job with source/date/AOI scope and the originating question; return findings to the same assessment with an explicit changed-evidence state. Acceptance: the analyst can trace request → job → findings → renewed review without manual copying; recording a request must never look like completed research. Links to phase 5b rather than a separate competing implementation. |
| UX-F07 · P1 | **Recovery controls are fragmented.** Progress exists, but there is no common job-level resume/reconnect/cancel experience across ordinary operations, research and brief preparation. Frontend busy/error state alone does not explain whether backend work continues after a disconnect. Evidence: `App.jsx`, `OperationsView.jsx`, `AnalystWorkflow.jsx`. | Give each job an identity and explicit running/completed/failed/interrupted/unknown state. Reconnect to ongoing work; expose safe retry/resume only where supported, and explain cancellation boundaries. Acceptance: a lost connection does not trigger duplicate paid search or generation; partial outputs and failure reasons remain inspectable. Use real stages and elapsed time, never an invented model completion percentage. |
| UX-F08 · P2 | **Evidence inspection still falls back to implementation formats.** Artefact browsing provides useful filters, coverage and record previews, but filenames/paths dominate navigation, nested data often becomes JSON, and review history is raw JSON. Evidence: `ArtifactsView.jsx`, `AnalystWorkflow.jsx`. | Add human-readable output titles, stage/outcome summaries and a structured review timeline; retain IDs and originals as details. Connect findings to available source passages/provenance in a contextual reader. Acceptance: answer “what was found, what failed, what changed and what supports this judgement?” within the desk, with clear partial-preview and missing-source states. |

### 2. Non-functional UX issues

| ID / priority | Finding and evidence | Required change and acceptance |
|---|---|---|
| UX-N01 · P1 | **Workflow hierarchy is unclear.** Overview, Evidence, Collection and Notes & assessment sit above a second four-step workflow; the final brief is nested inside Notes. The overview leads with a long generated watch product while the finished-product path can be empty. Evidence: live desk/brief walkthrough. | Establish a visible investigation journey with current stage, completed work, blockers and one next action. Make the finished brief a clearly named destination. Preserve free navigation for experienced analysts. Acceptance: a first-time reviewer can identify what exists, what remains and how to reach a finished brief without explanation from the developer. |
| UX-N02 · P2 | **Wasted vertical space and inconsistent margins.** At 1280 × 720, Operations repeats its heading, gives health and an idle harvest large full-width cards, and pushes packet building below the fold. The notice view combines a fixed header, permanent inbox, callout, explanatory row and divider before substantive content. Evidence: desktop screenshots; layout rules in `styles.css`. | Condense idle health into a status strip, group execution controls by stage, standardise spacing and align content/action edges. Keep explanatory detail progressively disclosed. Acceptance: at the reviewed viewport, the main task and status are visible without scrolling past idle panels; long reading content retains comfortable line length rather than simply stretching to fill space. |
| UX-N03 · P2 | **Reading and working layouts compete.** A permanent inbox reduces document width; assessment is capped at `90ch`, while brief/annex readers have their own `38rem` scrolling limits inside the scrolling notice body. Evidence: `styles.css`; nested scrolling visible on Desk. | Provide a focus/reading mode with collapsible inbox, a consistent document gutter and a deliberate primary scroll container. Use wider space for evidence comparison and tables, narrower space for prose. Acceptance: review a long brief and annex without competing vertical scroll areas; return to the same inbox selection and reading position. Validate laptop, wide desktop and narrow layouts. |
| UX-N04 · P2 | **Branding and control styling lack coherence.** The WSD identity is present, but the browser title still says “Notices — collection cueing desk”, Operations uses duplicate headings, and the overview's brief CTA appeared as a generic grey button beside custom controls. Mobile CSS hides the brand entirely. Evidence: live title/screenshots, `App.jsx`, `styles.css`. | Define one product name, restrained identity, type scale, colour and spacing tokens, and consistent primary/secondary controls across desk and previews. Keep a compact identity on narrow screens and align exported-document identity without implying institutional affiliation. Acceptance: navigation, buttons, headings, states and documents look like one product in both colour schemes. |
| UX-N05 · P1 | **Terminology increases cognitive load and can overstate meaning.** “Generated brief”, watch packet and intelligence brief overlap; “Evidence ready” can coexist with zero proposals and no assessment. Internal labels such as `development_showcase`, source IDs and measurement hashes appear directly in controls. Evidence: live UI and scenario/operations components. | Use task language and separate collection, review and brief readiness. Explain technical identifiers on demand; retain them for audit. Keep replay mode/cutoff and cue-versus-assessment status prominent. Acceptance: users can distinguish available evidence from reviewed evidence and a signed brief, without reading repository documentation. |
| UX-N06 · P2 | **Accessibility and responsive behaviour need explicit qualification.** Existing labels, status roles and breakpoints are useful. However, custom menus, dense tabs, small metadata, chart interaction and nested scroll regions need keyboard/screen-reader and narrow-screen verification; visual inspection alone does not establish contrast compliance. Evidence: component and CSS inspection; not asserted as confirmed failures. | Audit keyboard order, visible focus, menu opening/closing and focus return, tab semantics, error announcements, contrast, zoom, touch targets and non-colour chart/state descriptions. Acceptance: complete the core review/preview journey keyboard-only and at 200% zoom; narrow layouts have no page-wide horizontal overflow, with intentional table scrolling clearly bounded. Record actual failures and fixes. |
| UX-N07 · P2 | **Freshness language is too broad.** “Up to date” is driven by notice polling while catalog/result/health refreshes can fail independently. “No live collection running” describes a job state without clearly stating whether the desk is replaying history or continuously watching. Evidence: `App.jsx`, `OperationsView.jsx`. | Show last successful refresh and degraded resource states, separately from job activity and operating mode. Acceptance: a failed measurement or health refresh cannot leave an unqualified workspace-wide “Up to date”; idle replay must not imply an active continuous watch. |

### 3. Command-level UX: backtesting execution

**Scope clarification:** the initial walkthrough identified UI coverage gaps but did not exercise collection or measurement. This follow-up reviews the command definitions and orchestration in [cli.py](src/wsf/cli.py), [workflow.py](src/wsf/workflow.py), [measure.py](src/wsf/measure.py) and [agent.py](src/wsf/agent.py). The requirements below are source-informed design work, not verification of executed jobs. No network collection or model work was run.

The backtesting workspace should make this journey explicit:

```text
choose scenario and historical windows → validate configuration
→ collect a corpus revision → inspect coverage and review gaps
→ repair gaps if needed → measure the chosen revision
→ inspect results, including a valid zero-notice outcome → emit/open notices
→ build watch packet → investigate → review → assessment → preview brief
```

The user needs both a bounded “Run backtest” action and individual stage controls. Before execution, show a readable run plan with scenario/configuration version, historical windows, evidence cutoff, selected sources, existing inputs being reused, stages to run and expected outputs. Separate three independent concepts: **historical replay versus realtime watch**, **real-source versus synthetic data**, and **exploratory versus frozen measurement status**. A real-source harvest of 2022 data is still backtesting. Freeze is a measurement qualification control, not a prerequisite for all analyst product work.

| Command / current behaviour | Required controls and prerequisites | Visible output, next step and recovery |
|---|---|---|
| `wsd doctor`; `scenario create`, `validate`, `status` | Provide source/configuration readiness and a scenario creation path. Creation currently produces an incomplete template; explain required fields and validate them before collection. Distinguish missing configuration from actual source availability: offline validation does not prove that a remote service will respond. | Show field-level errors, configured-source readiness, scenario hash and active collection/review/measurement IDs with links. Offer “Complete configuration” or “Collect” according to state. Keep setup checks distinct from a running watch's health. |
| `wsd corpus collect` | Show scenario windows/AOIs, source subset (`--only`), optional previous gap review (`--focus`), real-source/synthetic mode, and source concurrency (`--source-workers`, advanced). Explain that this creates a new corpus revision; a source subset must not look like complete coverage. Resolve a focus file to its scenario/review in the UI rather than requiring a filesystem path. | Show collection ID, per-source/window progress, elapsed time, source failures, retrieved coverage and links to manifest, observations and provenance. Finish at “Review collection”, not simply “Success”. A focused recollection must show what it attempts to repair and which previous inputs it retains or replaces. Do not equate selecting a source or ending a job with obtaining usable evidence. |
| `wsd corpus review` | Identify the exact active corpus revision and applicable gates before running. Label `--mock-model` as rehearsal. Explain the difference between deterministic corpus gates, semantic review status and later analyst review of findings; “review” is currently overloaded. | Show decision, gate reasons, source/window gaps and `missing.json` in readable form. A `no_go` outcome leads to a prefilled focused recollection, followed by a new review. Preserve the original review and distinguish “review completed with gaps” from execution failure. Do not label a prepared or mocked semantic result as completed substantive model review. |
| `wsd measure` | Show the collection revision that will be scored, configuration and protocol, active series and historical baseline/score windows. Standalone measurement defaults to non-exploratory, whereas `run workflow` defaults to exploratory: expose this choice consistently and explain eligibility. Block missing/ineligible inputs with a specific recovery action. | Show measurement ID, collection lineage, `measurement_mode`, `scientific_result`, coverage/unknowns and separate protocol, exploratory, amber and rhythm results. Link directly to charts, diagnostics and raw summary. “Zero episodes” is a valid completed outcome, not a failed run. Remeasurement creates a distinguishable result; comparison must show changed inputs/configuration rather than imply like-for-like results. |
| `wsd notice emit` / `notice list` | Select the exact measurement and notice policy; avoid silently using whichever measurement became active most recently. Explain that emission persists investigation cues, not final intelligence judgements. | Open the resulting notices, report none when applicable, and distinguish newly created from already-existing notices where the backend can support that accounting. Repeating emission must not appear to produce new evidence or rewrite immutable triggers. Preserve the selected run when returning to results. |
| `wsd run workflow` | Expose start/end stages (`--from`, `--through`), source subset, focus, concurrency and exploratory/rehearsal settings through a readable plan. Explain reused stage inputs. Validation still runs when starting at a later stage. Prevent a new active revision from silently changing the inputs between planning and execution; pin/revalidate identities as part of job implementation. | Show a stage timeline and linked outputs for each completed stage. Existing `stopped_no_go` is a blocked data-quality outcome; rehearsal stops before measurement. “Resume from review” means starting another bounded invocation from retained inputs, not proof of durable job resumption. The current pipeline does not freeze, prune, call Ollama or build packets: label completion “Replay through notice emission complete”, with a next action into investigation. |
| `wsd scenario freeze`, `init-run`, `corpus prune-viirs` | Keep qualification and maintenance outside the main investigation action row. Freeze requires an accepted matching corpus; rehearsal permission must be explicit. `init-run` belongs to reproducibility setup. Cache pruning needs an impact summary and must respect the active-harvest restriction. | Show frozen revision and qualification status, or manifest identity. For pruning, show cache scope, retained outputs and space affected; do not disguise it as harmless job cleanup or automatically invoke `--force`. These commands should not be hidden prerequisites that stall ordinary exploratory assessment. |
| `wsd packet build`, `collect`, `draft`, `report`, `pdf` | Distinguish watch-packet construction, secondary context collection, model drafting, saved analyst assessment and document export. Carry the notice, cutoff and packet version forward; show source/model budgets before relevant work. | Connect to UX-F03/F04/F06: preview existing products without regeneration, show collection/drafting outcomes, retain analyst edits and offer the correct next review step. Completing `run workflow` does not complete this downstream path. |

**P1 acceptance for UX-F01/F02/F07:** using retained fixtures or an explicitly authorised bounded run, perform collection → review → measurement without a terminal, inspect each command's output in place, and recover from one source failure and one review `no_go`. Navigate away/reload during a job and reconnect to its recorded state. Verify that a measurement started after a configuration or active-corpus change either uses the explicitly selected snapshot or requests an updated plan; it must not silently score a different input. Record precise eligibility errors rather than weakening measurement gates to make a button work.

### 4. Realtime UX: continuous watch and exceptions

**Current implementation boundary:** `wsd agent run` presently checks the database and writes an `idle` heartbeat. It does not execute a collection/measurement queue, implement source schedules or maintain a rolling watch. Therefore “Agent idle/healthy” proves neither watch coverage nor end-to-end operation. Realtime controls below are requirements for phase 7, not claims that this runtime exists. Build them with the corresponding orchestration, after the retrospective readiness gate; do not present decorative Start/Pause controls or turn the batch workflow into a scheduled whole-window recollection.

| UX concern | Backtesting mode | Realtime watch target |
|---|---|---|
| Entry and primary action | Choose a historical scenario/run; “Run backtest” executes a finite plan. | Choose a configured watch; “Start watch” activates its source schedules and event processing. Display prerequisites and configuration version first. |
| Time and coverage | Fixed lookback/score windows, replay cutoff and retained source versions. | Rolling evidence/knowledge times, per-source latest usable observation, last successful retrieval, next expected publication/poll and measurement watermark. Show timezone and explain legitimate publication latency. |
| Collection | Whole declared windows or a focused gap repair, with a finite completion state. | Incremental arrivals at source-specific cadence. The watch remains active between jobs; “waiting for next source publication” is distinct from paused, stalled, disconnected or broken. |
| Measurement | Explicit scoring of a selected corpus revision with frozen/exploratory status. | Automatic scoring when the required observation/day-close event arrives, with coverage and last successful scoring time. Version late/corrected inputs; show resulting revised analysis without rewriting prior notice triggers. |
| Progress and outputs | Stage progress, elapsed time, completed/blocked/failed outcome and run artefacts. | Persistent watch health plus individual job histories, backlog/lag and last/next activities. Never give the continuous watch a completion percentage; expose bounded job progress separately. |
| Normal user work | Inspect run outputs and compare historical cases. | Review an exception/notice queue grouped by watch, with new/changed items, age, owner and unresolved collection needs. Successful routine polls need no analyst intervention. |
| Pause, stop and restart | Cancel a bounded job only where supported; show partial outputs and eligible rerun stages. | Specify whether Pause stops new scheduling, drains current jobs or requests cancellation. Show effective state. On resume, preview missed intervals and a bounded catch-up plan; retain checkpoints and avoid duplicate jobs/notices. |
| Configuration changes | Save a new configuration for subsequent runs; retained results keep their originals. | Show which future jobs use the revision, whether baseline warm-up/backfill is needed and when it becomes effective. Current assessments and signed briefs retain their input versions. |
| Alerting and failure | Display a failed stage and its repair path within the selected run. | Distinguish source unavailable, expected delay, stale heartbeat, queue backlog and processing failure. Notify on meaningful degradation, new investigation needs or required action; deduplicate repeated outage alerts and show recovery. |

The realtime landing view should answer, without opening logs: **what is being watched; is it actually operating; what information is late or missing; when was it last measured; and what needs my judgement?** Use a compact watch summary, a per-source freshness/coverage table, an exception queue and a linked activity history. Keep raw logs and technical IDs available in details. Offer a read-only preview of watch scope, schedules, budgets and expected next actions before activation.

Separate **worker heartbeat**, **scheduler state**, **source freshness**, **measurement freshness**, **investigation progress** and **brief readiness**. A green database indicator cannot stand in for these. Carry the operating-mode label throughout navigation and preview/export metadata; use “real-source harvest” rather than “live” when describing historical collection. Manual “Collect now” or “Recalculate” overrides must state their scope and resulting job/version, and must not reset or duplicate the normal schedule.

**Phase 7 acceptance:** use a controlled clock and source fixtures to demonstrate scheduled arrival, expected delay, outage/recovery, late correction, worker restart and pause/resume with catch-up. Confirm that ordinary idle periods look healthy, missed data cannot appear current, retries do not duplicate work, prior notices remain immutable and new findings return to the correct assessment. Verify that replay and watch histories remain distinguishable when both use the same region. Realtime delivery remains open until these controls operate against real persisted orchestration; retain the existing owner-reviewed pilot gate.

### UX delivery order and closure checks

1. **Complete the operator loop:** UX-F01–F03, F05 and F07, using the command-level backtesting contract above; establish command coverage, durable outputs, honest naming, context and recovery. Coordinate requirement-driven follow-up (F06) with phase 5b. Carry the separate realtime UX requirements into phase 7 rather than implying that batch controls implement a watch.
2. **Make review and preview the normal path:** UX-F04/F08 and UX-N01/N05; connect evidence, retained findings, assessment and all brief versions with clear readiness and readable previews.
3. **Apply a coherent presentation system:** UX-N02–N04; correct spacing, density, document reading and branding across the existing path. Include N06 accessibility checks throughout implementation and N07 truthful status in the first slice.
4. **Validate the journey:** use retained fixtures for empty, partial, failed, stale, unsaved, draft and signed-off states. Walk scenario → execution → output → evidence review → saved assessment → brief preview → optional download, including reload and back navigation. Check 1280 × 720, wide desktop, a narrow viewport, keyboard-only operation and zoom. Record task completion, wrong turns, manual file/terminal detours and correction effort; do not claim measured usability improvement from this heuristic review alone.

Close each item only with the relevant visible behaviour and acceptance evidence. A new button, successful API response or passing build alone does not close a workflow gap. This section records review findings and planned work; it does not mark UX implementation complete.

---

## Near-term order

Finish one complete retrospective investigation-to-brief path before expanding breadth. The existing research and draft slice is infrastructure toward that outcome, not a completed feature.

1. Address the P1 gaps in the [UX review and delivery backlog](#ux-review-and-delivery-backlog--2026-09-07), then owner-review the implemented phase 5b/6 UI path: decisions, explicit draft integration, saved assessment, briefing version, sign-off, preview and export. Fix usability or substantive assembly gaps found in that walkthrough.
2. In the same delivery slice, qualify the existing bounded research and draft against actual admitted public sources. Fix concrete source, passage, counterevidence and replay gaps that prevent a defensible assessment; do not wait for perfect coverage of every possible feed.
3. Qualify the generated brief against the agreed assessment: key judgements, alternatives, citations, caveats and readability. Editorial synthesis, amendment and export exist; substantive adequacy still requires analyst review.
4. Use a bounded manual comparison to identify remaining heavy lifting. Record and automate the highest-value missing steps, including adaptive follow-up or public PDF/imagery handling when the case needs them. Measure correction effort as well as time saved.
5. Run the declared retrospective readiness gate on independent cases. Complete baseline, posture and dependency support to the extent needed for those cases, with outstanding limitations explicit.
6. On a documented go decision, implement and qualify the continuous live pilot: schedules, events, incremental collection and automatic assessment/brief preparation with initial analyst review. External dissemination remains a separate action.

Model training, hosted models, vector retrieval, additional feeds and further statistical experiments are options justified by observed delivery gaps. None replaces completing this vertical workflow, and none is a standing prerequisite for it.
