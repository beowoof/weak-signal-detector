import test from "node:test";
import assert from "node:assert/strict";
import { readRoute, routeSearch, workflowLabel, noticeTitle, draftKey, briefProduct } from "./workspace.js";
import { readDraft, writeDraft, clearDraft } from "./drafts.js";

test("workspace deep links round-trip notice, tab and independent result", () => {
  const route = { surface: "anomaly", tab: "notes", step: "", notice: "notice/a&b", result: "deu2018quiet/measure-x" };
  assert.deepEqual(readRoute(routeSearch(route)), route);
});
test("assessment step is part of the notice route", () => {
  const route = { surface: "notices", tab: "notes", step: "brief", notice: "notice-1", result: "" };
  assert.deepEqual(readRoute(routeSearch(route)), route);
});
test("invalid sections fall back to the desk overview", () => {
  assert.deepEqual(readRoute("?view=unknown&tab=bogus"), { surface: "notices", tab: "overview", step: "", notice: "", result: "" });
});
test("explicit links take precedence over remembered choices", () => {
  const storage = { getItem: () => "remembered" };
  assert.equal(readRoute("?notice=linked", storage).notice, "linked");
  assert.equal(readRoute("", storage).notice, "remembered");
  assert.equal(readRoute("?notice=linked", storage).step, "");
});
test("triage labels expose readable workflow without changing its value", () => {
  assert.equal(workflowLabel("in_packet"), "Evidence ready");
  assert.equal(workflowLabel("context_requested"), "Context requested");
  assert.equal(noticeTitle({ scenario_id: "ukraine2022" }), "ukraine · 2022");
});
test("draft storage is scoped by notice", () => {
  assert.notEqual(draftKey("notice-one"), draftKey("notice-two"));
});
test("draft survives notice navigation even when persistent storage is full", () => {
  const unavailable = { getItem() { throw Error("denied"); }, setItem() { throw Error("quota"); }, removeItem() { throw Error("denied"); } };
  assert.equal(writeDraft("quota-test", "Keep this assessment", unavailable), false);
  assert.equal(readDraft("quota-test", unavailable), "Keep this assessment");
  assert.equal(readDraft("another-notice", unavailable), null);
  clearDraft("quota-test", unavailable);
  assert.equal(readDraft("quota-test", unavailable), null);
});
test("brief preview is the editorial product, not the working assessment annex", () => {
  assert.equal(briefProduct({
    body: "## BLUF\n\n- Condensed takeaway.",
    markdown: "# Title\n\n## BLUF\n\n- Condensed takeaway.\n\n## Editorial input references\n\n### Analyst working assessment\n- The saved notes.",
  }), "## BLUF\n\n- Condensed takeaway.");
  assert.equal(briefProduct({
    editorial: { body: "## BLUF\n\n- From synthesis." },
    markdown: "### Analyst working assessment\n- Notes",
  }), "## BLUF\n\n- From synthesis.");
  assert.equal(briefProduct({
    markdown: "# Brief\n\n## BLUF\n\n- Product.\n\n## Editorial input references\n\n### Analyst working assessment\n- Notes",
  }), "# Brief\n\n## BLUF\n\n- Product.");
  assert.equal(briefProduct({ markdown: "### Analyst working assessment\n- Notes only" }), "");
});
test("brief preview strips editorial input codes that are not in the document", () => {
  assert.equal(briefProduct({
    body: "## BLUF\n\n- Takeaway [A3, A20]\n\n## Key judgements\n\n- Detail [A5, P1, R3].",
  }), "## BLUF\n\n- Takeaway\n\n## Key judgements\n\n- Detail.");
});

test("investigation journey names the actual next step and does not assume readiness", async () => {
  const { investigationNext: next } = await import("./workspace.js");
  assert.equal(next({}).tab, "evidence");
  assert.match(next({ packet: {} }).detail, /unavailable or loading/);
  assert.equal(next({ packet: {}, workflow: { briefs: [] } }).tab, "collection");
  assert.equal(next({ packet: {}, workflow: { review: {}, briefs: [] } }).step, "review");
  const workflow = { report: { empty: false }, briefs: [{ version: 1, signed_off: {} }] };
  assert.equal(next({ packet: {}, workflow }).label, "Open intelligence brief");
  assert.equal(next({ packet: {}, workflow, dirty: true }).step, "assessment");
  workflow.briefs[0].stale = true;
  assert.equal(next({ packet: {}, workflow }).label, "Prepare intelligence brief");
});
