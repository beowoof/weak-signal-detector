# Changelog

All notable enhancements to this project are recorded here. The project follows an iterative research workflow rather than promising semantic-version compatibility during the PoC.

## Unreleased

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

### Changed

- Reduced the proposed panel from eight windows to five for an achievable PoC.
- Separated deterministic mobilisation/activation measurement from AI-assisted strategic-intent triage.
- Made `qwen3.8:27b-mlx` a local, repeated, resumable interpretation component rather than the detector.
- Defined Docker as the boundary for persistent or environment-specific components, not ephemeral scripts.
- Changed the primary measurement comparison from an oracle best singleton to VIIRS alone.
- Corrected stale-observation persistence, VIIRS reconstruction semantics, covariance sample minima, ALFRED raw-level handling, and scientific-input hashing in the specification.
- Split engineering tests from scenario experiments so `run_test.py` now means a research-harness run, not pytest.

### Security

- Ignored `.env` variants while keeping `.env.example` trackable.
- Default tests exclude live API and model calls.
- Codex is prohibited from invoking the model-enabled profile.
