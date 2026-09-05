# Documentation checkpoint — 2026-09-05

## Current operator path

1. Open a notice in **Desk**, then click **Secondary collection**.
2. Choose source jobs and click **Start secondary collection**. Government actions retrieve public advice changes; satellite jobs inspect catalogues and assemble existing observations; chronology assembles recorded series; public-reporting search returns leads. These jobs do not run Ollama or produce the final brief.
3. Inspect returned statuses, explanations and last-run timestamps immediately below. A returned job is not necessarily successful or complete. Detailed source results and cue validation remain expandable.
4. **Research and draft assessment** retrieves/checks documents, combines them with collected evidence and invokes Ollama. Query, document-attempt and time controls sit beside this action. Review findings in **Notes & assessment**, retain/edit proposals, add judgement and save.
5. **Prepare new brief version** synthesises the saved assessment and retained material. It makes no new searches. Review/amend, sign off and export the desired version. Export does not distribute it.

Source jobs in step 2 have their own connector behaviour; the document-research controls in step 4 do not govern those jobs. Whole-run background execution, automatic adaptive follow-up and continuous live monitoring remain future work.

## Research limits and failure visibility

Defaults: 6 queries, 6 document attempts per invocation, 180 seconds of research and 12,000 retained characters per document. UI/API ranges are 1–12 queries, 1–48 document attempts and 1–600 seconds; the UI offers presets within those ranges. Each request waits at most 30 seconds, bounded by time remaining. Ollama time is separate. These application limits are unrelated to Tavily's account balance, which the application does not inspect.

Failed retrievals consume document attempts. YouTube, social video, PDFs, images and post-cutoff URL dates are skipped without consuming attempts. Preferred queries and official/imagery domains are tried first; a broader fallback search runs only when those leads are unusable, and outcomes label fallback reporting as such. Repeating a plan can try remaining URLs with a fresh per-run allowance while skipping previously attempted URLs. Changing only document/time limits preserves the checkpoint. Changing the query plan can create a different research record; exact Tavily requests still use the shared search cache. Uncertain model completions and paid requests are not automatically retried. Gzip-compressed archive captures are decompressed; binary bodies are not admitted.

The UI streams actual stages and elapsed time, retains the run activity, and displays stopping reason, cumulative counts, this-run counts, failed retrievals and unattempted questions. The assessment model and editorial brief receive per-question collection outcomes: obtaining a document is distinct from answering the question. A replay archive failure is not evidence that no contemporaneous reporting existed.

A later Ukraine replay (8 queries, 18 document attempts) admitted five documents, including pre-cutoff GOV.UK travel-advice captures and Washington Post embassy/force-movement reporting. Earlier 0-document snapshots remain on disk. Drafting now indexes admitted documents as passages and retrieves cited slices for the model; the review bundle keeps the full text. Map-reduce generation was not used.

The inspected historical Ukraine run of 5 September attempted six documents in 50.97 seconds, obtained zero admissible documents, recorded six “No usable pre-cutoff archive capture” failures and stopped at its document-attempt limit. It did not exhaust its 180-second allowance; Tavily credits were not checked. That snapshot is not the current retrieval behaviour.

## Analytical and sensor changes

Brief synthesis preserves concrete evidence, counterevidence, the analyst's current judgement and both directions of change indicators. Earlier packet context and retained machine material are labelled separately. Substantive analysis precedes concise confidence/source sections. Direct imagery is not a prerequisite for an OSINT judgement; indirect evidence must still support the inference. Reference/shape checks do not prove semantic faithfulness.

The deterministic packet compiler no longer raises explanatory confidence merely because VIIRS/FIRMS data is present. New VIIRS collection records cloud-mask rejection, quality rejection, fill values, absent granules and retrieval failures separately, while keeping reconstructed availability latency distinct. Older records cannot acquire an unrecorded cause retrospectively. No measurement protocol, saved assessment or historical brief is silently rewritten by these changes.

## Markdown review inventory

| File/group | Disposition |
|---|---|
| README.md | Current implementation, entry points and regeneration boundaries reconciled |
| HOWTO.md | Current source collection, research limits, streaming and assessment workflow reconciled |
| dashboard/web/README.md | Secondary-collection sequence and current UI verification documented |
| ROADMAP.md | Implemented local path separated from outstanding qualification and live orchestration |
| CHANGELOG.md | Session changes recorded; obsolete present-tense claims corrected |
| FINDINGS.md | Historical detector verdict preserved and clearly scoped |
| COUPLING_EVALUATION.md, EWS_EVALUATION.md | Historical numerical evaluations preserved; no new results claimed |
| IDEAS.md | Proposal status clarified and unsupported significance/tone wording corrected |
| weak-signal-fusion-spec.md | Original design/date preserved, current implementation pointers clarified |
| data/fixtures/README.md | Synthetic-only boundary reviewed; fixture data unchanged |
| brief-editorial-example.md | Example/reference mapping preserved; not represented as a model or collection result |
| scenarios/*/interpretation/* | Local runtime products (packets, briefs, collection, drafts). Not tracked in git |
| scenarios/*/notices/* | Local notice workflow state. Not tracked in git |

Generated records can contain older phrasing. Rewriting them to match today's documentation would erase what the system actually produced. Use the explicit collection/draft/brief actions to produce new results.

## Verification and loading changes

The session's last complete offline Python run passed 321 tests (one skipped, three live/model tests deselected). Frontend unit tests passed 13 tests. The frontend production build and mocked browser workflow passed; the latter verifies source selection, a collection POST, visible returned results, no model call during source collection, and the subsequent assessment/review/brief flow. These are engineering checks, not proof of analytical quality. No live collection or Ollama generation was performed by those checks.

For the source-mounted Docker stack, restart the API after backend changes (`docker compose restart api`) and reload the UI. Rebuild containers when dependencies change. Static deployments must serve a rebuilt frontend. Loading new code does not regenerate existing briefs.
