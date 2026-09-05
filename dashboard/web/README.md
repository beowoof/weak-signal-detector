# Analyst workspace UI

**Reviewed 2026-09-05.** Current UI workflow; see Secondary collection below for the entry point and source-job sequence.

## Secondary collection

A notice has one tab row (Overview, Evidence, Collection, Notes & assessment) and a separate **Notice actions** menu. Notes & assessment is four stages; only the selected stage is shown: review findings, retained findings, your assessment, intelligence brief. **Prepare new brief version** reports running, failure and completion, including while you are on another stage.

On a notice, click **Secondary collection**. The Collection tab has one sequence:

1. **Start secondary collection:** select government actions, satellite availability/recorded observations, chronology and/or public reporting leads. The source descriptions say what each job actually does. Starting these jobs does not invoke Ollama.
2. **Review collection results:** returned status, explanation and last-run timestamp are visible immediately. Detailed results and cue validation are expandable.
3. **Research and draft assessment:** document retrieval/checks and Ollama drafting are a separate action. Research limits sit here, with streamed elapsed time/activity and explicit stopping reasons. Review proposals and save judgement under Notes & assessment, then prepare the final brief there.

The defaults remain 6 queries, 6 document attempts and 180 research seconds. UI controls allow up to 12 queries, 48 attempts and 600 seconds. Failed retrievals count; model time is additional. Limits do not reflect Tavily credit balance and do not control the earlier connector jobs. Research results distinguish total recorded requests from new requests in this invocation.

The mocked `node tests/machine-draft-smoke.cjs` suite exercises this path, including source selection and immediate result display, and prevents real collection/model POSTs. `node tests/brief-workflow.cjs` checks the four-stage assessment path and brief-preparation status. Set `WSD_UI_URL` to the test UI; use `NODE_PATH` if Playwright is installed outside this package. See [the documentation checkpoint](../../DOCUMENTATION_STATUS.md).

## Scenarios and collection artefacts

Open **Scenarios** in the top navigation. All scenario files are listed, including
those without measurement runs. **Scenario editor** offers common fields and an
Advanced JSON editor for the full contract. Validation uses the existing scenario
schema; incomplete but valid draft scenarios show collection-readiness warnings.
Saved JSON preserves additional fields. Scenario IDs cannot be renamed here.

Drafts are retained per scenario in the browser, including across reloads when
local storage is available. Saves compare a content revision before atomically
replacing `scenario.json`; a changed file produces a conflict rather than an
overwrite. Use **Reload from disk**, copy/reconcile the draft, then discard it if
you want the on-disk version. Frozen contracts are read-only. Saving does not
start a collection, reset lifecycle state, or regenerate existing artefacts.

**Collection artefacts** provides a searchable stage/run file browser:

- `missing.json` and review files: recorded gaps by source, severity, window,
  reason and requested follow-up.
- Collection manifests: recorded coverage, expected/OK/missing/source-down
  counts, mode, provenance and observation links. Not-applicable sources remain
  distinct from observations; legacy missing counts display as unknown.
- JSONL observations and measurement files: 100-record pages, field-selectable
  plots where dated numeric values exist, and raw records. Charts cover only
  the current page; null values are not replaced with zero.
- Other JSON and Markdown artefacts: structured inspection and raw text.

Previews are bounded to 1 MB. Large previews are explicitly labelled as partial;
**Download original** returns the complete file. Artefact browsing is read-only
and restricted to files under the selected scenario. Source-side public API keys
are not required for browsing already collected local artefacts.

Additional verification:

```sh
.venv/bin/python -m pytest tests/test_scenario_workspace_api.py tests/test_dashboard.py
```

From `dashboard/web`, with Playwright and Chrome available, run
`node tests/scenarios-smoke.cjs`. The browser suite uses the existing Ukraine
and German scenarios, real read-only artefacts and validation, and mocked saves;
it verifies that the real scenario remains unchanged.

The Docker web service serves this React frontend on port 5173. Source edits are
live-mounted; reload the browser to open the updated workspace. The scenario API
adds validated contract saves and read-only artefact access; measurement rules
and existing stored reports are unchanged.

- **Desk:** searchable notice queue and independently scrolling notice workspace.
  Overview leads with the cue and generated brief. Evidence, collection tasks,
  and human notes each have their own tab. On small screens, select a notice
  from the queue and use **← Notices** to return.
- **Explorer:** independent result browsing without a notice's notes or highlights.
- **Operations:** existing notice emission and brief-building controls.

Notice, section, workspace, and Explorer result are represented in the URL for
links, reload, and browser back/forward. Chart visibility survives background
polling. Chart controls reset when moving to a different result or notice.

Assessment drafts are keyed by notice and retained in browser local storage.
They are not saved to the server until **Save assessment** succeeds. A failed
save retains the draft. **Discard draft** requires confirmation and never deletes
the saved assessment. Browser storage failure falls back to session memory;
reload will lose a session-only draft. Drafts are specific to this browser.

## Verification

```sh
cd dashboard/web
npm test
npm run build
```

With the existing Docker image, the source-only unit tests and build can also run
without rebuilding the image:

```sh
docker compose exec -T web node --test src/lib/workspace.test.js
docker compose exec -T web npm run build
```

The optional browser smoke test requires Playwright resolvable by Node (an
existing installation via `NODE_PATH` also works) and installed Google Chrome:

```sh
cd dashboard/web
npm run test:ui
```

It uses a disposable browser context. All writes are intercepted: report saving
is simulated, and other POST requests are blocked. The running desk needs two
notices with briefs and a German control result for cross-scenario checks. Set
`WSD_UI_URL` for a different local URL, or `WSD_UI_SCREENSHOT` for a final screenshot.
The suite covers independent scrolling, collapsed collection, keyboard tabs,
polling, per-notice drafts, reload, save failure/success, Explorer isolation,
browser back, Operations selection, and 1024/390/360px layouts.
