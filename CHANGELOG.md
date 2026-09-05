# Changelog

**Reviewed 2026-09-05.** Current development history; dated entries below describe their state at the time.

## 2026-09-05 — Collection clarity, bounded research and substantive briefs

- Added **Secondary collection → Start secondary collection** with source selection, immediate status/explanation/timestamp results and a separate **Research and draft assessment** step. Removed competing inline launch controls; moved research limits beside their action.
- Exposed query/document/time controls and streamed browser stages, elapsed time, failures and stopping reasons. Document attempts are per invocation; increasing document/time allowances preserves the same-plan research checkpoint. Tavily credit balance is not inspected.
- Passed per-question collection outcomes into assessment drafting and editorial synthesis. Recorded cloud/quality/fill/no-granule/retrieval diagnostics for new VIIRS observations without inventing reasons for older missing data.
- Strengthened editorial instructions to retain concrete evidence, current analyst judgement, counterevidence and actionable discriminators; separated earlier packet context and removed sensor-availability-based explanatory confidence.
- Added an editorial example and reconciled all maintained Markdown guides with the implemented workflow. Generated historical briefs and numerical experiment results remain records, not rewritten outputs.
- Verified the offline Python suite (321 passed, one skipped), frontend tests (13 passed), production build and mocked collection-to-brief browser flow. No live collection or model generation is claimed by these checks.

## 2026-09-05 — Align delivery around the complete intelligence workflow

- Make public-source investigation through assessment and a finished brief the product objective, with manual detours feeding automation.
- Specify durable review decisions, assessment integration, brief revision/sign-off/export, and a practical retrospective gate for a bounded live pilot.
- Separate detector research claims from product delivery gates and reconcile conflicting README guidance. This earlier documentation-only entry specified the workflow; subsequent implementation is recorded below.

All notable enhancements to this project are recorded here. The project follows an iterative research workflow rather than promising semantic-version compatibility during the PoC.

## Unreleased

### Changed

- **Repository contents:** git now tracks scenario contracts (`scenario.json`) and application code only. Notices, packets, briefs, collection jobs and harvest products remain local bind-mounted files.
- **Assessment workflow UI:** one notice-tab row, a separate Notice actions menu, and four assessment stages that show only the selected step. Brief preparation keeps visible running, failure and completion states when switching steps.
- **Replay research:** preferred queries now use AOI/place names and contemporaneous source language instead of the first four generic keys plus the full requirement text. Official/imagery domains are fetched first. YouTube, social video, PDFs, images and post-cutoff URL dates are skipped without consuming the document-attempt budget. If a preferred search returns no fetchable leads, a broader fallback search runs while query budget remains. Collection outcomes and the draft prompt distinguish preferred sources from fallback public reporting. Admitted documents stay in the review bundle in full. Drafting indexes them as exact character slices, embeds with `OLLAMA_EMBED_MODEL` (default `mxbai-embed-large`), and sends retrieved passages with parent evidence IDs instead of dropping pages to fit a character cap. Lexical overlap is used if embeddings are unavailable. Search snippets are never indexed.
- **Archive admission:** gzip-compressed Wayback bodies are decompressed before the HTML/text check; binary or non-UTF-8 captures are rejected rather than admitted as replacement-character garbage. Wayback captures whose URL differs only by scheme, `www`, trailing slash or percent-encoding are treated as the same document.
- Brief preparation now reports input preparation, model drafting, validation and saving stages. The UI polls during generation and shows elapsed time with an indeterminate bar while the model runs, rather than inventing a completion percentage.

### Documentation

- Clarify README regeneration examples: packet builds rewrite evidence and watch-summary exports under a stable ID; PDF rendering, machine assessment drafting and final editorial synthesis are separate actions. Document UI refresh, API restart and assessment reset.

### Changed

- **Analytical briefing presentation:** notice overviews and regenerated notice exports lead with a two-sentence BLUF, analytical confidence/rationale and an explicit public-source assessment. Display-only probability ranges follow PHIA's published yardstick on first use without changing stored observations or hypotheses.
- **Editorial output contract:** requires BLUF (maximum two sentences/60 words), substantive judgements before the concise confidence and source-assessment sections. Model input includes relevant source provenance and warns against invented reliability, independent corroboration or confidence ratings. Existing saved brief versions are preserved.


### Added

- **Editorial brief synthesis:** preparation now calls configured Ollama with saved assessment, retained proposal wording and review limitations, producing referenced key judgements, significance, alternatives and outlook. Strict section/reference/length checks, retained attempt inputs/outputs, stale-input rejection and duplicate-generation protection preserve existing briefs on failure. Analyst amendments create unsigned versions with the annex retained.
- **Testing reset and brief removal:** reset archives saved state and clears the active assessment, review decisions and briefs while retaining research; successful UI reset also clears local drafts. Individual brief removal hides its exports while retaining audit history. No reset or generation was performed on the user's assessment during implementation.


### Changed

- **Useful weak-signal findings:** the draft prompt requires observation-capable sources for negative findings, keeps relevant coverage gaps under unknowns, and encourages attributed affirmative reporting without demanding direct deployment imagery. Existing model outputs remain unchanged until rerun.
- **Review navigation:** saved proposals collapse into labelled summaries with reopening; numbered steps and navigation connect retained-material preview, assessment editing/saving and brief naming/preparation in page order.

### Added

- **Complete local review-to-brief path:** persisted, version-bound finding/hypothesis/action decisions and history; explicit reviewed-material merge that preserves surrounding analyst prose; immutable brief content versions with evidence annex, stale-state detection, reviewer sign-off, Markdown and printable HTML export. The initial renderer made no model call; current brief preparation uses editorial Ollama synthesis as described above. It performs no new research or distribution. API revision checks reject stale writes; tests cover lifecycle, changed proposals using the same bundle, preservation and escaped export.


### Fixed

- **Prompt-JSON quotation recovery:** malformed unescaped quotations are repaired only when one longest interpretation is an exact substring of the cited admitted evidence. Raw output remains unchanged, repair metadata is recorded, and the resulting draft is forced to human review rather than automatic application. An explicit rerun can revalidate a rejected, completed response when its prompt hash and model match, avoiding another Ollama generation.
- **Long and token-limited drafts:** Ollama now receives a deterministic model view capped at 32,000 characters rather than the full 76k-character Ukraine bundle. Round-robin evidence-class selection prevents numeric rows from consuming the whole prompt while the immutable full bundle remains available for review. The output contract removes duplicated notes/sections/citations, caps claims and renders Markdown deterministically. Explicit length-stopped responses and timing counters are retained under the attempt but never applied or automatically continued. CLI output now exposes prompt/item limits and new research-call counts; a cache-only rerun reports zero enrichment calls.
- **Historical draft input admission:** undated official search hits no longer get a special exemption. All cached search snippets remain leads until a content version is established; generic official/packet prose cannot reintroduce excluded search claims. Genuine pre-cutoff warnings can be retained as versioned evidence. The original contaminated checkpoint remains on disk for audit, and an old draft is not automatically regenerated.
- **Automatic draft application:** `--apply` now also requires the reference-review checks to pass; incomplete grounding stays visible and does not automatically seed even an empty human report. Explicit manual editing/saving remains available.
- **pytest temporary-directory vulnerability:** raised both runtime and dev requirements to `pytest>=9.0.3,<10` and updated `uv.lock` from 8.4.2 to 9.0.3. This addresses Dependabot alerts #1 and #2 for the same Unix temporary-directory issue, [CVE-2025-71176 / GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g). Existing Python Docker images must be rebuilt to receive the patched dependency; source bind mounts alone do not update installed packages.
- **Structured draft sections:** model-authored lists and objects in `sections` are converted to readable Markdown before validation. The raw response and conversion metadata are preserved; malformed and empty assessments remain rejected. The prompt now explicitly requests string-valued sections, and cutoff-language checks include saved sections even when `notes` takes display precedence.
- **Ollama structured-output compatibility:** an explicit HTTP 501 `structured output is unavailable` response gets one resubmission without native JSON mode. Prompt JSON is still validated before saving; other errors and uncertain timeouts are not retried. Draft sidecars record the output mode.
- **Draft progress:** the host CLI consumes API stage events and two-second heartbeats via `/api/packet/draft/stream`, showing a job ID, stage bar and elapsed time on stderr. `--quiet` retains JSON-only output; the JSON endpoint remains supported; the UI now also consumes the progress stream. The bar measures completed stages, not token-generation percentage.
- **Draft CLI routing:** `wsd packet draft` now submits to the Docker desk API, which owns Ollama configuration and generation. `WSD_API_BASE_URL` defaults to `http://127.0.0.1:8000`; no local fallback or automatic retry. Existing flags, JSON summary and leakage exit status are preserved.
- **CBR holidays:** a weekday with a policy rate but no RUONIA print is a closed session (`missing`), not `source_down`. New Year, 23 Feb, 8 Mar and 2020 non-working days no longer fail the 0.95 coverage gate.

### Added

- **Checksummed OSINT search index:** exact Tavily requests are reused project-wide across packets and scenarios using a normalized query/date/options checksum and a content-addressed result object. Every cache read verifies both checksums; corrupt entries fail closed, and an identical in-flight query is deferred rather than charged twice. Cache hits work without an API key, and the legacy collector no longer retries an uncertain search automatically. Search snippets remain outside the model prompt and do not become admitted evidence. Per-run CLI telemetry distinguishes new Tavily requests from index hits.
- **Phase 5a first implementation:** a versioned `desk_evidence_v1` input bundle now supplies item-level observations, official events, physical records and chronology. Exclusions and deterministic context-budget omissions are explicit; original packet/collection files are not rewritten. Exact model inputs and raw completions (including structurally rejected output) are retained per attempt.
- **Bounded requirement-led research:** drafting can run up to six contextual/counterevidence searches and six document attempts, with a 180-second scheduling budget and per-request timeouts. Historical text requires an exact pre-cutoff archive capture; HTML/text extraction, hashes, truncation, source identity and unresolved provenance are recorded. Request checkpoints avoid silently repeating paid, failed or uncertain requests; this is not an unrestricted research agent.
- **Claim and hypothesis review:** source-ID and exact-quotation checks flag unsupported references; model proposals can revise hypothesis likelihoods without changing detector facts. The Notes view exposes evidence, source passages, changed hypotheses, exclusions and research gaps. Accept/reject marks are session-only; saved assessments remain human-owned. Citation presence is not semantic verification, and labour savings are not yet measured.
- **Phase 5a verification:** 291 offline Python tests passed (1 skipped, 3 deselected), 11 frontend tests passed, and the production build and mocked browser hand-off test passed. No live model generation was used for implementation verification; real-source usefulness and analyst effort reduction remain unqualified.

- **Bounded machine draft:** `wsd packet draft --replay` (desk button **Machine draft**) uses local Ollama and server-side `.env` configuration. Phase 5a replaces the original snippet-based input with versioned evidence and optional bounded research. The draft is a sidecar (`machine_draft.md`); it does not open notices or vote. `--apply` requires an empty report, clear cutoff-language checks and passing reference checks. `--no-search` uses collected evidence and cached admitted documents, not unverified search snippets; it is not a signals-only ablation.
- **Analyst-controlled draft hand-off:** the UI offers preview / use / keep assessment; replacing editor text requires confirmation. Saved notes remain unchanged until an explicit save, and switching notices does not silently reapply a machine draft. A mocked browser smoke test covers these behaviours.
- **4 September checkpoint:** the owner completed a real host CLI → Docker API → Ollama draft in about 78 seconds, with three citation entries and `applied: false`. Offline verification reached 257 passed, 1 skipped and 3 deselected. This demonstrates execution, not factual correctness, clean replay provenance or measured labour savings.
- **`wsd run workflow`:** one command for validate → collect → review → measure → emit. Stops on `no_go` (exit 2) and prints the `--focus` resume. `--from` / `--through` skip or cut stages. Measure defaults to `--exploratory`. Does not freeze, prune, call Ollama, or build packets. This is the **backtest** operator path (replay a closed window). The live desk is continuous, scheduled, and event-driven (ROADMAP phase 7); do not cron this command as a watch.
- **Harvest progress:** corpus collect writes `collect_progress.json` (source, day, AOI, tile, bytes, elapsed, stalled). Desk banner and Operations poll `GET /api/collection/progress` every 2s. VIIRS uses cached granules when present and times out a hung NASA download after 5 minutes. The CLI shows a byte bar when NASA reports granule size (`[####....] 50% 11/22MB`). HDF5 cache is kept through collection. `wsd corpus prune-viirs --scenario <id>` is allowed only after that scenario’s corpus review is not `no_go`, and not while a harvest is running.
- **Copernicus catalogue pointers:** Physical posture harvests cutoff-safe Sentinel-1 GRD and Sentinel-2 L1C catalogue hits over named AOIs. Pointers only; scenes are not downloaded and do not vote. Sentinel-2 CDSE PublicationDate is often a later reprocess, so knowability uses reconstructed 1-day availability when publication is stale.
- **Collection job plans:** Physical and Official tasks now state which open sources can answer the requirement, which AOIs to query, which dates are admissible at cutoff, and what observation would discriminate among the hypotheses. Wired harvest still runs; unwired sources are marked as analyst search.
- **Analyst working assessment:** **Add Notes** on the alert and Anomaly banner opens one text box pre-filled with a packet template (`GET`/`POST /api/report`, `wsd packet report`). The desk does not draft it. Writes `scenarios/<id>/reports/<report-id>/`.
- **Brief PDF:** `packet build` writes `brief.pdf` (A4). Desk button **Download PDF** (`GET /api/packet/pdf`). CLI `wsd packet pdf`.
- **Declared posture family:** non-voting `posture.travel_risk`, `diplomatic_posture`, `official_threat_language`, `government_action`. FCDO travel-advice `change_history` is cutoff-filtered (replay-safe). US State uses the live API when contemporaneous, otherwise the last Wayback snapshot at or before cutoff. Official pack harvests it and asks whether the quantitative cue is consistent with, ahead of, or divergent from the UK/US public prior. Costly signals (embassy drawdown, leave-now, travel-advice escalation) outweigh rhetoric.
- **Collection tasks:** `Validate cue`, `Chronology (30 days)`, `Refresh physical`, and `Official pack` write into `interpretation/<packet>/collection/`. **Request more information** runs the three harvests at focused posture (not surge). Cutoff-safe; does not vote. `POST /api/packet/collect`, `wsd packet collect`.
- **Intelligence-product brief:** default playback is assessment, translated watchlist (observation → analytic significance), can/cannot, competing explanations with coarse fit and “what would discriminate”, and collection priorities. Analytic state `quiet → anomaly → watch → preparatory pattern → escalation` labels observable system state. Audit/provenance (z-scores, latency, missingness) is an expander. VIIRS unavailability stays a prominent warning.
- **Operations UI:** left nav (Notices / Anomaly / Operations). Emit notices and build briefs are buttons (`POST /api/notice/emit`, `POST /api/packet/build`). CLI stays for tests and harvests.
- **Notice operator workflow:** `ack`, `reexamine`, `request_context`, `ignore`, `reject` with an append-only event log. Human state machine, not LangGraph. `POST /api/notice/action` and `wsd notice act`.
- **Brief UI:** notice brief renders as tables, status chips, and coloured callouts (chorus rows, missing cells, not-yet-knowable), not a preformatted wall of text.
- **Model-free brief:** `wsd packet build` / **Build brief** writes `brief.md` plus structured `brief[]` sections. Replay cutoff is binding: VIIRS 3-day latency and next-day wiki are stated as not yet knowable, not as quiet. No model, no invented geopolitics.
- **Packet brief layers:** `evidence.json` now has `layers`, information-environment dimensions (proxy vs missing, never a vote), and a geopolitical-context slot (empty until harvest).
- **Notice as the UI alert:** desk opens on an inbox of notices (not a results-viewer tab). `/api/notices` lists alerts across scenarios; Anomaly charts are a drill-down from the selected notice. Opening an alert marks its dates on the charts, highlights contributing series/domains, and flags the matching matrix rows.
- **`packet_v0` compiler** (`src/wsf/packet.py`, `wsd packet build`): same command for a live desk (`knowledge_cutoff=now`, requires `available_at` and `retrieved_at`) and a historical replay (`--replay` / `--as-of`, `available_at` only). Writes `interpretation/<packet-id>/evidence.json`. Does not assign significance. Refuses to treat a years-late emit as live.
- **Docker Compose desk** (`compose.yaml`): `db` (Postgres 16), `api` (FastAPI), `agent` (`wsd agent run`), `web` (Vite). `docker compose up --build` is the running app. Harvests stay on bind-mounted files; Postgres holds agent heartbeat and a jobs table for later queue/websocket work. `/api/health` reports both.
- **FastAPI desk API** (`dashboard/server.py`): stdlib `ThreadingHTTPServer` replaced with FastAPI + uvicorn. `--reload` is on by default; `--api-only` pairs with Vite. OpenAPI at `/docs`.
- **React/Vite desk UI** (`dashboard/web/`): like-for-like port of the results viewer with HMR. `python dashboard/server.py --api-only` plus `npm run dev`. Polls `/api/result` every 8s so new notices appear without a UI restart.
- **`notice_v0` desk object:** `config/notice_policy.yaml`, `src/wsf/notice.py`, `wsd notice emit|list`. K≥3 coupling episodes persist as an immutable trigger plus mutable workflow. Dashboard **Notice inbox** lists them. Re-emit does not rewrite trigger facts.

### Changed

- **Next roadmap increment:** phase 5a explicitly prioritises analyst labour reduction: evidence admission, detailed collected evidence, requirement-led research, claim/evidence review and proposed hypothesis revisions. The first engineering slice is implemented; source/model qualification, persistent review decisions, richer investigation and measured effort savings remain outstanding. Removed the unsupported “70–80% first pass” claim and added measurable effort/grounding acceptance checks.
- **Operating mode:** ROADMAP now distinguishes batch backtest (`wsd run workflow` on a closed window) from the later live desk (continuous, per-source schedules, event-driven measure/emit). README and HOWTO no longer call the batch command the live path.
- **Desk draft vs frozen interpretation:** sitting-desk draft is `desk_draft_v0` on Ollama + Tavily. Frozen `intent_triage_v0` (Ollama, four conditions, `enabled: false`) is unchanged.
- **Analytic state:** Escalation requires a prior notice in the same scoring window. A first cue at the research window’s last days is Watch. Window geometry is not observable system state; `days_before_window_end` no longer promotes Escalation. Ukraine 21–23 Feb stays Escalation because 10–12 Feb already opened.
- **Watchlist market series:** USD/RUB (MOEX) appears when it contributes and CBR does not. Maritime warnings are omitted from the “simultaneously elevated” clause when they do not persist.
- **FIRMS spatial attribution:** the watchlist states detections as a count within the monitored staging AOIs as a combined set. Named AOIs appear only in keys and physical-posture collection, not as if one detection occurred in every listed place.
- **Assessment:** the geographic-frame sentence sits in keys only. Assessment is judgement → evidence → alternatives → decision.
- **Official posture requirement:** a bounded collection task (contemporaneous Russian, Ukrainian, UK, US and allied statements and formal measures, including travel advice, diplomatic drawdowns, defence announcements, NOTAM/NAVAREA restrictions and sanctions). Identify changes in declared threat assessment or costly government action.
- **Desk copy:** product headings no longer lecture the taxonomy. Inbox and header state the current surface; the brief speaks in observations and implications.
- **Brief hedging:** the assessment states abnormal multi-domain activity. It no longer carries a “does not support mobilisation / intent / imminent attack” card. Those claims are outside the signal.
- **PHIA language:** key judgements use the Probability Yardstick (`almost certain`, `realistic possibility`, `likely`/`unlikely`). Analytical confidence is an AnCR (Low/Moderate/High) with a rationale. Competing explanations show likelihood, not “fit”. The assessment ends on the collection decision.
- **Collection-indicator framing:** dashboard and README treat multi-domain co-movement as a cue to collect more (news, tasked imagery), not as a determination of mobilisation or intent.
- **RUS physical AOIs:** `config/facilities.yaml` replaces Kremlin / Sheremetyevo / MoD postage stamps with seven frontier/staging boxes (Yelnya, Klintsy, Belgorod, Valuyki, Boguchar, Millerovo, Dzhankoi). `max_aois_per_focal` is 8.
- **FIRMS per-AOI counts:** detections are summed inside each staging box. A union bbox from Yelnya to Crimea would have ingested Donbas contact-line fires.

### Known limitations at the 4 September checkpoint

These describe the original owner-run checkpoint, before the phase 5a changes above. Its artefacts have not been regenerated or qualified as a clean replay.

- **Replay contamination:** three of six saved Tavily hits for the 12 February 2022 Ukraine packet were undated official-source results, including a January 2024 map. They reached the draft input despite being marked `date_unverified`. Existing “cutoff-safe” artefact summaries overstate admission quality. The artefacts are retained as audit evidence; new drafts use the revised admission path, verified with offline fixtures but not yet a fresh owner-run assessment.
- **Investigation versus summarisation:** drafting uses fixed searches and snippets, plus packet summaries and official notes. It does not yet consume the detailed official/physical collection, investigate released imagery or geolocated movement reporting, or validate claim-level citations. The prompt constrains likelihood revision to the initial packet. Human evidence discovery and corroboration remain the major unautomated work.

### Added

- **Multi-Domain Dynamic Coupling & Sensor Cueing Engine (`src/wsf/analysis/coupling.py`, `scripts/run_coupling_analysis.py`, `COUPLING_EVALUATION.md`):**
  - Replaced rigid univariate smoking-gun gates with continuous **Multi-Domain Anomaly Energy** $E_{\text{dom}}(t) = \sum_{d} \max_{s \in d} \max(0, z_{s,t})$.
  - Two-tier operational triage model:
    - **Strategic Warning ($K_{\text{dom}} \ge 3$, $\ge 3$ consecutive days):** Co-elevation across $\ge 3$ independent causal domains.
    - **Soft Coupling Cue ($K_{\text{dom}} \ge 2$, $\ge 3$ consecutive days):** Multi-channel preparatory activity tipping high-cost sensors.
  - **Dynamic Sensor Tasking Orders:** Automated trigger mechanism emitting collection orders to all-weather/high-resolution sensors (SAR, commercial imagery) during optical/cloud gaps whenever soft coupling is elevated.
  - Availability-preserving circular-shift permutation test for multi-domain coupling episodes.
- **Costly Non-Optical & Administrative Indicators (Option 2):**
  - Added `spatial_restriction` and `domestic_financial_conditions` causal domains in `src/wsf/types.py`.
  - `official.gazette_cadence` (`src/wsf/connectors/gazette_cadence.py`): positive bureaucratic document cadence, weekend/out-of-hours releases, and issuing authority entropy.
  - `nav.spatial_warnings` (`src/wsf/connectors/navarea.py`): NGA NAVAREA maritime warning spatial restriction area ($\text{km}^2$) and lead time.
  - `market.cbr_funding_spread` (`src/wsf/connectors/cbr.py`): Bank of Russia RUONIA interbank funding spread ($\text{RUONIA} - \text{policy rate}$) and sovereign yield curve slope ($3\text{M}-2\text{Y}$).
  - `air.notam_restrictions` (`src/wsf/connectors/notam.py`): airspace closure connector stub.
  - Registered new indicators in `config/indicator_register.yaml` (23 total registered indicators) and `src/wsf/measure.py`.
  - Unit test suites in `tests/test_new_connectors.py` and `tests/test_coupling.py`.
- **Interactive Multi-Domain Coupling Dashboard (`dashboard/`):**
  - Added dedicated **"Multi-domain coupling"** view tab in `dashboard/index.html` and `dashboard/app.js`.
  - Executive metric cards for Strategic Warnings, Soft Cues, Sensor Tasking Orders, and Peak Domain Energy.
  - Interactive multi-domain energy time series with automated sensor tasking point markers.
  - Causal domain energy breakdown chart tracking peak anomaly scores by domain mechanism.
  - Daily operational triage matrix table displaying date, active domain list, total energy, optical sensor state, verdict badges, and sensor cue triggers.
  - Backend integration in `dashboard/server.py` serving coupling metrics via `/api/result`.
- **Salvage Blueprint & Re-Evaluation Documentation:**
  - `IDEAS.md`: Complete salvage blueprint and priority roadmap.
  - `EWS_EVALUATION.md`: Comparative evaluation of rolling Pearson correlation leading eigenvalues ($\lambda_{\max}$) vs level-shift anomaly energy.
  - `COUPLING_EVALUATION.md`: Detailed multi-scenario evaluation report across all 4 scenarios.
  - Updated `FINDINGS.md`: Documented successful post-salvage validation, full 4-scenario scorecard, and project findings.

### Fixed

- **DEU Gazette Cadence Pagination (`src/wsf/connectors/gazette_cadence.py`):**
  - Follows `next` pagination URLs in the OffeneGesetze API (`https://api.offenegesetze.de/v1/veroeffentlichung/`), resolving the constant-zero issue on `deu2018quiet` and harvesting 206 real historical publications.
- **Explicit `source_down` Failure Handling (`gazette_cadence.py`, `navarea.py`, `cbr.py`):**
  - Replaced pre-filled zero dictionaries with explicit `source_down_days` tracking on HTTP timeouts, non-200 responses, and JSON/XML parse errors, preventing failed harvests from masquerading as quiet observations.
- **Actor-Appropriate Gazette Sources:**
  - Disabled `gazette_cadence` on Russian scenarios (`ukraine2022`, `rus2021apr`) to eliminate leaking unfiltered US Federal Register document counts into the Russian bureaucratic domain.
- **CBR Interbank Spread Validation (`src/wsf/connectors/cbr.py`):**
  - Requires policy key rate data before computing RUONIA funding spreads, marking missing key rate dates as `source_down` instead of silently returning 0.0.
- **Comprehensive Connector Unit Tests (`tests/test_new_connectors.py`):**
  - Added assertions on HTTP transport calls, parsed non-zero values, multi-page DEU pagination, and HTTP 503 `source_down` branches across all new connectors.
- **Documentation & ID Alignment (`FINDINGS.md`, `COUPLING_EVALUATION.md`, `scripts/run_coupling_analysis.py`):**
  - Synchronized active collection/measurement IDs with on-disk state (`status.json`).
  - Updated permutation p-values and episode counts across all documents, reflecting the empirical results ($p_{\text{episodes}} \approx 0.43$–$0.44$).
  - Clarified that tasking orders are a derived operational triage rule rather than proof of unusual precursor coupling.

### Added (Previous)

- `FINDINGS.md`: recorded outcome of the development panel (speculative success, execution failure). Development stopped.

### Changed

- Sentinel-1 frozen orbit is descending IW. On the panel AOIs it is the only RUS overpass geometry, slightly denser than ascending for DEU, and thinner for USA. Ascending+descending are not mixed. Revisit-limited SAR coverage is a review warning, not a 0.95 daily no-go.

- FIRMS area queries use a 1–5 day span (NASA now rejects 10). HTTP 400/invalid and crt.sh 502/timeout are `source_down` (unknown threat), never observed zero. MAP_KEY is stripped from FIRMS provenance URLs.
- Certificate Transparency queries the frozen official-host domains (not only `mil.ru` / `army.mil`, which public CT often omits) and treats a total fetch failure as `source_down`. Demoted from the v1 basket: crt.sh is not a usable dated series from the UK.

- MOEX coverage is harvest health (prints vs source_down), not the fraction of weekdays with a session. Exchange holidays stay `missing` (cannot flag) and no longer trip the 0.95 daily-coverage gate. ISS history is paginated; HTTP errors are `source_down`, not zeros.
- ALFRED coverage is harvest health the same way: H.10 holidays (`.`) and unpublished tail days stay `missing` and no longer trip 0.95. Scoring uses a 7-day H.10 vintage lag (`fred` connector) so FX can become visible instead of remaining absent on every event day.

- Filter measurement baskets to series actually materialised by the active collection, so disabled Sentinel-1 no longer creates permanent costly-source unknowns.
- Replace raw prior-year rhythm comparison with a symmetric frozen local lookback for each incident/control window; require both z and empirical-tail thresholds.
- Treat equality to a zero-variance baseline as normal while allowing a genuinely new value beyond that baseline to flag.
- Require `wsd measure --exploratory` until a non-rehearsal semantic GO and freeze exist; every report records measurement mode and scientific status.
- Bind new freezes and scientific measurements to the complete scientific-configuration hash, preventing a pre-revision freeze from validating a changed protocol.
- Calculate MOEX coverage over expected weekdays. Keep weather-limited VIIRS shortfalls as warnings, but restore other daily coverage failures as hard gates.
- Demote Internet Archive official-host capture counts from the voting basket until their bureaucratic construct validity is demonstrated.

- OSM changesets, Wikipedia edits, and Brent are out of the v1 voting basket and disabled on new scenarios / `ukraine2022`. OSM is public attention, not physical activity.
- ICEWS stays as a robustness stream in the information domain; it does not double-vote GDELT.
- FIRMS, CT, and RIPEstat notes now describe AOI/list anomalies versus own history, not military-thermal, military-named certs, or cyber-operations inference.
- Protocol `k_distinct_families` is off; domain independence supersedes family clones as the fusion axis.

### Added

- Initial Python 3.12+ package and `uv` project metadata.
- Nine YAML scientific configuration objects for the reduced five-window panel.
- Pydantic contracts for indicators, periods, observations, and feature rows.
- Canonical YAML hashing that includes milestones, priors, and the interpretation protocol.
- Immutable run-manifest creation and hash-mismatch refusal.
- Exact expected-event-date cutoff selection with no stale fallback.
- Population-standard-deviation trailing z-scores with explicit polarity and missing-baseline handling.
- Cross-family, cross-source, costly-gated coincidence and calendar-day persistence episodes.
- Synthetic cutoff/revision fixture and offline invariant tests.
- `run_unit_tests.py` with automatic run IDs, offline defaults, explicit live/model profiles, and run artifacts.
- Project-virtual-environment test execution with a `uv` bootstrap fallback, avoiding unnecessary global cache access after setup.
- `.env.example` for FRED, Earthdata, optional Google Cloud, and local Ollama configuration.
- README covering architecture, setup, testing, data semantics, AI boundaries, investment gates, and roadmap.
- `wsd scenario` commands for creating, validating, inspecting, and freezing scenario state.
- `wsd corpus` commands for mocked corpus collection, deterministic review, and focused recollection from `missing.json`.
- Immutable scenario hashes, append-only lifecycle history, parent collection links, and explicit rehearsal freeze labels.
- A semantic corpus-review queue for later owner-run Ollama processing; the current mock path never invokes a model.
- `run_test.py` as the scenario experiment harness, with parent/child run IDs and JSON/Markdown summaries.
- `HOWTO.md` with a command-by-command operator handoff from scenario creation through corpus freeze.
- Live connectors for Wikipedia pageviews, GDELT Events 2.0 English export files, ALFRED vintages, and VIIRS VNP46A2 zonal means.
- Offline HTTP fixtures and a `pytest.mark.live` Wikipedia smoke test that is excluded from the default profile.
- Optional `uv sync --extra viirs` extra (`earthaccess`, `h5py`, `numpy`) for granule harvest.
- `wsd corpus collect --only` for partial harvests, with review treating skipped enabled sources as gaps.
- Daily GDELT count cache under `data/raw/gdelt/` and redacted provenance URLs.
- VIIRS Collection 2 search uses CMR version `2`, 10-degree geographic tiles, and the `VIIRS_Grid_DNB_2d` HDF group.
- VIIRS reader looks up `HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields` before any Collection 1 path.

### Changed

- Reduced the proposed panel from eight windows to five for an achievable PoC.
- Separated deterministic mobilisation/activation measurement from AI-assisted strategic-intent triage.
- Made `qwen3.8:27b-mlx` a local, repeated, resumable interpretation component rather than the detector.
- Defined Docker as the boundary for persistent or environment-specific components, not ephemeral scripts.
- Changed the primary measurement comparison from an oracle best singleton to VIIRS alone.
- Corrected stale-observation persistence, VIIRS reconstruction semantics, covariance sample minima, ALFRED raw-level handling, and scientific-input hashing in the specification.
- Split engineering tests from scenario experiments so `run_test.py` now means a research-harness run, not pytest.
- `wsd corpus collect` without `--mock` now runs live connectors instead of raising `NotImplementedError`.
- `run_test.py` can run a live harvest when `--mock` is omitted; it still never invokes Ollama.
- `wsd doctor` reports connector credential presence and whether the VIIRS extra is installed, without printing secrets.
- Lengthened `ukraine2022` observation windows from 7 to 21 pre-event days after the 7-day February slice failed the VIIRS 0.70 coverage gate.
- Enlarged RUS capital, Sheremetyevo, and MoD AOIs so a night is not lost to an 8-pixel cloudy stamp; capital and MoD remain disjoint.
- Stderr progress for collect and review (GDELT per-day/slot, VIIRS per night, Wikipedia titles). JSON remains on stdout. `--quiet` disables it.
- Gitignore scenario harvest products (`corpus/`, `reviews/`, `status.json`, `history.jsonl`); keep `scenario.json` as the tracked contract.
- Corpus review treats VIIRS/cloud coverage holes and incident/control imbalance as warnings. Hard NO-GO is reserved for broken collection (provenance, cutoff leakage, missing source, all-day source_down).
- `wsd measure` scores the active live harvest. Cloudy/missing observations are unknown threat, never treated as normal activity or silence.
- Free extra sources: MOEX USD/RUB, FIRMS thermal, Wikipedia edits, OSM changesets, RIPEstat prefixes, Internet Archive official-host captures, crt.sh certs, ICEWS local dump, ALFRED Brent. No paid APIs.
- v1 panel reorganised around causal-domain independence; Sentinel-1 added then disabled on `ukraine2022`; OSM/wiki-edits/Brent demoted.
- OpenSky Trino credentials are optional placeholders; the mobility connector is not built.
- HTTP retries truncated Internet Archive CDX bodies (`IncompleteRead`); official cadence isolates per-host failures instead of marking the whole window source_down.
- RIPEstat isolates per-ASN timeouts, caches daily prefix JSON, and records a timed-out day as missing rather than failing the whole window.
- RIPEstat uses the prefix-count endpoint (one small JSON per ASN per window) instead of downloading announced-prefixes lists. AS12389 timed out for hours on the full list.
- Live collect runs independent sources in parallel (default 4). Retries/backoff remain inside each connector; the same source still processes windows one at a time.
- Collect harvests `lookback_days` before each scored window (default 120). Measure still scores only `start`–`end`; z-baselines can now reach protocol `n_min`. Coincidence thresholds are unchanged.
- Initial parallel rhythm overlay and permutation scaffolding, superseded in `coincidence_v1` by frozen local priors and availability-aware circular shifts.
- README, HOWTO, and fixture notes aligned to the live panel (NOAA-20 FIRMS, ICEWS zip, Sentinel-1 off, `wsd measure`). The design spec defers to those files for connector state.

### Security

- Ignored `.env` variants while keeping `.env.example` trackable.
- Default tests exclude live API and model calls.
- Codex is prohibited from invoking the model-enabled profile.
