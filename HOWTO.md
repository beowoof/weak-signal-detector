# Operator HOWTO: Scenario to Frozen Corpus

**Reviewed 2026-09-05.** Current operator guide. Secondary collection and assessment research are separate actions; see the session update below.

## Secondary collection and assessment — current UI

1. Open the notice and click **Secondary collection**.
2. Select source jobs and click **Start secondary collection**. Review statuses, summaries and last-run times directly below; open detailed results as needed.
3. Use **Research and draft assessment** to retrieve/check documents and generate Ollama proposals. Set query, document-attempt and research-time limits beside that button before running. Source jobs in step 2 are separate from these limits.
4. Review retained findings in **Notes & assessment**, save your judgement, then **Prepare new brief version**. Brief preparation does editorial synthesis, not further collection.

The [2026-09-05 checkpoint](DOCUMENTATION_STATUS.md) explains exact limits, per-run continuation, reasons for missing data and the inspected six-document archive failure. A generic “missing” record does not establish cloud cover. A returned source job or retrieved document does not establish that the research question was answered.

## Current experiment (read this first)

The original detector claim is closed; analyst-desk development continues. Read [`FINDINGS.md`](FINDINGS.md) for the historical measurement conclusions.

`ukraine2022` is a **development showcase**, not held-out evidence. Do **not** change `z_threshold`, `k`, amber persistence, or coincidence rules after seeing February 2022. Do **not** add another media feed. Do **not** harvest `GRC-TUR-2020`.

The commands below replay the recorded path (21-day scored windows + 120-day lookback) under frozen `coincidence_v1`. Create local lifecycle files automatically via `wsd scenario validate` if you cloned only `scenario.json`.

```text
Order (all development_showcase, none of them held-out):
  1. rus2021apr        other mobilisation-positive (spring 2021 buildup/drawdown)
  2. deu2018quiet      hard negative: quiet German autumn
  3. usachn2018trade   hard negative: loud 2018 tariff talk, no mobilisation
Do not harvest GRC-TUR-2020 yet.
```

For each historical scenario, one **backtest** command runs validate → collect → review → measure → emit on that closed window. The live desk (later) is continuous, scheduled, and event-driven; do not treat this batch job as that watch.

```bash
wsd run workflow --scenario <id>
```

It does not freeze, prune VIIRS, call Ollama, or build packets. Measure is
`--exploratory` (non-scientific) unless you pass `--no-exploratory` on a freeze.
If review is `no_go`, the pipeline stops (exit 2) and prints the resume command
with `--focus missing.json`. After a harvest that already exists:

```bash
wsd run workflow --scenario <id> --from review
```

The same stages still exist as individual commands if you need to inspect between
them. Collect harvests each window plus 120-day lookback. 2018 cases disable
FIRMS (NOAA-20 starts 2018-04-01; 2017 control lookback cannot use the frozen
instrument) and MOEX (not a DEU/USA mechanism); they do call ALFRED
(`DEXUSEU` / `DEXCHUS`). Review: critical=0 continues; `no_go` needs a focused
recollect. Measure is development scoring until semantic review and freeze.
Do not retune from Ukraine. If emit opens notices, the JSON `next` field lists
`wsd packet build --scenario <id> --notice <id> --replay`.

Ollama / Qwen is not part of this measurement path. The separate, implemented desk assessment step uses cutoff-safe evidence bundles and bounded public-document research; it does not require Chroma.

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

Progress is on stderr and in `scenarios/<id>/collect_progress.json` (source, window, day, AOI, tile, bytes, elapsed, stalled). When NASA reports granule size the CLI draws a bar: `viirs incident 101/141 2021-02-27 RUS-dzhankoi h21v04 [############............] 50% 11.2/22.5MB`. The desk polls `GET /api/collection/progress`. JSON results stay on stdout. Use `--quiet` to suppress stderr only. VIIRS reuses cached granules and times out a hung NASA download after five minutes. HDF5 tiles stay on disk through collection so a fix-and-recollect does not re-download NASA. After `wsd corpus review --scenario <id>` is not `no_go`, `wsd corpus prune-viirs --scenario <id>` can free the cache. Independent sources harvest in parallel (default four at a time). `--source-workers 1` restores one-source-at-a-time.

Operator expectations:

- GDELT downloads 96 fifteen-minute English `export` zips per day, counts CAMEO talk rows, then discards the zip. A 21-day incident plus 21-day control is about 4,000 files; already-cached days are skipped. Daily counts live under `data/raw/gdelt/`.
- VIIRS requires `uv sync --extra viirs` and `EARTHDATA_TOKEN`. Collection 2 is a 15-arc-second geographic grid (Moscow is tile `h21v03`), retrospectively reconstructed; `available_at` is night + 3 days.
- v1 harvests independent *mechanisms*, not more media clones. Enabled by default: Wikipedia pageviews, GDELT, ICEWS (robustness only; same information domain as GDELT), ALFRED, MOEX, VIIRS, FIRMS, Internet Archive official-host cadence, crt.sh certificate counts, RIPEstat prefixes. OSM, Wikipedia edits, Brent, and Sentinel-1 are implemented but disabled. FIRMS needs a free `FIRMS_MAP_KEY` (quota 5000 transactions / 10 minutes; this harvest is about 6 calls). ICEWS needs `ICEWS_EVENTS_PATH=data/raw/icews/dataverse_files.zip` (the zip is read in place; do not unpack it, and do not commit it). Failures on one source no longer abort the rest of the harvest. X and full news NLP remain paid/heavy. Do not add another media-derived feed until a synchrony/permutation test has run.
- Sentinel-1, if later enabled, is a boring AOI series: mean IW VV backscatter (dB) versus the AOI's own history on comparable ascending passes. It does not detect vehicles. Days without an overpass are unknown, not zero.
- FIRMS is an AOI thermal-count anomaly, not "military thermal activity." The frozen sensor is NOAA-20 VIIRS standard processing (`VIIRS_NOAA20_SP`), which covers April 2018–present. The area API accepts a 1–5 day span (10-day chunks return HTTP 400 and must be `source_down`, not zero). Suomi-NPP FIRMS delivery ceases 1 November 2026; do not use SNPP as the panel instrument. NOAA-21 only starts January 2024, so it cannot cover Ukraine 2022. crt.sh 502/timeout is the same as cloudy: unknown, never a recorded zero.
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

Without `--mock-model`, the command still makes **no model call**. When hard gates pass, it writes the queue and returns `model_pending`. Cloudy VIIRS nights, Sentinel-1 days without an overpass, and incident/control coverage imbalance are **warnings**, not NO-GOs. Other daily sources below their declared coverage gate are critical. MOEX weekends/exchange holidays and ALFRED H.10 holidays (`.` values) or unpublished tail days are `missing` (cannot flag) and do not count against coverage; do not recollect them hoping for a print. ALFRED scoring waits 7 days for the H.10 vintage. Stop at `model_pending` until the owner-run Ollama execution step is implemented.

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

From the repository root, start the desk as one Compose app:

```bash
docker compose up --build
```

Open <http://127.0.0.1:5173>. Left nav: **Notices**, **Anomaly**, **Operations**. Emit notices and build briefs from Operations (or **Build brief** on an alert). The CLI remains for tests and harvests (`docker compose exec agent wsd measure …`). The API is at <http://127.0.0.1:8000/docs>.

Host-only fallback (two terminals):

```bash
uv run python dashboard/server.py --api-only
```

```bash
cd dashboard/web
npm install
npm run dev
```

To serve a production build from Python alone:

```bash
cd dashboard/web && npm run build
uv run python dashboard/server.py
```

Open <http://127.0.0.1:8000>. Use **Result set** to move between scenarios and measurement runs, then switch among:

- **Individual series** for raw values plus trailing and frozen-rhythm z-scores;
- **All series** for aligned small multiples with independent raw-value scales;
- **Combined z-scores** for comparable multi-series time plots; and
- **Z-score scatter** to see where trailing and rhythm baselines disagree.

The server discovers ignored `scenarios/*/measurement/` outputs on each request and never changes them. Older result formats without rhythm fields remain navigable; their rhythm and scatter views state that paired values are unavailable. Treat the viewer as a diagnostic aid only: it does not change `measurement_mode`, make an exploratory result scientific, or turn missingness into a normal observation.

## 6E. Build an evidence packet

The compiler is the live desk path. `knowledge_cutoff` defaults to now and requires both `available_at` and `retrieved_at`. A notice whose episode ended long before it was emitted is a replay, not a live score:

```bash
wsd packet build --scenario ukraine2022 --notice notice-8f9869999a00 --replay
```

`--replay` sets cutoff to 23:59:59 UTC on the episode end date and uses `available_at` only, so a 2026 harvest cannot leak into a 2022 packet. `--as-of 2022-02-12T23:59:59Z` does the same with an explicit clock. Output is `scenarios/<id>/interpretation/<packet-id>/evidence.json` plus `brief.md` and `brief.pdf`. Download the PDF from the notice (**Download PDF**) or `wsd packet pdf --scenario ukraine2022 --notice notice-8f9869999a00`. The sitting product is the intelligence brief (`product` in the JSON): what changed, why it is on the watchlist, competing explanations, collection next. Series-days, z-scores, and reconstructed latency are the evidence layer. Significance on individual items stays `unassigned`. No model, no live search.

Operator actions on a notice (mark as read, re-examine, request more information, ignore, flag incorrect) are a human state machine:

```bash
wsd notice act --scenario ukraine2022 --notice notice-8f9869999a00 --action ack
```

They do not edit trigger facts. **Request more information** (or `wsd packet collect --replay --task harvest --request-context`) runs three packet-scoped jobs from the existing corpus: crisis chronology (30 days), physical refresh (FIRMS/VIIRS/SAR), and official pack (NAVAREA plus **declared UK/US posture** from FCDO travel-advice history, cutoff-filtered; US State live API or last Wayback snapshot at or before cutoff). **Validate cue** is a checklist from the packet (substrate, holes, latency) with no harvest. Jobs write to `interpretation/<packet-id>/collection/` and do not vote in the notice. Posture stays `focused` unless the analyst already chose otherwise. The travel-advice harvest is dated public history, not a live news scrape.

Clicking **Physical posture** or **Official posture** on the brief runs the job *and* returns a collection plan: sources (desk harvest vs analyst search), named AOIs, dates admissible at cutoff, and what would discriminate each hypothesis. Physical posture also searches the Copernicus catalogue for Sentinel-1 GRD and Sentinel-2 L1C granules over those AOIs. It stores pointers (product name, sensing date, knowable-at-cutoff), not scenes, and they do not vote. OSM, NOTAMs and official statements remain analyst search.

**Your assessment** opens the saved notes/editor. Under **Secondary collection**, **Research and draft assessment** uses a cutoff-dated Tavily search plus Ollama (`wsd packet draft --scenario ukraine2022 --notice notice-8f9869999a00 --replay`). The model and server come from `OLLAMA_MODEL` and `OLLAMA_BASE_URL` in `.env`; exported environment values take precedence. No xAI key or hosted-model credits are required. Edit, then save. The machine write-up is a sidecar; it does not vote or overwrite a saved human report. CLI save: `wsd packet report --scenario ukraine2022 --notice notice-8f9869999a00 --notes "…"`.

To draft from already collected material without another Tavily request, add `--no-search`:

```sh
wsd packet draft --scenario ukraine2022 --notice notice-8f9869999a00 --replay --no-search
```

**Evidence admission:** the original 4 September draft admitted undated official
hits, including later material. Those artefacts are preserved as an audit record.
New drafts rebuild a `desk_evidence_v1` bundle: cached search snippets are leads,
not admitted document text. Replay documents need a matching pre-cutoff archive
capture, content hash and recorded retrieval; dates in URLs alone do not suffice.
An old draft is not automatically repaired or regenerated.

`--no-search` performs no network research. It uses the collected item-level
evidence and any versioned documents cached for the same research plan/cutoff;
legacy Tavily snippets are excluded until document verification. Without the flag,
the API performs requirement-led research. Defaults are six queries, six document
attempts per invocation, 12,000 retained characters per document and 180 seconds.
The UI exposes query/document/time controls before drafting (up to 12 queries,
48 document attempts and 600 seconds); these are application limits, not Tavily
credit limits. Each request waits at most 30 seconds, bounded by time remaining.
Failed document retrievals consume attempts; stopping reasons and counts are visible.
YouTube, social video, PDFs, images and URL dates after cutoff are skipped without
consuming that attempt budget. Preferred queries name AOIs and contemporaneous
official/imagery sources first; if those searches return no fetchable leads, a
broader fallback search runs while query budget remains. Outcomes record whether
retained documents are preferred sources or fallback public reporting. Historical
HTML/text is retrieved through exact Wayback captures, including gzip-compressed
captures; binary bodies are rejected. PDFs, imagery interpretation and independent
video geolocation are not implemented. Present-day extraction uses Tavily Extract;
documents retrieved after a fixed packet cutoff are excluded, so live use needs
an appropriately timed packet. This first implementation is qualified offline,
not yet through an owner-run live search/model comparison.

Packet-local `research/` records the plan, requests, results and failures. Reruns
reuse completed requests and do not silently repeat failed or uncertain paid
calls. A rerun can attempt remaining URLs up to its per-invocation allowance;
increasing only document/time limits preserves the same-plan checkpoint. Project-wide `scenarios/.osint_search_index/` also indexes exact Tavily
requests across packets and scenarios. Whitespace/case-normalised query text plus
date window and search options form the request checksum; the complete result list
is stored once under its own content checksum. Checksums are verified on every read
and corruption fails closed rather than spending another credit. An identical
in-flight query is deferred, not duplicated. Cache hits remain usable without an
API key; a cache miss without a key is deferred for an explicit later retry.

Search results remain discovery leads and are not placed in the model prompt.
Only separately admitted, versioned documents can enter the evidence input, so
indexing results saves search credits without turning duplicated snippets into
corroboration. A process crash may leave a `.lock`; inspect API logs and request
state before manually clearing a confirmed stale lock. Research does not edit the
measurement or original packet. Search snippets and publication dates are not
substitutes for reviewing the underlying document version.

`evidence_bundles/` contains immutable, content-addressed inputs; `draft_runs/`
contains the exact system/user prompt and raw response per attempt. Both are
ignored by Git, like machine drafts. Selection prioritises the cue, official
events, physical observations and admitted documents before catalogue/chronology
records, with a 60,000-character item budget. Every omission is listed, not silently
treated as absence. Legacy dated official events retain their collector provenance;
they are not labelled independently verified. Catalogue pointers are not scene analysis.

The complete evidence bundle remains the audit and source-review object. Ollama receives
a separate `desk_model_input_v1` projection capped at 32,000 characters. Repeated metadata
is removed and evidence classes are selected round-robin so a long numeric series cannot
crowd out official, physical, documentary or contradictory material. The prompt records
the full, selected and unselected item counts plus both content-addressed IDs. This is a
deterministic first retrieval layer, not semantic RAG; source passages remain available
from the full bundle in the review UI.

Admitted documents are stored in full in the packet evidence bundle and in a
content-addressed passage index (`scenarios/.document_index/`). Drafting embeds
those passages with local Ollama (`OLLAMA_EMBED_MODEL`, default `mxbai-embed-large`)
and puts the retrieved slices in the model view with the parent evidence ID,
character offsets and source URL. The review bundle is the citation source; a
passage that was not retrieved is not evidence of absence. If embeddings are
unavailable, lexical overlap is used. qwen3.8:27b-mlx lists a 256K context; the
desk still sends a compact retrieved view rather than whole pages, so `OLLAMA_NUM_CTX`
need only exceed the prompt plus `OLLAMA_MAX_OUTPUT_TOKENS`.

The compact model output includes one short summary, claim/evidence IDs, supporting quotations, proposed changes
for every hypothesis and a collection decision. Unknown IDs, quotations absent
from the referenced text, missing hypotheses and unrecognised citation URLs are
flagged. Passing these checks does not prove factual truth, entailment, source
independence or full grounding of every prose sentence. `--apply` requires the
reference checks to pass as well as an empty report and no language-review flags.
The analyst can always edit and explicitly save their own assessment.

### Finish an assessment and brief in the UI

In **Notes & assessment**, the latest source-linked review (including CLI-generated drafts) loads alongside saved analyst decisions.

1. Inspect each finding's passages and the proposed hypothesis revisions. **Accept finding** saves it for assessment. **Edit proposal** saves your revised wording; rejection, editing and unresolved decisions require a reason. Decisions survive navigation and reopening. Saved proposals collapse to a status summary; open them to revisit. Numbered links guide you through review, preview, editing/saving and brief preparation. A changed draft invalidates the old decisions even if its evidence bundle ID is unchanged; history remains available.
2. **Preview reviewed material → Merge reviewed material into assessment** builds a cited starting point from retained proposals. The merge updates a marked review section; writing outside that section is preserved. Updating an existing section asks before replacing edits inside it. The original **Use machine draft** option imports the unfiltered draft and does not apply review decisions.
3. Add your key judgement, implications, alternatives, uncertainty and next questions, then **Save assessment**. Collection recommendations do not themselves run searches: use the Secondary collection source jobs and Research and draft assessment action when more evidence is needed, then review the new version.
4. **Download assessment PDF** (also Markdown/HTML) on **Your assessment** is the desk product for intelligence colleagues: saved notes plus the evidence/review annex. It is not the senior-leadership brief.
5. **Prepare new brief version** calls the configured Ollama model for editorial synthesis: BLUF (maximum two sentences), analytical confidence and its rationale, source assessment, key judgements, significance, alternatives/uncertainty and outlook. It uses the saved assessment, retained proposals and review limitations, and makes no new searches. Input references are checked mechanically, not for semantic entailment, and are not printed as `[A1]` codes in the leadership product. Preview it, use **Edit brief wording** if needed, then **Save revised brief** to create a new unsigned version before sign-off. Failed/incomplete outputs are retained under `brief_runs/` and do not replace existing versions. Assessment changes during generation prevent stale output being published.
6. Review all proposals (explicitly unresolved with a reason is allowed), enter your name and confirm the assessment/source checks, then **Sign off this version**. Download the brief as Markdown, printable HTML or PDF. Neither signing nor downloading distributes the brief.

Decisions, history and briefing versions persist in the notice's report directory as `workflow.json`, alongside `report.json` and `report.md`. `GET/POST /api/analyst-workflow` uses revision checks to reject conflicting writes. Changed saved notes or review decisions mark existing briefs stale; prepare and sign off a new version. Brief contents retain their original snapshot, including evidence and caveats. Unsaved editor changes must be saved before preparation or sign-off.

To test again, expand **Reset assessment for a fresh test → Reset assessment**. Confirming clears saved notes, review decisions, active briefs and this browser's drafts. Prior saved state is copied under `resets/`; source evidence, research and machine proposals remain available. Nothing is reset until you press the button. Individual briefs have **Remove version** under Versions and exports; removal hides them from active exports while retaining the audit record. A reset is not secure erasure and does not clear drafts on other browsers.

This completes the local review-to-export path. Adaptive research follow-up, measured labour savings and retrospective qualification across independent cases remain roadmap work; a signed-off local brief is not evidence those gates have passed.

The [native Ollama chat API](https://docs.ollama.com/api/chat) is used with JSON output,
model-token streaming and thinking disabled, temperature 0, and seed 42.
If the backend explicitly rejects structured output with HTTP 501 and
`structured output is unavailable`, the API resubmits once without `format`.
The prompt still requires JSON and the same structure validation applies before
saving. The sidecar records `output_mode` as `native_json` or `prompt_json`.
Timeouts and other failures never trigger this compatibility resubmission. Desk limits default to
900 seconds, 4096 output tokens, and 32768 context tokens; override them with
`OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_MAX_OUTPUT_TOKENS`, and `OLLAMA_NUM_CTX`.
The model is not asked to repeat its answer as free-form notes, duplicate sections and
a claim ledger. Markdown notes are rendered deterministically from the compact response.
Malformed, empty, and token-truncated output is rejected before replacing draft files.
On an explicit token-limit stop, `draft_runs/<attempt>/rejected_completion.json` retains
the partial response and timing counters. It is never continued or applied automatically;
inspect it before deliberately raising the output limit and retrying.
Prompt-only JSON can occasionally leave quotation marks unescaped. The parser does
not run a general or model-assisted repair. It repairs a malformed evidence-quotation
line only when the cited evidence ID exists and one longest interpretation occurs
verbatim in that admitted record. The untouched raw completion and repair metadata
are retained, and any repaired draft remains `needs_review` and cannot auto-apply.
When a completed response was rejected and an explicit rerun has the same prompt
hash and model, the API revalidates that retained completion instead of invoking
Ollama again. A changed prompt or model always requires a new generation.
Section values returned as lists or objects are deterministically rendered as
Markdown before schema validation (for example, hypotheses as labelled records
and findings as bullet lists). Existing Markdown strings are unchanged. The raw
model response and the names of converted sections are retained in the sidecar;
format conversion does not validate the model's factual claims. Empty structures
do not count as an assessment. Cutoff-language checks cover both notes and sections.
The sidecar records raw model text, prompt hash, provider/model, generation settings,
and available Ollama timing metrics. This does not establish semantic correctness;
the analyst still reviews grounding, alternative explanations and cutoff compliance.
The frozen interpretation protocol and its settings are unchanged.

The host `wsd packet draft` command submits to `POST /api/packet/draft/stream`;
its final JSON reports the prompt character/item budget, configured output-token limit,
and search/document requests made by that invocation (cached requests report zero).
The UI **Research and draft assessment** action also consumes the streaming endpoint.
`POST /api/packet/draft` remains available for JSON API clients.
Both run the same server-side drafting function. The CLI uses `WSD_API_BASE_URL` (default
`http://127.0.0.1:8000`), not `OLLAMA_BASE_URL`. Start the Docker stack first.
The CLI reads its API settings from the project `.env`, with exported values
taking precedence. `WSD_API_TIMEOUT_SECONDS` defaults to 1800 seconds. It does
not retry or fall back to local generation: after a timeout, check API logs and
draft artefacts before resubmitting because server work may still be running.
Returned artefact paths are server paths. Other CLI commands remain unchanged.
Compose sets the agent container's API URL to `http://api:8000`, so the same
draft command can be run there too (recreate an existing agent to pick this up).

The CLI shows a job ID, completed-stage bar, current activity and elapsed time
on stderr. Stages are preparation, search/context, generation, validation and
saving. For example: `Job-abc123 [########............] 2/5 stages | Ollama generating · 1m 04s`.
The stage bar is **not a percentage of generation or remaining time**. The API
sends heartbeats every two seconds while waiting on the model; this confirms the
API request is still active, not that the model is making tokens. Non-terminal
logs print each changed stage and a heartbeat every 30 seconds. `--quiet`
suppresses progress; stdout remains the final JSON summary. Ctrl-C stops watching,
not server work. These are request IDs, not durable/resumable queued jobs.

The API container owns model configuration and must reach Ollama:
`localhost` refers to the container, not the Mac. Set `OLLAMA_BASE_URL` in the API
container environment to `http://host.docker.internal:11434` (or your reachable
Ollama server) and recreate that container after changing its environment.
Host-shell `OLLAMA_*` overrides do not change the running API's configuration.

In the UI, generated text appears as **Machine draft ready for review**. Preview
it, then choose **Use machine draft** or **Keep my assessment**. Replacing existing
editor text requires confirmation; the saved report changes only when you save it.

## 7. Run the whole pipeline

Backtest path (validate, collect, review, exploratory measure, emit on a closed window). This is not the live watch:

```bash
wsd run workflow --scenario ukraine2022
```

`--mock` is a synthetic rehearsal and stops after review (measurement refuses a
mock harvest). Resume after an existing collect with `--from review`. Stop early
with `--through collect` or `--through review`.

The older experiment harness still exists for parent/child run IDs:

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
| Desk assessment | Public-source research and Ollama proposals | Review sources, retain/edit findings, save assessment, prepare a brief | Human review and sign-off; separate from scientific interpretation experiments |

The “ball” is always either with the system (a command is running) or the operator (a named file must be reviewed). There is no automatic jump from corpus collection to scientific analysis.


### Briefing presentation standards

Notice overviews show BLUF, analytical confidence and source limitations near the top. The displayed notice BLUF is a concise extract of its existing assessment plus its collection purpose, not a new model judgement. Source identity does not establish reliability; provenance, corroboration and misinformation remain explicit assessment questions. Notice PDFs and newly generated Markdown use the same presentation.

On first use, likelihood terms display the approximate ranges in the [published PHIA Probability Yardstick](https://www.gov.uk/government/publications/explaining-uncertainty-in-uk-intelligence-assessment/explaining-uncertainty-in-uk-intelligence-assessment). These explain language rather than numerical model probabilities. Analytical confidence remains separate. New editorial briefs must include a maximum two-sentence BLUF and prominent confidence/source assessments; regenerate an existing brief to apply the new model contract. Saved versions and trigger facts are not retroactively rewritten.
