# Weak Signal Fusion

Weak Signal Fusion is an evidence-first proof of concept for a narrow question:

> When several individually weak public indicators become unusual together, do they provide useful incremental information for strategic-intent triage?

The phenomenon under test is closer to **strategic coupling**: during costly state preparation, normally weakly coupled physical, bureaucratic, informational, economic, and infrastructural systems become temporarily more statistically dependent. That is why the panel is organised by *causal domain*, not by how many OSINT feeds we can collect. Three correlated newspaper-derived series are worse than six rubbish thermometers from different mechanisms. The interesting coincidence is not "VIIRS, SAR, and FIRMS all saw physical activity"; it is "physical activity, bureaucratic tempo, and digital infrastructure became unusual together."

Strategic intent is not directly observable. The first layer therefore measures unusual mobilisation or costly activation with deterministic time-series rules. A later, separately scored interpretation layer will compare an explicit historical prior with the same prior plus cutoff-safe signal evidence.

The scientific output remains headless: a reproducible alert episode, its contributing indicators, source health, provenance, and an evidence packet suitable for analyst review. A local read-only results viewer can plot those files for diagnosis, but a broader analyst or operational dashboard remains contingent on the headless PoC passing its investment gate.

## Current status

The v1 detector claim is closed: [`FINDINGS.md`](FINDINGS.md). Public series do move together in late February 2022; hard negatives stay quiet; that is not a proof of invasion and not a smoking-gun tripwire.

Work continues as a **collection cueing desk**: when several independent weak series become unusual together, cue more collection and read the news environment. Physical sensors (VIIRS/FIRMS/SAR on frontier staging AOIs) corroborate or leave a coverage gap; they do not certify intent. Do not retune frozen `coincidence_v1` thresholds on Ukraine.

The desk is a Docker Compose app. Start it with [Desk API and UI](#desk-api-and-ui).

The repository still contains:

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
- live connectors for Wikipedia pageviews, GDELT, ICEWS (local Dataverse zip), ALFRED, MOEX, VIIRS NTL, FIRMS NOAA-20, Sentinel-1 (descending IW), Internet Archive official hosts, crt.sh, and RIPEstat; OSM, wiki-edits, Brent, and Certificate Transparency are out of the v1 basket; OpenSky Trino is not built; default tests remain offline;
- `wsd measure` scores a live harvest with trailing and frozen-local rhythm baselines, emits amber evidence-gap episodes, permutation-tests the red chorus with availability-aware circular shifts, and permutation-tests amber with a frozen costly/VIIRS unknown mask (max-run statistic); no Ollama yet.
- Collection-ready development scenarios `rus2021apr`, `deu2018quiet`, and `usachn2018trade` (21-day score + 120-day lookback) sit next to `ukraine2022`. Frozen `coincidence_v1` rules; do not retune from Ukraine. `GRC-TUR-2020` stays unharvested.

Replay of a recorded harvest is in [`HOWTO.md`](HOWTO.md). `ukraine2022` is a development showcase, not held-out evidence. Findings: [`FINDINGS.md`](FINDINGS.md). Design record: `weak-signal-fusion-spec.md`.

## Architecture and lifecycle boundaries

The collection cueing desk runs as Docker Compose (`compose.yaml`): Postgres, FastAPI, a collection/measure agent, and the Vite UI. Scientific harvests stay as files on a bind mount. Postgres holds desk runtime state (agent heartbeat now; jobs and websocket fan-out next). Host `uv` remains for offline tests and one-shot CLI.

| Component | Boundary | Reason |
|---|---|---|
| Desk stack | `docker compose up` | `db`, `api`, `agent`, `web` as one app |
| Scientific harvest files | Bind mount `./scenarios`, `./data` | Not ingested into Postgres |
| Python tests and one-shot CLI | Host process managed by `uv` | Ephemeral and easy to reproduce from `pyproject.toml` |
| Scientific configuration | Versioned YAML | Human-readable experiment contract |
| Raw and derived analytical data | Parquet / JSONL files | Portable, immutable, tabular |
| Ollama and `qwen3.8:27b-mlx` | Existing host service/API | MLX depends on the Mac environment; no container or token required |

ChromaDB is not part of measurement. When an LLM later acts as a **named intelligence-analyst step** (packet interpretation, not a general-purpose aggregator and never a combiner), retrieval will go through Chroma + embeddings so the model sees a cutoff-safe cited subset rather than the raw harvest. Explicit frozen prior packets remain the audit trail.

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
| Internet Archive official-host captures | bureaucratic hypothesis | no (diagnostic; construct validity unresolved) |
| GDELT CAMEO | information | yes |
| ICEWS | information | yes (robustness, not a second domain) |
| Wikipedia pageviews | public attention | yes |
| OSM edits | public attention | no |
| Wikipedia edits | public attention | no |
| MOEX FX | market | yes |
| Brent | market | no |
| Certificate Transparency | digital infrastructure | no (diagnostic; crt.sh not a dated series) |
| RIPEstat BGP prefixes | digital infrastructure | yes |

`qwen3.8:27b-mlx` is local and token-costless but relatively slow. The planned harness therefore uses bounded output, warm serial batches, five repeated runs, native Ollama timing counters, checkpointing, and resume. Codex will implement and test that harness with mocks but will not invoke the model.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Node.js 20 or newer (desk UI)
- Ollama only when the interpretation phase is explicitly run by the project owner
- Docker only when a persistent component is introduced

The current development machine has Python 3.13, `uv`, Node.js, and Docker available.

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

## Desk API and UI

One command from the repository root:

```bash
cp .env.example .env   # if you do not already have .env
docker compose up --build
```

Then open <http://127.0.0.1:5173> (UI) and <http://127.0.0.1:8000/docs> (API). `/api/health` reports Postgres and the agent heartbeat.

| Service | Port | Role |
|---|---|---|
| `web` | 5173 | Vite UI; proxies `/api` to the API container |
| `api` | 8000 | FastAPI over local measurement files |
| `db` | 5432 | Postgres (`wsd` / `wsd` / `wsd`) |
| `agent` | — | Heartbeats into Postgres; run CLI jobs with `docker compose exec` |

Collect or measure inside the stack:

```bash
docker compose exec agent wsd measure --scenario ukraine2022 --exploratory
docker compose exec agent wsd notice emit --scenario ukraine2022
```

The UI polls `/api/result` every 8s. Source under `dashboard/web/src` and `src/` is bind-mounted, so Vite and uvicorn still reload. Websocket invalidation of that poll is next.

Host-only fallback (no Docker): `uv sync --extra dev`, then `uv run python dashboard/server.py --api-only` and `cd dashboard/web && npm install && npm run dev`.

## Scenario workflow

Corpus review separates **broken collection** from **weather-limited nights**. Provenance failures, post-cutoff material, outcome-encoded queries, a source that never arrived, and non-weather daily coverage below its declared gate are hard NO-GOs. VIIRS cloud coverage and balanced incident/control missingness remain explicit warnings. MOEX coverage is calculated over expected weekdays rather than calendar weekends.

The workflow is intentionally gated:

```text
draft -> collected -> reviewed -> frozen -> scientific measurement
             ^           |
             +-- focused recollection  +-> exploratory measurement (explicit flag)
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

Until the owner-run semantic review is implemented, development measurements must opt in explicitly:

```bash
wsd measure --scenario ukraine2022 --exploratory
```

The report records `measurement_mode: exploratory_unfrozen` and `scientific_result: false`.

### Visualising local measurement results

See [Desk API and UI](#desk-api-and-ui). The plots are diagnostic views of recorded result labels. In particular, `exploratory_unfrozen` remains non-scientific, missing values remain unknown, and plotting does not satisfy the investment gate.

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
- No broader analyst, operational, or current-monitoring dashboard before the headless investment gate. The local read-only result visualiser is diagnostic only.

## Roadmap

1. Offline contracts, run identity, fixtures, z-scores, and coincidence — complete.
2. Scenario lifecycle, mocked corpus gates, review queue, and operator HOWTO — complete.
3. Live connectors across causal domains (Wikipedia, GDELT, ICEWS zip, MOEX, VIIRS, FIRMS NOAA-20, official cadence, CT, RIPEstat) plus `wsd measure` — current checkpoint.
4. Owner-run Ollama corpus-review worker with bounded, resumable batches.
5. Lookback harvest, synchrony/permutation test, interpretation, and report pipeline.
6. Frozen held-out measurement and interpretation.
7. Broader corpus and analyst dashboard only after a positive investment decision. OpenSky Trino and Sentinel-1 stay out until explicitly opted in.

See `CHANGELOG.md` for the enhancement history.
