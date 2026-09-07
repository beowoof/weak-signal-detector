export const NOTICE_TABS = ["overview", "evidence", "collection", "notes"];
export const WORKFLOW_STEPS = ["review", "findings", "assessment", "brief"];
export const SURFACES = ["notices", "anomaly", "operations", "scenarios"];

export function readRoute(search, storage) {
  const params = new URLSearchParams(search);
  return {
    ...Object.fromEntries(["scenarioTab", "artifact", "artifactQuery", "artifactGroup", "artifactRun", "artifactOffset", "artifactPages"].filter(k => params.has(k)).map(k => [k, params.get(k)])),
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
  for (const key of ["scenarioTab", "artifact", "artifactQuery", "artifactGroup", "artifactRun", "artifactOffset", "artifactPages"]) { if (route[key]) params.set(key, route[key]); }
  if (route.step) params.set("step", route.step);
  return `?${params}`;
}
export function humanize(value = "") { return String(value).replaceAll("_", " "); }
export function workflowLabel(state = "new") {
  return ({ new: "New", acked: "Read", in_packet: "Watch packet available", watching: "Watching",
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

// A saved packet is only the start of the investigation journey.
export function investigationNext({ packet, workflow, dirty = false }) {
  if (!packet) return { label: "Build watch packet", detail: "No watch packet yet. Build it in Evidence to start the investigation.", tab: "evidence" };
  if (!workflow) return { label: "Open assessment status", detail: "Assessment status is unavailable or loading; no readiness is assumed.", tab: "notes", step: "review" };
  if (dirty) return { label: "Continue unsaved assessment", detail: "Save your assessment changes before preparing a brief.", tab: "notes", step: "assessment" };
  const brief = workflow.briefs?.at(-1);
  if (workflow.preparing) return { label: "View brief progress", detail: "Brief preparation is running.", tab: "notes", step: "brief" };
  if (brief && !brief.stale) return { label: "Open intelligence brief", detail: brief.signed_off ? "Brief signed off. Preview the approved version." : "Draft brief available. Review it before sign-off.", tab: "notes", step: "brief" };
  if (workflow.report && !workflow.report.empty) return { label: "Prepare intelligence brief", detail: brief?.stale ? "The previous brief is stale. Prepare a version from the current assessment." : "Assessment saved. Prepare the decision-facing brief.", tab: "notes", step: "brief" };
  if (workflow.review) return { label: "Review findings", detail: "Findings are available. Review, retain and merge them into your assessment.", tab: "notes", step: "review" };
  return { label: "Collect context and findings", detail: "Watch packet available; no research proposals or saved assessment yet. Collect context or write your assessment.", tab: "collection" };
}

export function readinessSummary(workflow) {
  if (!workflow) return "Assessment and brief status unavailable or loading";
  const review = workflow.review;
  const total = review ? (review.claims?.length || 0) + (review.hypothesis_updates?.length || 0) + 1 : 0;
  const reviewed = Object.keys(workflow.active_decisions || {}).length;
  const brief = workflow.briefs?.at(-1);
  return [total ? `${reviewed}/${total} proposals reviewed` : "No research proposals",
    workflow.report && !workflow.report.empty ? "Assessment saved" : "No saved assessment",
    !brief ? "No intelligence brief" : brief.stale ? "Brief stale" : brief.signed_off ? "Brief signed off" : "Draft brief available"].join(" · ");
}
export function sourceLabel(id) {
  return ({ alfred: "Economic data vintages (ALFRED)", brent: "Brent oil prices", cbr: "Russian central bank", ct: "Certificate transparency", firms: "Thermal detections (FIRMS)", gdelt: "Public reporting (GDELT)", icews: "Coded public events (ICEWS)", moex: "Moscow exchange", navarea: "Maritime warnings", notam: "Aviation notices", official: "Official statements", osm: "OpenStreetMap", ripe: "Network activity (RIPE)", sar: "Radar imagery", viirs: "Night lights (VIIRS)", wiki_edits: "Wikipedia edits", wikipedia: "Wikipedia pageviews", gazette_cadence: "Official publication cadence" })[id] || humanize(id);
}

export function mergeRoute(current, changes) {
  const next = { ...current, ...changes };
  if (changes.scenario && changes.scenario !== current.scenario) {
    for (const key of ['artifact', 'artifactQuery', 'artifactGroup', 'artifactRun', 'artifactOffset', 'artifactPages']) {
      if (!(key in changes)) delete next[key];
    }
  }
  return next;
}
