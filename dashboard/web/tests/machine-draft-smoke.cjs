const assert = require("node:assert/strict");
const { chromium } = require("playwright");

// No real collection, generation or report writes: every POST is mocked or blocked.
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    let requests = 0;
    const reviews = new Map();
    const workflows = new Map();
    const reports = new Map();
    function workflow(id) {
      if (!workflows.has(id)) workflows.set(id, { revision: 0, review_version: "fixture", active_decisions: {},
        decisions: {}, events: [], briefs: [], stale_decisions: 0, assembly: "## Reviewed findings\n- A source-backed proposed finding. [Sources: ev-test]" });
      return { ...workflows.get(id), review: reviews.get(id) || null };
    }
    const reply = (route, data) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
    await context.route("**/*", (route) => {
      const req = route.request();
      if (req.url().includes("/api/analyst-workflow")) {
        if (req.method() === "GET") return reply(route, workflow(new URL(req.url()).searchParams.get("notice_id")));
        const body = req.postDataJSON(), state = workflow(body.notice_id);
        state.revision += 1;
        if (body.action === "review") {
          state.active_decisions[body.proposal_id] = { status: body.status, reason: body.reason, text: body.text };
          state.events.push(body);
        } else if (body.action === "prepare") {
          state.briefs.push({ version: state.briefs.length + 1, title: body.title, created_at: new Date().toISOString(),
            body: "## Key judgements\nEditorial synthesis [A1]", editorial: { model: "mock" },
            markdown: "## Key judgements\nEditorial synthesis [A1]", stale: false, signed_off: null });
        } else if (body.action === "sign_off") state.briefs.at(-1).signed_off = { reviewer: body.reviewer };
        if (body.action === "revise_brief") state.briefs.push({ ...state.briefs.at(-1), version: state.briefs.length + 1,
          body: body.text, markdown: body.text, signed_off: null });
        if (body.action === "remove_brief") state.briefs = state.briefs.filter(b => b.version !== body.version);
        if (body.action === "reset") {
          state.active_decisions = {}; state.decisions = {}; state.briefs = [];
          state.report = { notes: "", empty: true, updated_at: new Date().toISOString() };
          reports.set(body.notice_id, state.report);
        }
        workflows.set(body.notice_id, state);
        return reply(route, state);
      }
      if (req.url().includes("/api/report")) {
        if (req.method() === "POST") {
          const body = req.postDataJSON();
          const report = { notes: body.notes, empty: false, updated_at: new Date().toISOString() };
          reports.set(body.notice_id, report);
          return reply(route, report);
        }
        const report = reports.get(new URL(req.url()).searchParams.get("notice_id"));
        if (report) return reply(route, report);
      }
      if (req.method() === "GET" && req.url().includes("/api/packet/draft/review?")) {
        const id = new URL(req.url()).searchParams.get("notice_id");
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ review: reviews.get(id) || null }) });
      }
      if (["GET", "HEAD", "OPTIONS"].includes(req.method())) return route.continue();
      if (req.url().endsWith("/api/packet/draft/stream")) {
        assert.equal(req.postDataJSON().research_limits.documents, 6);
        requests += 1;
        const review = {
          bundle_id: `fixture-${requests}`, status: "references_checked", proposed_decision: "collect_more",
          notice: "Reference checks do not establish factual truth.", issues: [], excluded: [], omitted: [],
          initial_cue: { fixed: true }, cautions: ["Catalogue pointers are not imagery interpretation"],
          evidence: [{ id: "ev-test", kind: "document", verification: "versioned_document",
            source_ref: "fixture", available_at: "2022-02-11", data: { url: "javascript:alert(1)", text: "<script>window.reviewInjected=true</script> Source passage." } }],
          claims: [{ claim_id: "claim-1", statement: "A source-backed proposed finding.", evidence_ids: ["ev-test"],
            quotes: { "ev-test": "Source passage." }, reference_check: "references_match" }],
          hypothesis_updates: [{ hypothesis: "routine_variation", change: "lowered", rationale: "Proposed change with a source.", supporting_evidence: ["ev-test"] }],
        };
        reviews.set(req.postDataJSON().notice_id, review);
        return route.fulfill({ status: 200, contentType: "application/x-ndjson", body: JSON.stringify({type: "progress", stage: "Checking source", elapsed_s: 1}) + "\n" + JSON.stringify({type: "result", result: {
          notes: `Mock machine draft ${requests}`, provider: "ollama", model: "mock", leakage: [], votes: false, review,
        }}) + "\n" });
      }
      return route.abort();
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(process.env.WSD_UI_URL || "http://127.0.0.1:5173", { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: "Notes & assessment", exact: true }).click();
    await page.getByRole("button", { name: /^(Edit|Write) assessment$/ }).click();
    const editor = page.getByLabel("Your notes and assessment", { exact: true });
    await editor.fill("My unsaved assessment");
    await page.getByRole("button", { name: "Machine draft", exact: true }).click();
    await page.getByRole("heading", { name: "Machine draft ready for review" }).waitFor();
    assert.equal(await editor.inputValue(), "My unsaved assessment");
    const reviewPanel = page.getByRole("region", { name: "Evidence and assessment review" });
    await reviewPanel.getByText("A source-backed proposed finding.", { exact: true }).waitFor();
    await reviewPanel.getByRole("button", { name: "Accept finding" }).first().click();
    assert.equal(await editor.inputValue(), "My unsaved assessment", "Review marks must not edit notes");
    const acceptedCard = reviewPanel.locator(".proposal-card").first();
    await acceptedCard.getByText(/Saved · Open to revisit/).waitFor();
    assert.equal(await acceptedCard.evaluate(el => el.open), false, "Saved review should collapse");
    assert.equal(await reviewPanel.locator('a[href^="javascript:"]').count(), 0);
    assert.equal(await page.evaluate(() => Boolean(window.reviewInjected)), false);
    await page.getByRole("button", { name: "Preview reviewed material", exact: true }).click();
    await page.getByRole("button", { name: "Merge reviewed material into assessment", exact: true }).click();
    assert.match(await editor.inputValue(), /My unsaved assessment/);
    assert.match(await editor.inputValue(), /Sources: ev-test/);
    await page.getByRole("button", { name: "Save assessment", exact: true }).click();
    await page.reload({ waitUntil: "networkidle" });
    await page.getByText(/Saved · Open to revisit/).first().waitFor();
    await page.getByRole("button", { name: "Edit assessment", exact: true }).click();
    await editor.fill("My unsaved assessment");
    // Recreate the import offer after reload; no real model call is made.
    await page.getByRole("button", { name: "Machine draft", exact: true }).click();
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("button", { name: "Use machine draft", exact: true }).click();
    assert.equal(await editor.inputValue(), "My unsaved assessment");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Use machine draft", exact: true }).click();
    assert.equal(await editor.inputValue(), "Mock machine draft 2");
    await editor.fill("Human revision of draft");
    await page.locator(".alert-row").nth(1).click();
    await page.locator(".alert-row").first().click();
    assert.equal(await editor.inputValue(), "Human revision of draft", "Remount must not reapply seed");
    await page.getByRole("button", { name: "Machine draft", exact: true }).click();
    await page.getByRole("heading", { name: "Machine draft ready for review" }).waitFor();
    await page.getByRole("button", { name: "Keep my assessment", exact: true }).click();
    assert.equal(await editor.inputValue(), "Human revision of draft");
    // Finish the assessment and brief; every write remains mocked.
    const currentReview = page.getByRole("region", { name: "Evidence and assessment review" });
    await currentReview.locator("details").evaluateAll(items => items.forEach(el => { el.open = true; }));
    for (const card of await currentReview.locator(".proposal-card").all()) {
      await card.evaluate(el => { el.open = true; });
      const button = card.getByRole("button", { name: "Accept finding", exact: true });
      // Hypothesis controls live inside collapsed details.
      await button.evaluate(el => { let p = el.parentElement; while (p) { if (p.tagName === "DETAILS") p.open = true; p = p.parentElement; } });
      await button.click();
    }
    await page.getByRole("button", { name: "Save assessment", exact: true }).click();
    await page.getByRole("button", { name: "Prepare new brief version", exact: true }).click();
    await page.getByLabel("Reviewer name", { exact: true }).fill("Test analyst");
    await page.getByRole("checkbox").last().check();
    await page.getByRole("button", { name: "Sign off this version", exact: true }).click();
    await page.getByRole("heading", { name: "Brief signed off", exact: true }).waitFor();
    await page.getByText("Versions and exports (1)", { exact: true }).click();
    assert.equal(await page.getByRole("button", { name: "Markdown" }).count(), 1);
    await page.getByRole("button", { name: "Edit brief wording", exact: true }).click();
    await page.getByLabel("Brief wording", { exact: true }).fill("## Key judgements\nAnalyst-edited editorial brief [A1]");
    await page.getByRole("button", { name: "Save revised brief", exact: true }).click();
    await page.getByRole("heading", { name: "Brief ready for review", exact: true }).waitFor();
    await page.getByText("Versions and exports (2)", { exact: true }).evaluate(el => { el.parentElement.open = true; });
    page.once("dialog", d => d.accept());
    await page.getByRole("button", { name: "Remove version 2", exact: true }).click();
    await page.getByRole("heading", { name: "Brief signed off", exact: true }).waitFor();
    await page.getByText("Reset assessment for a fresh test", { exact: true }).click();
    page.once("dialog", d => d.accept());
    await page.getByRole("button", { name: "Reset assessment", exact: true }).click();
    await page.getByText("No saved assessment", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Markdown" }).count(), 0);
    await page.reload({ waitUntil: "networkidle" });
    await page.getByText("No saved assessment", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Write assessment", exact: true }).count(), 1);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await page.screenshot({ path: "/tmp/wsd-workflow-mobile.png", fullPage: true });
    assert.equal(requests, 3);
    assert.deepEqual(errors, []);
    console.log("PASS: persisted review, merge, reload, assessment save, brief sign-off/export, mobile layout and protected edits.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
