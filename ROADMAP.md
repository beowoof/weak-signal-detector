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

The quantitative detector is largely finished infrastructure. The next research object is an **evidence-building workflow that reduces analyst labour**, not merely a more fluent draft. The human should review evidence, challenge interpretations and own the decision, rather than manually locate and assemble the foundations. See [phase 5a](#5a-evidence-building-and-analyst-labour-reduction-next-not-built).

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

This is the **live** loop. Backtesting (`wsd run workflow`) replays it on a closed window so the packet can be judged. It does not replace schedules and events.

1. **Scenario / region.** A theatre declares the focal actor, counterparts, AOIs, quantitative sources, contextual sources, and historical windows.
2. **Information-environment baseline.** Maintain the contemporary public context: reporting volume, tone/intensity, originating-source diversity, official posture, narrative concentration, geographic focus, and change over time.
3. **Watch.** Daily observations and derived scores land as sources publish (not because an operator re-ran collect). The desk waits for configured convergence across causal domains rather than staring at raw z-plots.
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
| Collection posture | Persisted notice posture and focused packet jobs exist; a complete posture-budgeted collection controller is not built. |
| Anomaly (coupling / coincidence) | Built. K≥3 episodes are the “look here” in the data. |
| Notice (alert) | Built (`notice_v0`, inbox). Immutable trigger + workflow. |
| Packet (brief) | Model-free product compiler. Default playback is assessment / watchlist / competing explanations / collection priorities. Analytic state `quiet → anomaly → watch → preparatory_pattern → escalation` describes observable system state, not intent. z-scores and reconstructed-latency machinery sit in an evidence drawer. |
| Report (send up the chain) | Dump-in working assessment on the notice (`report_v0`). Template of what a sitting analyst would cover; human-owned. Not a finished send-up product. |
| Dashboard as **inbox of notices** | Notices are the home surface (alerts). Anomaly charts are a drill-down. |
| On-cue context harvest | Chronology / physical refresh / official pack as packet-scoped jobs. Physical and Official jobs carry a plan (sources, AOIs, admissible dates, discriminators). Official pack harvests **declared UK/US posture**. Physical posture harvests Copernicus S1/S2 catalogue pointers (no scene download, no vote). Tavily adds up to six fixed contextual searches; OSM, RIMA, GKG and investigation of public imagery/movement reporting remain unbuilt. |
| Batch backtest CLI | Built (`wsd run workflow`: validate → collect → review → measure → emit). Retrospective only. |
| Continuous live watch | Missing. Phase 7: schedules per source plus event-driven measure/emit. Do not grow the batch command into this. |
| LLM assessment | Sitting desk: bounded `desk_draft_v0` (Tavily + Ollama, no vote). Host CLI delegates to Docker API with streamed stage feedback; model output is validated and structured sections normalised. Replay filtering has a known admission defect (below). Frozen experiment: `intent_triage_v0` still `enabled: false`. |
| Evidence-building / revised assessment | Not built. Current drafting packages the cue and limited context; it does not reproduce the analyst's physical corroboration, source verification and evidence-driven hypothesis revision. |

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

The sitting desk now has a **bounded** drafter (`desk_draft_v0`): optional Tavily search requested against the packet cutoff, then Ollama using server-side `OLLAMA_MODEL` and `OLLAMA_BASE_URL` fills the working-assessment template. `--no-search` reuses saved search results, not a signals-only ablation. The replay-admission defect above must be fixed before a clean historical assessment. Frozen `intent_triage_v0` (Ollama, four conditions) stays disabled and separate.

The current implementation is a first-pass summary, not a demonstrated 70–80% reduction in analyst work. The analyst previews a machine draft, explicitly chooses whether to use it, edits and owns the save. Phase 5a supplies the missing investigative work.

- Target inputs: a versioned, frozen snapshot of the packet and admitted contextual evidence. No post-cutoff material or uncited model-memory claims. Current input is a selective summary, not that complete snapshot.
- The model must not invent observations. Proposed evidence significance and hypothesis updates belong in a separate, attributable interpretation layer for analyst review, not in the immutable detector facts.
- Target output schema (not yet enforced by the current free-text sections) **requires every hypothesis**, each with:

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

### 5a. Evidence-building and analyst labour reduction (next; not built)

**Outcome:** automate finding, organising and comparing evidence so the analyst operates at the top of the information pyramid. Do not optimise for a more alarming conclusion or force the machine to match the manual “send up” decision.

Implement in this order:

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

### 6. Produce the analyst report

`scenarios/<id>/reports/<report-id>/` as the thing an analyst would actually send:

1. cue: what converged, for how long, under which heuristic;
2. observations and derivations: hard statistics, baselines, geography, coverage, and permutation context;
3. information environment: prevailing public posture and likely amplification/dependency;
4. contextual evidence and counterevidence: cited, dated, both clocks;
5. assessment: competing hypotheses, packet-relative confidence, and what would change the judgement;
6. recommended public-source collection: wait, broaden news/official sources, inspect maps/catalogues, or enter focused review.

The report says: “these public channels changed together; here is the context we collected; here is how I assess it.” It never turns that configuration into a countdown prediction.

### 7. Continuous watch, only after phases 1–6 work retrospectively

The live desk is not `wsd run workflow` on a cron. It is a process that stays up and is driven by **time**.

- **Schedules** per source: weekday CBR prints, next-day Wikimedia, 3-day VIIRS reconstructed latency, FIRMS daily, NAVAREA as published. Each source is pulled when it is due, not when a scenario job starts.
- **Events** over time: observation arrived, expected day closed missing, source_down, coupling episode opened, notice workflow asked for context, posture harvest due. Measure and emit run on those edges.
- **Incremental corpus:** append new days; do not re-harvest the 120-day lookback unless a revision is required.
- **Rolling present:** notices open as coupling appears, not from a finished whole-window measurement. Packet cutoff is `now`.
- Collection jobs already have the live shape (Physical / Official on a notice). The missing piece is the watch itself, not more batch stages.

This is later PoC operations, not a claim that the underlying scientific detector has been validated. Keep the batch CLI as the backtest tool.

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
9. The evidence-building workflow reduces measured analyst collection/assembly effort while retaining source traceability and surfacing contradictions; fluency and agreement with a retrospective conclusion are not substitutes.

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
- Treat `wsd run workflow` (or a cron of it) as the live desk. Batch is backtesting; live is continuous, scheduled, and event-driven.

---

## Near-term order

The notice inbox, model-free packet, human assessment and first Ollama draft now exist. The manual comparison exposed the investigative gap. Preserve that checkpoint, then follow phase 5a:

1. Fix replay admission and revalidate cached context before another historical assessment is treated as clean.
2. Pass the already-collected evidence through an explicit, versioned input contract; surface missing and omitted items.
3. Add bounded requirement-led document discovery, extraction and a claim/evidence ledger, including contradictory evidence.
4. Draft evidence-backed changes to hypotheses, confidence and the collection decision in a separate interpretation layer.
5. Build source-linked analyst review and measure actual collection/assembly labour saved, including correction effort.
6. Exercise the same workflow on independent positive, quiet and contradictory cases. Continue the information-environment baseline and posture/dependency contracts; these remain incomplete.
7. Only then consider expanding source breadth or implementing the **continuous watch** (schedules + events, not a cron of `wsd run workflow`). A hosted model is not required.
