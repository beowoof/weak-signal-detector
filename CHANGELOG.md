# Changelog

All notable enhancements to this project are recorded here. The project follows an iterative research workflow rather than promising semantic-version compatibility during the PoC.

## Unreleased

### Added

- **FastAPI desk API** (`dashboard/server.py`): stdlib `ThreadingHTTPServer` replaced with FastAPI + uvicorn. `--reload` is on by default; `--api-only` pairs with Vite. OpenAPI at `/docs`.
- **React/Vite desk UI** (`dashboard/web/`): like-for-like port of the results viewer with HMR. `python dashboard/server.py --api-only` plus `npm run dev`. Polls `/api/result` every 8s so new notices appear without a UI restart.
- **`notice_v0` desk object:** `config/notice_policy.yaml`, `src/wsf/notice.py`, `wsd notice emit|list`. K≥3 coupling episodes persist as an immutable trigger plus mutable workflow. Dashboard **Notice inbox** lists them. Re-emit does not rewrite trigger facts.

### Changed

- **Collection-indicator framing:** dashboard and README treat multi-domain co-movement as a cue to collect more (news, tasked imagery), not as a determination of mobilisation or intent.
- **RUS physical AOIs:** `config/facilities.yaml` replaces Kremlin / Sheremetyevo / MoD postage stamps with seven frontier/staging boxes (Yelnya, Klintsy, Belgorod, Valuyki, Boguchar, Millerovo, Dzhankoi). `max_aois_per_focal` is 8.
- **FIRMS per-AOI counts:** detections are summed inside each staging box. A union bbox from Yelnya to Crimea would have ingested Donbas contact-line fires.

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
