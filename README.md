# Weak Signal Fusion

Weak Signal Fusion is an evidence-first proof of concept for a narrow question:

> When several individually weak public indicators become unusual together, do they provide useful incremental information for strategic-intent triage?

The phenomenon under test is closer to **strategic coupling**: during costly state preparation, normally weakly coupled physical, bureaucratic, informational, economic, and infrastructural systems become temporarily more statistically dependent. That is why the panel is organised by *causal domain*, not by how many OSINT feeds we can collect. Three correlated newspaper-derived series are worse than six rubbish thermometers from different mechanisms. The interesting coincidence is not "VIIRS, SAR, and FIRMS all saw physical activity"; it is "physical activity, bureaucratic tempo, and digital infrastructure became unusual together."

Strategic intent is not directly observable. The first layer therefore measures unusual mobilisation or costly activation with deterministic time-series rules. A later, separately scored interpretation layer will compare an explicit historical prior with the same prior plus cutoff-safe signal evidence.

The intended output is initially headless: a reproducible alert episode, its contributing indicators, source health, provenance, and an evidence packet suitable for analyst review. A dashboard is contingent on the headless PoC passing its investment gate.

## Current status

This repository is at the live-connector checkpoint. It contains:

- a reduced five-window development/holdout panel;
- nine versioned scientific configuration objects;
- Pydantic contracts for indicators, periods, observations, and features;
- canonical configuration hashing and immutable run manifests;
- exact-event-date cutoff selection that cannot carry stale anomalies forward;
- population-standard-deviation trailing z-scores with explicit polarity;
- coincidence across causal domains and source systems, with a costly-signal gate and persistence;
- synthetic fixtures and offline invariant tests;
- a JSON scenario lifecycle: create, validate, collect, review, focused recollect, and freeze;
- deterministic corpus gates and an explicit semantic-review queue;
- `run_test.py`, which assigns a parent experiment ID and runs a mocked scenario rehearsal;
- `run_unit_tests.py`, which assigns a run ID and records engineering-test artifacts;
- live connectors for Wikipedia pageviews, GDELT, ICEWS (local Dataverse zip), ALFRED, MOEX, VIIRS NTL, FIRMS NOAA-20, Internet Archive official hosts, crt.sh, and RIPEstat; OSM, wiki-edits, and Brent are implemented but out of the v1 basket; Sentinel-1 is implemented but disabled on `ukraine2022`; OpenSky credentials may be present but the Trino connector is not built; default tests remain offline;
- `wsd measure` scores a live harvest (missing/cloudy = unknown threat); no full-panel evaluation/report pipeline or model invocation yet.

The detailed design record is in `weak-signal-fusion-spec.md`. The literal operator workflow is in [`HOWTO.md`](HOWTO.md). This README is the operational source of truth and will be kept current as implementation proceeds.

## Architecture and lifecycle boundaries

Docker is used when a component requires a persistent process or a specific reproducible service environment. It is not used merely to wrap an ephemeral Python script.

| Component | Initial boundary | Reason |
|---|---|---|
| Python collection, build, evaluation, and test scripts | Host process managed by `uv` | Ephemeral and easy to reproduce from `pyproject.toml` |
| Scientific configuration | Versioned YAML | Human-readable experiment contract |
| Raw and derived analytical data | Parquet files; DuckDB may be added for queries | Portable, immutable, tabular, no service required |
| Ollama and `qwen3.8:27b-mlx` | Existing host service/API | MLX depends on the Mac environment; no container or token required |
| Future API/frontend | Docker | Persistent environment-specific component |
| Future PostgreSQL or ChromaDB | Docker, only if access patterns justify it | No database is required for the current tabular PoC |

ChromaDB is deferred. It becomes relevant only if the cited prior corpus grows large enough to need semantic retrieval. Explicit frozen prior packets are currently easier to reproduce and audit.

## Scientific separation

The project keeps two outputs separate:

1. **Deterministic measurement:** trailing anomalies, cross-domain coincidence, a costly-signal gate, and persistence.
2. **AI interpretation:** four paired packet conditions—base-rate, prior-only, masked signals-only, and prior-plus-signals.

The Ollama model never creates an observation, changes a feature, or changes an alert. Actor masking is an ablation, not the primary task. Historical behaviour remains available through explicit cutoff-safe, cited prior packets.

v1 coincidence requires three distinct **causal domains** and three source systems, plus one costly series. GDELT and ICEWS are independent coders of overlapping public reporting; they cannot double-vote. VIIRS, Sentinel-1, and FIRMS are independent sensors of physical activity; they also cannot triple-vote.

| Series | Domain | In v1 basket? |
|---|---|---|
| VIIRS NTL | physical activity | yes |
| Sentinel-1 backscatter | physical activity | register yes; **off** on `ukraine2022` |
| FIRMS thermal (NOAA-20) | physical activity | yes |
| OpenSky ADS-B | mobility | no (credentials optional; connector not built) |
| Official publication cadence | bureaucratic | yes |
| GDELT CAMEO | information | yes |
| ICEWS | information | yes (robustness, not a second domain) |
| Wikipedia pageviews | public attention | yes |
| OSM edits | public attention | no |
| Wikipedia edits | public attention | no |
| MOEX FX | market | yes |
| Brent | market | no |
| Certificate Transparency | digital infrastructure | yes |
| RIPEstat BGP prefixes | digital infrastructure | yes |

`qwen3.8:27b-mlx` is local and token-costless but relatively slow. The planned harness therefore uses bounded output, warm serial batches, five repeated runs, native Ollama timing counters, checkpointing, and resume. Codex will implement and test that harness with mocks but will not invoke the model.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Ollama only when the interpretation phase is explicitly run by the project owner
- Docker only when a persistent component is introduced

The current development machine has Python 3.13, `uv`, and Docker available.

## Setup

Install the package and development tools:

```bash
uv sync --extra dev
```

Copy the environment template:

```bash
cp .env.example .env
```

Populate only the credentials you have. `.env` and `.env.*` are ignored; `.env.example` remains tracked.

### Credentials and services

| Variable | Purpose | Required now? |
|---|---|---|
| `FRED_API_KEY` | Live FRED/ALFRED vintages | Yes, when `fred_series` is not null |
| `EARTHDATA_TOKEN` | Live NASA VIIRS granules | Yes, for live VIIRS collection |
| `FIRMS_MAP_KEY` | NASA FIRMS area API (quota 5000 txn / 10 min) | Yes, for live FIRMS |
| `FIRMS_SENSOR` | FIRMS product id, default `VIIRS_NOAA20_SP` | No; SNPP ceases 2026-11-01 |
| `COPERNICUS_CLIENT_ID` | Copernicus Data Space OAuth client | No unless Sentinel-1 is enabled |
| `COPERNICUS_CLIENT_SECRET` | Copernicus Data Space OAuth secret | No unless Sentinel-1 is enabled |
| `OPENSKY_TRINO_USER` | OpenSky website username | No; connector not built |
| `OPENSKY_TRINO_PASSWORD` | OpenSky website password | No; connector not built |
| `ICEWS_EVENTS_PATH` | Dataverse zip, directory, or `.tab` | Yes; `data/raw/icews/dataverse_files.zip` |
| `GOOGLE_CLOUD_PROJECT` | Optional bounded GDELT BigQuery path | No; bulk GDELT is qualified first |
| `GOOGLE_APPLICATION_CREDENTIALS` | Optional path to Google ADC credentials | No |
| `OLLAMA_BASE_URL` | Local Ollama API, default `http://localhost:11434` | Only for owner-run interpretation |
| `OLLAMA_MODEL` | Frozen local model, `qwen3.8:27b-mlx` | Only for owner-run interpretation |

Google Cloud will not be configured or used without an explicit decision after the GDELT bulk acquisition sample. Live source calls and model calls are never part of default tests.

## Scenario workflow

Corpus review separates **broken collection** from **incomplete nights**. Provenance failures, post-cutoff material, outcome-encoded queries, and a source that never arrived are hard NO-GOs. Coverage holes (cloud, holidays, one-AOI nights) are warnings. The measurement layer already treats missing days as not flagged; a learning / covariance system should keep ingesting every source that is up, including future X, OSINT, and news metrics.

The workflow is intentionally gated:

```text
draft -> collected -> reviewed -> frozen
             ^           |            \
             +-- focused recollection  +-> wsd measure (live harvest; not a scientific freeze)
```

Create an incomplete scenario template, fill it in, and validate it:

```bash
.venv/bin/wsd scenario create --name ukraine2022
.venv/bin/wsd scenario validate --scenario ukraine2022
```

Rehearsal:

```bash
wsd corpus collect --scenario ukraine2022 --mock
wsd corpus review --scenario ukraine2022 --mock-model
```

Live harvest of the declared scenario windows (no Ollama, no Google Cloud):

```bash
wsd corpus collect --scenario ukraine2022 --only wikipedia,alfred
wsd corpus collect --scenario ukraine2022
```

VIIRS live harvest also needs `uv sync --extra viirs`. Mocked output is always labelled rehearsal and cannot be frozen as real evidence. Live harvests are still not frozen scientific results until deterministic gates and the owner-run semantic review both pass. See [`HOWTO.md`](HOWTO.md).

## Running a scenario experiment

The normal command is:

```bash
python3 run_test.py --scenario ukraine2022 --through review --mock
```

It:

1. assigns a parent run ID such as `experiment-20260828T120000Z-a1b2c3`;
2. runs synthetic collection and a fake semantic review without live or Ollama calls;
3. writes `experiment_summary.json` and `experiment_summary.md` to `artifacts/<run-id>/`;
4. prints the run ID and artifact directory for feedback.

`--mock` remains the default rehearsal. Omit it for live collection. Live review still does not call Ollama; it stops at `model_pending` unless `--mock-model` is also set. Use `--through collect`, `--through review`, or `--through freeze` to choose the stopping point.

## Running engineering tests

The normal offline engineering-test command is:

```bash
python3 run_unit_tests.py
```

It assigns a `unit-...` run ID, excludes `live` and `model` tests, and records `pytest.log` plus `test_summary.json`. Use a supplied ID when reproducing a named run:

```bash
python3 run_unit_tests.py --run-id unit-my-reproduction
```

Optional profiles are deliberately explicit:

```bash
# May contact source APIs. Not used by default.
python3 run_unit_tests.py --live

# May invoke local Ollama. Codex must not run this profile.
python3 run_unit_tests.py --with-model
```

`--live` does not imply `--with-model`, and `--with-model` does not imply `--live`.

## Configuration validation and run identity

Validate all scientific configuration offline:

```bash
uv run wsf doctor
```

Create or verify an immutable run manifest:

```bash
uv run wsf init-run --run-id rehearsal-001
```

The manifest hashes:

- indicator register;
- period panel;
- measurement protocol;
- facilities and queries;
- expected baselines and milestones;
- explicit priors;
- interpretation protocol.

Reusing a run ID after any scientific value changes is an error. YAML comments and formatting do not change the canonical hash.

## Initial panel

| Window | Split | Role |
|---|---|---|
| `DEU-2018-quiet` | Development | Long quiet baseline |
| `USA-CHN-2018-trade` | Development | High-tension hard negative |
| `RUS-2021-apr` | Development | Reversed mobilisation positive |
| `GRC-TUR-2020` | Held out | High-tension hard negative |
| `RUS-2022` | Held out | Overt-action positive |

This is an investment-decision panel, not a population sample. It cannot establish a general false-alert rate or intent-classification accuracy.

## Data and cutoff rules

An observation contains:

- `event_time`: what date it describes;
- `available_at`: when that version was available under its declared regime;
- `retrieved_at`: when this project obtained it;
- immutable `version_id`, value, quality, and provenance metadata.

At cutoff date `D`, each daily source has an exact expected event date derived from its declared latency. If that expected observation is absent, the feature is missing. The builder must never reuse an older spike as a fresh daily flag.

VIIRS Collection 2 is explicitly retrospectively reconstructed. v0 uses an assumed three-day availability regime and retains actual production timestamps separately. It must not be described as a strictly contemporaneous historical feed.

## Planned source qualification

The current development harvest (`ukraine2022`) checks:

- GDELT bulk acquisition cost and completeness before considering BigQuery;
- Wikimedia complete-title aggregation;
- ALFRED as-of levels (no-call dud for daily ruble);
- VIIRS two-AOI minimum, cloud/quality/geometry artefacts, and coverage;
- FIRMS NOAA-20 AOI thermal counts;
- ICEWS talk counts from the local Dataverse zip;
- MOEX, official-host cadence, CT, and RIPEstat as additional domain channels;
- immutable provenance and reproducibility.

`ukraine2022` is a development showcase, not held-out evidence. No held-out source data is scored as a scientific result before the measurement and interpretation protocols are frozen.

## Investment gate

Further corpus expansion or dashboard work requires all of the following:

- real-source measurement qualification passes;
- the basket retains the development-positive detection relative to VIIRS alone;
- the basket reduces development false-alert episodes;
- the frozen held-out direction is useful without post-hoc changes;
- AI interpretation is grounded, stable enough to review, and adds value over prior-only packets.

A positive result justifies further human investment. It does not validate autonomous or operational alerting.

## Development procedure

- Work in reviewable enhancements.
- Add every enhancement to `CHANGELOG.md`.
- Keep default tests offline and inexpensive.
- Give every test or experiment run an immutable run ID.
- Preserve failed runs and duds.
- Feed each run's Markdown/JSON summary back for diagnosis and the next enhancement.
- Never change frozen scientific inputs after held-out output; create a new protocol and run instead.

## Safety and no-gos

- Retrospective research only; no current operational alerting or targeting.
- No live web search inside historical interpretation packets.
- No LLM-generated observation or deterministic alert score.
- No missingness interpreted as meaningful silence without a declared baseline. A cloudy VIIRS night is missing, not a reason to stop watching other sources.
- No stale daily carry, post-hoc threshold tuning, AOI splitting into extra votes, or hidden source substitution.
- No synthetic fixture reported as a scientific result.
- No dashboard before the headless investment gate.

## Roadmap

1. Offline contracts, run identity, fixtures, z-scores, and coincidence — complete.
2. Scenario lifecycle, mocked corpus gates, review queue, and operator HOWTO — complete.
3. Live connectors across causal domains (Wikipedia, GDELT, ICEWS zip, MOEX, VIIRS, FIRMS NOAA-20, official cadence, CT, RIPEstat) plus `wsd measure` — current checkpoint.
4. Owner-run Ollama corpus-review worker with bounded, resumable batches.
5. Lookback harvest, synchrony/permutation test, interpretation, and report pipeline.
6. Frozen held-out measurement and interpretation.
7. Broader corpus and analyst dashboard only after a positive investment decision. OpenSky Trino and Sentinel-1 stay out until explicitly opted in.

See `CHANGELOG.md` for the enhancement history.
