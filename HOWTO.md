# Operator HOWTO: Scenario to Frozen Corpus

## Current experiment (read this first)

`ukraine2022` is a **development showcase**, not held-out evidence. Do **not** change `z_threshold`, `k`, amber persistence, or coincidence rules after seeing February 2022. Do **not** add another media feed.

The next live work uses the **same frozen `coincidence_v1` rules** on other panel cases (21-day scored windows + 120-day lookback). Create local lifecycle files automatically via `wsd scenario validate` if you cloned only `scenario.json`.

```text
Order (all development_showcase, none of them held-out):
  1. rus2021apr        other mobilisation-positive (spring 2021 buildup/drawdown)
  2. deu2018quiet      hard negative: quiet German autumn
  3. usachn2018trade   hard negative: loud 2018 tariff talk, no mobilisation
Do not harvest GRC-TUR-2020 yet.

For each scenario:

1. wsd scenario validate --scenario <id>
2. wsd corpus collect --scenario <id>
      Harvest each window plus 120-day lookback. Sources run in parallel.
      Inspect collection_summary.md (zeros and cloud are OK; source_down is not).
      2018 cases disable FIRMS (NOAA-20 starts 2018-04-01; 2017 control lookback
      cannot use the frozen instrument) and MOEX (not a DEU/USA mechanism).
      They do call ALFRED (`DEXUSEU` / `DEXCHUS`); confirm FRED_API_KEY.
3. wsd corpus review --scenario <id>
      critical=0 → continue (VIIRS weather gaps may remain warnings).
      no_go → focused recollect from the printed missing.json, then review again.
4. wsd measure --scenario <id> --exploratory
      Development scoring, explicitly non-scientific until semantic review and freeze:
        a. Trailing z — novelty vs the last 90 days of this window.
        b. Rhythm — each window vs its own frozen pre-window baseline (z + tail rank).
        c. Amber — persistent cross-domain soft flags while costly evidence is unavailable.
        d. Red permutation — circularly shift all flags across that series' observable days.
        e. Amber permutation — shift only non-costly flags; freeze the costly/VIIRS
           unknown mask. Statistic: max consecutive amber run.
      Read measurement.md. Compare incident vs control. Do not retune from Ukraine.

Ollama / Qwen is not part of this path. A later analyst step will retrieve
cutoff-safe packets from a vector store (Chroma + embeddings), not dump the harvest
into a general-purpose aggregator.
```

---

This is the bouncing-ball procedure for the current proof of concept. Follow it from top to bottom. Each command says what the system does, what the operator must inspect, and what permits the next step.

`--mock` creates synthetic corpus metadata and `--mock-model` creates a fake semantic-review response. Neither is evidence and neither calls Ollama. Live collection has real connectors for Wikipedia, GDELT, ALFRED, VIIRS, FIRMS (NOAA-20), MOEX, official cadence, CT, RIPEstat, and ICEWS. Sentinel-1 is implemented but disabled on the default panel. The owner-run Ollama review worker is still not connected.

## 0. One-time setup

Run these commands from the repository root:

```bash
uv sync --extra dev
cp .env.example .env
wsd doctor
```

Optional, only when you are ready to harvest VIIRS granules:

```bash
uv sync --extra viirs
```

Sentinel-1 is **opt-in** (disabled on `ukraine2022`). If you enable it later, the CDSE Statistical API needs a free OAuth client at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/) as `COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET`.

Operator action:

- If `.env` already exists, do not overwrite it; skip the `cp` command.
- Confirm `doctor` returns JSON with no error.
- For the default `ukraine2022` harvest, confirm `EARTHDATA_TOKEN`, `FIRMS_MAP_KEY`, and `ICEWS_EVENTS_PATH`. `FRED_API_KEY` is unused while `fred_series` is null. Copernicus is not required.
- Do not configure Google Cloud. GDELT uses the bulk file path, not BigQuery.

Expected result: `wsd` exists, the scientific YAML configuration validates offline, and connector credential flags are visible without printing secrets.

## 1. Create the scenario

Choose a lowercase, kebab-case name. For the development showcase:

```bash
wsd scenario create --name ukraine2022
```

Expected result:

```text
scenarios/ukraine2022/
├── scenario.json       <- operator edits this
├── status.json         <- system owns this
├── history.jsonl       <- system appends lifecycle events
├── corpus/             <- collection revisions appear here
├── reviews/            <- corpus reviews appear here
├── measurement/
├── interpretation/
└── reports/
```

Operator action: open `scenarios/ukraine2022/scenario.json`. It is intentionally incomplete. Do not edit `status.json` or `history.jsonl`. Git tracks `scenario.json` only; corpus, reviews, and lifecycle state stay local.

## 2. Complete `scenario.json`

Fill in all null dates and query actors. At minimum, supply:

- `actors.focal` and any `actors.counterparts`;
- incident `start`, `end`, `target_start`, and `target_end` dates;
- every control window's `start`, `end`, and `selection_reason`;
- cutoff-safe `queries.wiki_titles`;
- `queries.cameo_actor` and `queries.facility_actor`.

For a first Ukraine 2022 **development** rehearsal, these are reasonable starting values:

```json
{
  "actors": {
    "focal": "RUS",
    "counterparts": ["UKR"]
  },
  "incident": {
    "id": "incident",
    "start": "2022-02-03",
    "end": "2022-02-23",
    "target_start": "2022-02-24",
    "target_end": "2022-03-02",
    "lookback_days": 120,
    "selection_reason": "Twenty-one days immediately before the declared target event."
  },
  "controls": [
    {
      "id": "same-period-prior-year",
      "start": "2021-02-04",
      "end": "2021-02-24",
      "target_start": null,
      "target_end": null,
      "lookback_days": 120,
      "selection_reason": "Same seasonal 21-day window in the prior year without the target event."
    }
  ],
  "queries": {
    "wiki_titles": ["Russia", "Ukraine", "Russian Armed Forces"],
    "cameo_actor": "RUS",
    "cameo_root_codes": ["01", "02", "04", "13"],
    "fred_series": null,
    "facility_actor": "RUS"
  }
}
```

Merge those values into the generated file; do not replace the whole file, because the generated source and gate settings are also required.

Operator check:

- The pre-event observation window ends before the target event begins.
- The control was selected by a rule that could have been stated before seeing results.
- Query titles describe actors or general institutions, not the known outcome. For example, do not add `2022 Russian invasion of Ukraine`.
- Keep `purpose` as `development_showcase` for Ukraine 2022. Do not later present it as held-out evidence if it helped develop the harness.

## 3. Validate the operator input

```bash
wsd scenario validate --scenario ukraine2022
```

Expected result: JSON containing `"collection_ready": true` and a `scenario_hash`.

If validation fails, the error names the missing or invalid field. Edit only `scenario.json`, then rerun validation. Do not continue until it passes.

## 4. Rehearse corpus collection

```bash
wsd corpus collect --scenario ukraine2022 --mock
```

Expected result:

- a new `scenarios/ukraine2022/corpus/collection-.../` directory;
- `manifest.json` and `collection_summary.md` inside it;
- scenario status changes from `draft` to `collected`;
- output says `"mode": "synthetic_rehearsal"`.

Operator action: open `collection_summary.md` and `manifest.json`. Confirm the incident and control each contain one synthetic item per enabled source. This confirms orchestration only; it says nothing about real source quality.

Check state at any time with:

```bash
wsd scenario status --scenario ukraine2022
```

## 4B. Live corpus collection

Do this only after Step 3 has passed. Live collection writes a **new** corpus revision; it does not overwrite the mock revision. A previous mock collection is never copied into a live harvest.

Start with the cheap sources. Wikipedia is a few HTTP GETs. ALFRED is a no-call dud for Ukraine 2022 because there is no daily H.10 ruble series:

```bash
wsd corpus collect --scenario ukraine2022 --only wikipedia,alfred
```

Expected result:

- `"mode": "live_harvest"`
- observation JSONL under `corpus/collection-.../observations/`
- provenance logs with redacted credentials
- ALFRED items marked `not_applicable`

This partial harvest will fail deterministic review because GDELT and VIIRS are still enabled in `scenario.json`. That is intentional. Disable a source in `scenario.json` only if you are changing the hypothesis; do not use `--only` as a silent source substitution.

Full live harvest of each window **plus its lookback** (`lookback_days`, default 120). Measure still scores only `start`–`end`; the extra days are the trailing baseline so `n_min=20` is real from day one of the scored window. Do not copy a 21-day parent with `--focus` for this — run a new full collect.

Do **not** retune `z_threshold`, `k`, or persistence after seeing Ukraine 2022 flags. Those stay frozen.

Full live harvest:

```bash
wsd corpus collect --scenario ukraine2022
```

Progress lines go to stderr (source, window, day, cache vs download). The JSON result stays on stdout. Use `--quiet` to suppress progress. Independent sources harvest in parallel (default four at a time); retries and backoff stay inside each source. Windows of the same source stay sequential. `--source-workers 1` restores the old one-source-at-a-time behaviour.

Operator expectations:

- GDELT downloads 96 fifteen-minute English `export` zips per day, counts CAMEO talk rows, then discards the zip. A 21-day incident plus 21-day control is about 4,000 files; already-cached days are skipped. Daily counts live under `data/raw/gdelt/`.
- VIIRS requires `uv sync --extra viirs` and `EARTHDATA_TOKEN`. Collection 2 is a 15-arc-second geographic grid (Moscow is tile `h21v03`), retrospectively reconstructed; `available_at` is night + 3 days.
- v1 harvests independent *mechanisms*, not more media clones. Enabled by default: Wikipedia pageviews, GDELT, ICEWS (robustness only; same information domain as GDELT), ALFRED, MOEX, VIIRS, FIRMS, Internet Archive official-host cadence, crt.sh certificate counts, RIPEstat prefixes. OSM, Wikipedia edits, Brent, and Sentinel-1 are implemented but disabled. FIRMS needs a free `FIRMS_MAP_KEY` (quota 5000 transactions / 10 minutes; this harvest is about 6 calls). ICEWS needs `ICEWS_EVENTS_PATH=data/raw/icews/dataverse_files.zip` (the zip is read in place; do not unpack it, and do not commit it). Failures on one source no longer abort the rest of the harvest. X and full news NLP remain paid/heavy. Do not add another media-derived feed until a synchrony/permutation test has run.
- Sentinel-1, if later enabled, is a boring AOI series: mean IW VV backscatter (dB) versus the AOI's own history on comparable ascending passes. It does not detect vehicles. Days without an overpass are unknown, not zero.
- FIRMS is an AOI thermal-count anomaly, not "military thermal activity." The frozen sensor is NOAA-20 VIIRS standard processing (`VIIRS_NOAA20_SP`), which covers April 2018–present. Suomi-NPP FIRMS delivery ceases 1 November 2026; do not use SNPP as the panel instrument. NOAA-21 only starts January 2024, so it cannot cover Ukraine 2022.
- Certificate Transparency and RIPEstat are frozen-list counts versus own history. Do not inspect certificate names or infer cyber operations.
- OpenSky remains **uninstantiated**. Trino user/password may already be in `.env`; there is still no connector. Do not scrape the public REST API. If implemented later, freeze AOIs and ask whether nighttime aviation activity is unusual relative to itself.
- Google Cloud is not used.
- Codex/automation must not run this full harvest.

Inspect `collection_summary.md` for coverage, missing days, and source-down days. Then continue to review.

## 5. Review the corpus

For the fully mocked rehearsal:

```bash
wsd corpus review --scenario ukraine2022 --mock-model
```

Expected result: a new `reviews/review-.../` directory containing:

- `deterministic_review.json`: hard provenance/cutoff/query/daily-coverage checks plus VIIRS weather warnings;
- `model_queue.jsonl`: the semantic-review job that a later owner-run Ollama harness will consume;
- `model_responses.jsonl`: fake response, present only because `--mock-model` was used;
- `missing.json`: machine-readable gaps for focused recollection;
- `decision.json` and `review.md`: the review outcome.

Expected mocked decision: `go_candidate_rehearsal`. This proves only that the workflow can advance. It is not a scientific GO.

Without `--mock-model`, the command still makes **no model call**. When hard gates pass, it writes the queue and returns `model_pending`. Cloudy VIIRS nights and incident/control coverage imbalance are **warnings**, not NO-GOs. Other daily sources below their declared coverage gate are critical. MOEX weekends/exchange holidays and ALFRED H.10 holidays (`.` values) or unpublished tail days are `missing` (cannot flag) and do not count against coverage; do not recollect them hoping for a print. ALFRED scoring waits 7 days for the H.10 vintage. Stop at `model_pending` until the owner-run Ollama execution step is implemented.

A NO-GO means the collection is broken (no provenance, post-cutoff leakage, an enabled source never collected, or a connector that is down every day). It does not mean “a sensor had weather.”

## 6A. If the decision is NO-GO

Open the exact `missing.json` path printed by the review command. The operator chooses one of two actions:

1. Accept that the scenario cannot support a fair test and abandon it; or
2. approve one focused recollection that addresses the declared gaps without changing the hypothesis.

To rehearse focused recollection:

```bash
wsd corpus collect \
  --scenario ukraine2022 \
  --focus scenarios/ukraine2022/reviews/review-20260828T144512Z-affd62/missing.json \
  --mock
```

Replace `REVIEW_ID` with the printed directory name, then rerun Step 5. The new manifest records both its parent collection and the gap IDs it was asked to resolve.

Operator rule: do not quietly change dates, thresholds, sources, or queries to manufacture a GO. Any hypothesis-changing edit requires a fresh collection and must remain visible in history.

## 6B. If the decision is GO

A real corpus can advance only on `go_candidate`, which will require deterministic gates plus an owner-run, grounded semantic review. That execution path is not implemented yet.

The mocked rehearsal may be frozen only with an explicit warning flag:

```bash
wsd scenario freeze --scenario ukraine2022 --allow-rehearsal
```

Expected result: `freeze.json` is created and status becomes `frozen`. Its `rehearsal` field is `true`. A frozen scenario refuses further collection.

Do not use `--allow-rehearsal` for a scientific run. It exists solely to prove the state transition works.

## 6C. Measure the live harvest

After a live collection and review, development measurement must explicitly acknowledge that semantic review and freeze are incomplete:

```bash
wsd measure --scenario ukraine2022 --exploratory
```

This writes `scenarios/ukraine2022/measurement/measure-.../`:

- `features.jsonl`: per series-day state (`flagged`, `normal`, `unknown`, `insufficient_baseline`)
- `days.jsonl`: a verdict that does **not** treat a cloudy VIIRS night as quiet
- `measurement.md`: incident/control comparison, amber episodes, null effects, and daily tables
- `summary.json`

A missing or cloudy night is **unknown threat**, not a normal activity level. `soft_flags_costly_unknown` requires at least two distinct non-costly causal domains while a costly series is unavailable. Three consecutive such days create an **amber evidence-gap episode** for analyst review; it is not promoted to a red protocol alert.

Trailing z uses a moving baseline within the same window. **Rhythm** freezes each incident or control window's own pre-window lookback, then requires both the z threshold and an empirical tail rank. It never compares raw 2021 source levels directly with raw 2022 levels. **Red permutation** independently circular-shifts each series' flag calendar within that series' protocol-eligible days, preserving missingness and flag runs. **Amber permutation** circular-shifts only the non-costly kitchens and holds the costly/VIIRS unknown (cloud) mask fixed; the test statistic is the maximum consecutive amber run, with `p_max_run = P(null max_run ≥ observed)`. `coincidence_v1` still requires `n_baseline ≥ 20`, a costly signal, three sources, three distinct causal domains, and three-day persistence. VIIRS+SAR+FIRMS cannot triple-vote; GDELT and ICEWS share one information domain.

Expected report labels for this path are `measurement_mode: exploratory_unfrozen`, `scientific_result: no`. Omitting `--exploratory` before a real non-rehearsal freeze is an error.

A future scientific freeze records both the scenario hash and the complete scientific-configuration hash. Changing `protocol.yaml`, the indicator register, priors, or interpretation protocol invalidates that freeze and requires a new review/freeze cycle.

## 6D. Plot recorded measurements locally

From the repository root, start the read-only results viewer:

```bash
python3 dashboard/server.py
```

Open <http://127.0.0.1:8000>. Use **Result set** to move between scenarios and measurement runs, then switch among:

- **Individual series** for raw values plus trailing and frozen-rhythm z-scores;
- **All series** for aligned small multiples with independent raw-value scales;
- **Combined z-scores** for comparable multi-series time plots; and
- **Z-score scatter** to see where trailing and rhythm baselines disagree.

The server discovers ignored `scenarios/*/measurement/` outputs on each request and never changes them. Older result formats without rhythm fields remain navigable; their rhythm and scatter views state that paired values are unavailable. Treat the viewer as a diagnostic aid only: it does not change `measurement_mode`, make an exploratory result scientific, or turn missingness into a normal observation.

## 7. Run the whole mocked test harness

After `scenario.json` validates, Steps 4 and 5 can be run together:

```bash
python3 run_test.py --scenario ukraine2022 --through review --mock
```

The harness assigns a parent ID such as `experiment-20260828T120000Z-a1b2c3`, uses child collection/review IDs derived from it, and writes:

```text
artifacts/<run-id>/experiment_summary.json
artifacts/<run-id>/experiment_summary.md
```

Use `--through collect` to stop after collection, or `--through freeze` to rehearse the complete lifecycle. Never reuse a run ID. Omit `--mock` only for an owner-run live harvest; that path still does not call Ollama.

Operator action: send both summary files, plus `decision.json` and `missing.json` when relevant, back for the next enhancement review.

## 8. Run engineering tests

Engineering tests are separate from scenario experiments:

```bash
python3 run_unit_tests.py
```

Expected result: pytest passes and the command prints a `unit-...` run ID and an `artifacts/<run-id>/` path containing `pytest.log` and `test_summary.json`.

The optional profiles are owner-controlled:

```bash
# May contact real source APIs after connectors exist.
python3 run_unit_tests.py --live

# May invoke local Ollama after model tests exist. Codex must not run this.
python3 run_unit_tests.py --with-model
```

## Operator/system handoff

| Stage | System does | Operator must do | Continue when |
|---|---|---|---|
| Create | Writes a structured template and state files | Supply actors, dates, controls, and safe queries | Validation passes |
| Collect | Creates an immutable corpus revision and provenance manifest | Inspect coverage and source scope | Required evidence is present |
| Review | Applies hard gates; queues semantic balance review | Read decision and every critical gap | Decision is GO, or a focused recollection is approved |
| Recollect | Links the new revision to prior gaps | Verify it addressed gaps without changing the hypothesis | Review passes |
| Freeze | Pins scenario, collection, review, and hashes | Confirm rehearsal versus real status | `freeze.json` is correct |
| Measure | `wsd measure --exploratory` scores the active development harvest | Read strict, amber, control, and null results | Scientific only after real GO and freeze |
| Interpret | Future owner-run Ollama packets | Not implemented yet | — |

The “ball” is always either with the system (a command is running) or the operator (a named file must be reviewed). There is no automatic jump from corpus collection to scientific analysis.
