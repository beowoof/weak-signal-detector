# Operator HOWTO: Scenario to Frozen Corpus

This is the bouncing-ball procedure for the current proof of concept. Follow it from top to bottom. Each command says what the system does, what the operator must inspect, and what permits the next step.

The current build is an **engineering rehearsal**. `--mock` creates synthetic corpus metadata and `--mock-model` creates a fake semantic-review response. Neither is evidence and neither calls Ollama. Live collection and owner-run Ollama execution are deliberately not connected yet.

## 0. One-time setup

Run these commands from the repository root:

```bash
uv sync --extra dev
cp .env.example .env
.venv/bin/wsd doctor
```

Operator action:

- If `.env` already exists, do not overwrite it; skip the `cp` command.
- Confirm `doctor` returns JSON with no error.
- Do not configure Google Cloud. It is not required for this stage.

Expected result: `.venv/bin/wsd` exists and the scientific YAML configuration validates offline.

## 1. Create the scenario

Choose a lowercase, kebab-case name. For the development showcase:

```bash
.venv/bin/wsd scenario create --name ukraine2022
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

Operator action: open `scenarios/ukraine2022/scenario.json`. It is intentionally incomplete. Do not edit `status.json` or `history.jsonl`.

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
    "start": "2022-02-17",
    "end": "2022-02-23",
    "target_start": "2022-02-24",
    "target_end": "2022-03-02",
    "lookback_days": 120,
    "selection_reason": "Seven days immediately before the declared target event."
  },
  "controls": [
    {
      "id": "same-period-prior-year",
      "start": "2021-02-18",
      "end": "2021-02-24",
      "target_start": null,
      "target_end": null,
      "lookback_days": 120,
      "selection_reason": "Same seasonal week in the prior year without the target event."
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
.venv/bin/wsd scenario validate --scenario ukraine2022
```

Expected result: JSON containing `"collection_ready": true` and a `scenario_hash`.

If validation fails, the error names the missing or invalid field. Edit only `scenario.json`, then rerun validation. Do not continue until it passes.

## 4. Rehearse corpus collection

```bash
.venv/bin/wsd corpus collect --scenario ukraine2022 --mock
```

Expected result:

- a new `scenarios/ukraine2022/corpus/collection-.../` directory;
- `manifest.json` and `collection_summary.md` inside it;
- scenario status changes from `draft` to `collected`;
- output says `"mode": "synthetic_rehearsal"`.

Operator action: open `collection_summary.md` and `manifest.json`. Confirm the incident and control each contain one synthetic item per enabled source. This confirms orchestration only; it says nothing about real source quality.

Check state at any time with:

```bash
.venv/bin/wsd scenario status --scenario ukraine2022
```

## 5. Review the corpus

For the fully mocked rehearsal:

```bash
.venv/bin/wsd corpus review --scenario ukraine2022 --mock-model
```

Expected result: a new `reviews/review-.../` directory containing:

- `deterministic_review.json`: hard coverage, provenance, cutoff, symmetry, and query-leakage checks;
- `model_queue.jsonl`: the semantic-review job that a later owner-run Ollama harness will consume;
- `model_responses.jsonl`: fake response, present only because `--mock-model` was used;
- `missing.json`: machine-readable gaps for focused recollection;
- `decision.json` and `review.md`: the review outcome.

Expected mocked decision: `go_candidate_rehearsal`. This proves only that the workflow can advance. It is not a scientific GO.

Without `--mock-model`, the command still makes **no model call**. When hard gates pass, it writes the queue and returns `model_pending`. Stop there until the owner-run Ollama execution step is implemented.

## 6A. If the decision is NO-GO

Open the exact `missing.json` path printed by the review command. The operator chooses one of two actions:

1. Accept that the scenario cannot support a fair test and abandon it; or
2. approve one focused recollection that addresses the declared gaps without changing the hypothesis.

To rehearse focused recollection:

```bash
.venv/bin/wsd corpus collect \
  --scenario ukraine2022 \
  --focus scenarios/ukraine2022/reviews/REVIEW_ID/missing.json \
  --mock
```

Replace `REVIEW_ID` with the printed directory name, then rerun Step 5. The new manifest records both its parent collection and the gap IDs it was asked to resolve.

Operator rule: do not quietly change dates, thresholds, sources, or queries to manufacture a GO. Any hypothesis-changing edit requires a fresh collection and must remain visible in history.

## 6B. If the decision is GO

A real corpus can advance only on `go_candidate`, which will require deterministic gates plus an owner-run, grounded semantic review. That execution path is not implemented yet.

The mocked rehearsal may be frozen only with an explicit warning flag:

```bash
.venv/bin/wsd scenario freeze --scenario ukraine2022 --allow-rehearsal
```

Expected result: `freeze.json` is created and status becomes `frozen`. Its `rehearsal` field is `true`. A frozen scenario refuses further collection.

Do not use `--allow-rehearsal` for a scientific run. It exists solely to prove the state transition works.

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

Use `--through collect` to stop after collection, or `--through freeze` to rehearse the complete lifecycle. Never reuse a run ID.

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
| Analyse | Future measurement and interpretation stages | Review signals and evidence packet | Not implemented yet |

The “ball” is always either with the system (a command is running) or the operator (a named file must be reviewed). There is no automatic jump from corpus collection to scientific analysis.
