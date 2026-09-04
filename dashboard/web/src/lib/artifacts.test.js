import test from "node:test";
import assert from "node:assert/strict";
import { gapRows, manifestRows, recordSeries } from "./artifacts.js";
import { readRoute, routeSearch } from "./workspace.js";

test("missing gaps retain severity and do not double count review arrays", () => {
  assert.equal(gapRows({ gaps: [{ source: "sar" }], warning_gaps: [{ source: "sar" }] }).length, 1);
  assert.equal(gapRows({ critical_gaps: [{}] })[0].severity, "critical");
  assert.deepEqual(gapRows({ warning_gaps: [] }), []);
  assert.equal(gapRows({ unrelated: true }), null);
});
test("coverage does not equate not applicable with observations", () => {
  const data = { items: [{ n_expected: 21, coverage: 1, not_applicable: true, n_ok: 0 }] };
  assert.equal(manifestRows(data)[0].n_ok, 0);
  assert.equal(manifestRows({ items: [{ source: "legacy", coverage: 1, mode: "synthetic" }] })[0].mode, "synthetic");
});
test("malformed structures fall back to raw viewing", () => {
  assert.equal(gapRows({ gaps: [null] }), null);
  assert.equal(manifestRows({ items: [null] }), null);
  assert.deepEqual(recordSeries([null, 2, "record"], "value"), []);
});
test("plots preserve nulls and zeroes and separate series/window contexts", () => {
  const series = recordSeries([
    { event_day: "2020-01-01", value: 0, series_id: "x", period_id: "incident" },
    { event_day: "2020-01-02", value: null, series_id: "x", period_id: "incident" },
    { event_day: "2020-01-01", value: 3, series_id: "x", period_id: "control" },
  ], "value");
  assert.equal(series.length, 2);
  assert.deepEqual(series[0].rows.map((row) => row.raw), [0, null]);
});
test("scenario workspace links round trip", () => {
  const route = { surface: "scenarios", tab: "overview", notice: "", result: "", scenario: "ukraine2022" };
  assert.deepEqual(readRoute(routeSearch(route)), route);
});
