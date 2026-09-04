import test from "node:test";
import assert from "node:assert/strict";
import { readRoute, routeSearch, workflowLabel, noticeTitle, draftKey } from "./workspace.js";
import { readDraft, writeDraft, clearDraft } from "./drafts.js";

test("workspace deep links round-trip notice, tab and independent result", () => {
  const route = { surface: "anomaly", tab: "notes", notice: "notice/a&b", result: "deu2018quiet/measure-x" };
  assert.deepEqual(readRoute(routeSearch(route)), route);
});
test("invalid sections fall back to the desk overview", () => {
  assert.deepEqual(readRoute("?view=unknown&tab=bogus"), { surface: "notices", tab: "overview", notice: "", result: "" });
});
test("explicit links take precedence over remembered choices", () => {
  const storage = { getItem: () => "remembered" };
  assert.equal(readRoute("?notice=linked", storage).notice, "linked");
  assert.equal(readRoute("", storage).notice, "remembered");
});
test("triage labels expose readable workflow without changing its value", () => {
  assert.equal(workflowLabel("in_packet"), "Brief ready");
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
