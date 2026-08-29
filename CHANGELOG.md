# Changelog

All notable enhancements to this project are recorded here. The project follows an iterative research workflow rather than promising semantic-version compatibility during the PoC.

## Unreleased

### Added

- Causal-domain metadata on every instantiated indicator (`physical_activity`, `mobility`, `bureaucratic`, `information`, `public_attention`, `market`, `digital_infrastructure`) plus collector and whether the subject controls the signal.
- Coincidence now requires `k_domains` distinct causal domains. Sensor clones in the same domain (VIIRS+SAR+FIRMS, GDELT+ICEWS) cannot triple-vote.
- Sentinel-1 GRD AOI mean VV backscatter via the Copernicus Data Space Statistical API (`tempo.s1_backscatter`). Comparable ascending IW passes; missing overpass = unknown, not zero. Not equipment detection.
- Uninstantiated `mobility.opensky` placeholder pending KCL OpenSky Trino research access.
- `COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET` in `.env.example`. HTTP POST support for OAuth and the Statistical API.
- `.env.example` now lists every source with its public website. Keyless APIs have `=public` placeholders; ICEWS has `ICEWS_EVENTS_PATH`; OpenSky has Trino user/password stubs.
- ICEWS accepts the Dataverse zip, a directory of yearly `.tab` files, or a single table. Nested year zips are read in place; only window years are opened.
- FIRMS default sensor is NOAA-20 VIIRS standard processing. Suomi-NPP FIRMS delivery ceases 1 Nov 2026; NOAA-21 is too new for 2022 windows.
- ICEWS default path documents `data/raw/icews/dataverse_files.zip`; FIRMS MAP_KEY quota (5000 txn / 10 min) is noted in `.env.example`.

### Changed

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
- README, HOWTO, and fixture notes aligned to the live panel (NOAA-20 FIRMS, ICEWS zip, Sentinel-1 off, `wsd measure`). The design spec defers to those files for connector state.

### Security

- Ignored `.env` variants while keeping `.env.example` trackable.
- Default tests exclude live API and model calls.
- Codex is prohibited from invoking the model-enabled profile.
