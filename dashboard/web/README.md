# Analyst workspace UI

The Docker web service serves this React frontend on port 5173. Source edits are
live-mounted; reload the browser to open the updated workspace. No backend,
measurement rules, or stored reports are changed by this UI refactor.

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
