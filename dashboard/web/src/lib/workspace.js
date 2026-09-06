export const NOTICE_TABS = ["overview", "evidence", "collection", "notes"];
export const WORKFLOW_STEPS = ["review", "findings", "assessment", "brief"];
export const SURFACES = ["notices", "anomaly", "operations", "scenarios"];

export function readRoute(search, storage) {
  const params = new URLSearchParams(search);
  return {
    ...(params.get("scenario") ? { scenario: params.get("scenario") } : {}),
    surface: SURFACES.includes(params.get("view")) ? params.get("view") : "notices",
    tab: NOTICE_TABS.includes(params.get("tab")) ? params.get("tab") : "overview",
    step: WORKFLOW_STEPS.includes(params.get("step")) ? params.get("step") : "",
    notice: params.get("notice") || storage?.getItem("wsd-alert-id") || "",
    result: params.get("result") || storage?.getItem("wsd-dashboard-result") || "",
  };
}
export function routeSearch(route) {
  const params = new URLSearchParams({ view: route.surface, tab: route.tab });
  if (route.notice) params.set("notice", route.notice);
  if (route.result) params.set("result", route.result);
  if (route.scenario) params.set("scenario", route.scenario);
  if (route.step) params.set("step", route.step);
  return `?${params}`;
}
export function humanize(value = "") { return String(value).replaceAll("_", " "); }
export function workflowLabel(state = "new") {
  return ({ new: "New", acked: "Read", in_packet: "Evidence ready", watching: "Watching",
    context_requested: "Context requested", dismissed: "Dismissed", rejected: "Rejected",
    closed: "Closed" })[state] || humanize(state);
}
export function noticeTitle(notice) {
  const scenario = notice.scenario_id || notice.trigger?.scenario_id || "Unknown region";
  return scenario.replace(/(\D)(\d{4})/, "$1 · $2").replaceAll("_", " ");
}
export function draftKey(noticeId) { return `wsd-notes-draft:${noticeId}`; }
export function briefProduct(brief) {
  const body = String(brief?.body || brief?.editorial?.body || "").trim();
  let text = body;
  if (!text) {
    const markdown = String(brief?.markdown || "");
    for (const marker of ["## Editorial input references", "## Evidence and review annex"]) {
      const cut = markdown.indexOf(marker);
      if (cut >= 0) { text = markdown.slice(0, cut).trim(); break; }
    }
  }
  return text.replace(/\s*\[(?:[APRS]\d+(?:\s*,\s*[APRS]\d+)*)\]/g, "").trim();
}
