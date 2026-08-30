const NS = "http://www.w3.org/2000/svg";
const state = {
  catalog: null,
  result: null,
  windowId: null,
  seriesId: null,
  view: "series",
  visibleSeries: new Set(),
};

const resultSelect = document.getElementById("result-select");
const windowSelect = document.getElementById("window-select");
const seriesSelect = document.getElementById("series-select");
const seriesControl = document.getElementById("series-control");
const chartRoot = document.getElementById("chart-root");
const summaryRoot = document.getElementById("result-summary");
const errorRoot = document.getElementById("error");
const tooltip = document.getElementById("tooltip");

const cssSeries = index => `var(--series-${(index % 6) + 1})`;
const number = value => value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat(undefined, { maximumSignificantDigits: 5 }).format(value);
const escapeHtml = value => String(value).replace(/[&<>"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);

function svgElement(name, attributes = {}, text = null) {
  const node = document.createElementNS(NS, name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (text != null) node.textContent = text;
  return node;
}

function extent(values, padding = 0.08) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [-1, 1];
  let min = Math.min(...finite);
  let max = Math.max(...finite);
  if (min === max) {
    const delta = Math.abs(min || 1) * 0.5;
    return [min - delta, max + delta];
  }
  const delta = (max - min) * padding;
  return [min - delta, max + delta];
}

function ticks([min, max], count = 5) {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) return [min];
  const rough = span / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const error = rough / power;
  const step = (error >= 7.5 ? 10 : error >= 3.5 ? 5 : error >= 1.5 ? 2 : 1) * power;
  const start = Math.ceil(min / step) * step;
  const output = [];
  for (let value = start; value <= max + step * 1e-6; value += step) output.push(value);
  return output;
}

function lineSegments(rows, valueKey) {
  const segments = [];
  let current = [];
  rows.forEach(row => {
    if (Number.isFinite(row[valueKey])) current.push(row);
    else if (current.length) { segments.push(current); current = []; }
  });
  if (current.length) segments.push(current);
  return segments;
}

function showTooltip(event, html) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const x = Math.min(event.clientX + 14, window.innerWidth - tooltip.offsetWidth - 12);
  const y = Math.min(event.clientY + 14, window.innerHeight - tooltip.offsetHeight - 12);
  tooltip.style.left = `${Math.max(8, x)}px`;
  tooltip.style.top = `${Math.max(8, y)}px`;
}

function hideTooltip() { tooltip.hidden = true; }

function rowsForWindow() {
  return state.result.features.filter(row => row.window_id === state.windowId);
}

function seriesIds() {
  return [...new Set(rowsForWindow().map(row => row.series_id))].sort();
}

function seriesRows(seriesId) {
  return rowsForWindow().filter(row => row.series_id === seriesId).sort((a, b) => a.event_day.localeCompare(b.event_day));
}

function lineChart(container, series, options = {}) {
  const width = Math.max(container.clientWidth || 720, 320);
  const height = options.compact ? 230 : 300;
  const margin = { top: 16, right: 22, bottom: 52, left: 68 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const allRows = series.flatMap(item => item.rows);
  const dates = [...new Set(allRows.map(row => row.event_day))].sort();
  const values = allRows.map(row => row[options.valueKey]).filter(Number.isFinite);
  const forced = options.domain ? options.domain(values) : null;
  const domain = forced || extent(values);
  const x = date => margin.left + (dates.length <= 1 ? plotWidth / 2 : dates.indexOf(date) / (dates.length - 1) * plotWidth);
  const y = value => margin.top + (domain[1] - value) / (domain[1] - domain[0]) * plotHeight;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": options.ariaLabel || "Line chart" });
  svg.append(svgElement("title", {}, options.ariaLabel || "Line chart"));

  ticks(domain, 5).forEach(value => {
    const py = y(value);
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: py, y2: py, class: "grid-line" }));
    svg.append(svgElement("text", { x: margin.left - 10, y: py + 4, "text-anchor": "end", class: "tick-label" }, number(value)));
  });
  if (domain[0] < 0 && domain[1] > 0) svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: y(0), y2: y(0), class: "zero-line" }));
  (options.thresholds || []).filter(value => value > domain[0] && value < domain[1]).forEach(value => {
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: y(value), y2: y(value), class: "threshold-line" }));
  });

  const tickCount = width < 480 ? 3 : 5;
  const tickIndices = [...new Set(Array.from({ length: Math.min(tickCount, dates.length) }, (_, index) => Math.round(index * (dates.length - 1) / (Math.min(tickCount, dates.length) - 1 || 1))))];
  tickIndices.forEach(index => {
    const px = x(dates[index]);
    svg.append(svgElement("line", { x1: px, x2: px, y1: height - margin.bottom, y2: height - margin.bottom + 5, class: "axis" }));
    svg.append(svgElement("text", { x: px, y: height - margin.bottom + 21, "text-anchor": index === 0 ? "start" : index === dates.length - 1 ? "end" : "middle", class: "tick-label" }, dates[index]));
  });
  svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: "axis" }));
  svg.append(svgElement("line", { x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom, class: "axis" }));
  svg.append(svgElement("text", { x: margin.left + plotWidth / 2, y: height - 8, "text-anchor": "middle", class: "axis-label" }, "Event day"));
  svg.append(svgElement("text", { x: 15, y: margin.top + plotHeight / 2, transform: `rotate(-90 15 ${margin.top + plotHeight / 2})`, "text-anchor": "middle", class: "axis-label" }, options.yLabel || options.valueKey));

  series.forEach((item, index) => {
    const color = item.color || cssSeries(index);
    lineSegments(item.rows, options.valueKey).forEach(segment => {
      const path = segment.map((row, rowIndex) => `${rowIndex ? "L" : "M"}${x(row.event_day)},${y(row[options.valueKey])}`).join(" ");
      svg.append(svgElement("path", { d: path, class: "series-line", stroke: color, "data-series": item.id }));
    });
    item.rows.filter(row => Number.isFinite(row[options.valueKey])).forEach(row => {
      const group = svgElement("g", { "data-series": item.id });
      const point = svgElement("circle", { cx: x(row.event_day), cy: y(row[options.valueKey]), r: 3.5, fill: color, class: "series-point" });
      if (row.state === "flagged" || row.rhythm_state === "flagged") group.append(svgElement("circle", { cx: x(row.event_day), cy: y(row[options.valueKey]), r: 7, class: "flag-ring" }));
      group.append(point);
      group.append(svgElement("circle", { cx: x(row.event_day), cy: y(row[options.valueKey]), r: 12, class: "hover-target" }));
      const html = `<strong>${escapeHtml(item.id)}</strong><div class="tooltip-row"><span>${row.event_day}</span><span>${escapeHtml(options.yLabel || options.valueKey)} ${number(row[options.valueKey])}</span></div><div class="tooltip-row"><span>state</span><span>${escapeHtml(row.state || row.rhythm_state || row.quality || "—")}</span></div>`;
      group.addEventListener("pointermove", event => showTooltip(event, html));
      group.addEventListener("pointerleave", hideTooltip);
      svg.append(group);
    });
  });
  container.replaceChildren(svg);
}

function chartSection(title, note = "", small = false) {
  const block = document.createElement("section");
  block.className = "chart-block";
  const header = document.createElement("div");
  header.className = "chart-header";
  header.innerHTML = `<h2>${escapeHtml(title)}</h2>${note ? `<p>${escapeHtml(note)}</p>` : ""}`;
  const chart = document.createElement("div");
  chart.className = `chart-wrap${small ? " small" : ""}`;
  block.append(header, chart);
  return { block, chart };
}

function renderSeriesView() {
  const rows = seriesRows(state.seriesId);
  if (!rows.length) return renderEmpty("No rows for this series and window.");
  const metadata = rows[0];
  const raw = chartSection(state.seriesId, `${metadata.causal_domain || metadata.family || "unclassified"} · ${metadata.source || "unknown source"}`);
  chartRoot.append(raw.block);
  lineChart(raw.chart, [{ id: state.seriesId, rows, color: cssSeries(0) }], { valueKey: "raw", yLabel: "Raw measurement", ariaLabel: `${state.seriesId} raw values over time` });

  const normalized = chartSection("Normalized anomaly", "Trailing and frozen-rhythm z-scores share a scale");
  chartRoot.append(normalized.block);
  const normalizedSeries = [{ id: "trailing z", rows, color: cssSeries(0), key: "z" }];
  if (rows.some(row => Number.isFinite(row.rhythm_z))) normalizedSeries.push({ id: "rhythm z", rows, color: cssSeries(1), key: "rhythm_z" });
  const flattened = normalizedSeries.map(item => ({ id: item.id, color: item.color, rows: item.rows.map(row => ({ ...row, plotted: row[item.key] })) }));
  lineChart(normalized.chart, flattened, { valueKey: "plotted", yLabel: "Z-score", thresholds: [-2, 2], domain: values => { const [min, max] = extent([...values, -2, 0, 2]); return [min, max]; }, ariaLabel: `${state.seriesId} normalized anomaly scores` });
  renderLegend(normalized.block, flattened, false);
}

function renderAllView() {
  const intro = document.createElement("div");
  intro.className = "chart-header";
  intro.innerHTML = `<div><h2>All raw measurement series</h2><p>Independent y-scales preserve each instrument’s shape; compare timing, not magnitude.</p></div>`;
  chartRoot.append(intro);
  const grid = document.createElement("div");
  grid.className = "chart-grid";
  seriesIds().forEach((id, index) => {
    const rows = seriesRows(id);
    const section = chartSection(id, rows[0]?.causal_domain || rows[0]?.family || "", true);
    grid.append(section.block);
    lineChart(section.chart, [{ id, rows, color: cssSeries(index) }], { valueKey: "raw", yLabel: "Raw", compact: true, ariaLabel: `${id} raw values over time` });
  });
  chartRoot.append(grid);
}

function renderLegend(container, items, interactive = true) {
  const legend = document.createElement("div");
  legend.className = "legend";
  items.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.series = item.id;
    button.setAttribute("aria-pressed", String(!interactive || state.visibleSeries.has(item.id)));
    button.innerHTML = `<span class="swatch" style="--swatch:${item.color || cssSeries(index)}"></span>${escapeHtml(item.id)}`;
    if (interactive) button.addEventListener("click", () => {
      state.visibleSeries.has(item.id) ? state.visibleSeries.delete(item.id) : state.visibleSeries.add(item.id);
      render();
    });
    legend.append(button);
  });
  container.insertBefore(legend, container.querySelector(".chart-wrap"));
}

function renderCombinedView() {
  const items = seriesIds().map((id, index) => ({ id, rows: seriesRows(id), color: cssSeries(index) }));
  if (!state.visibleSeries.size) items.forEach(item => state.visibleSeries.add(item.id));
  const visible = items.filter(item => state.visibleSeries.has(item.id));
  const section = chartSection("Combined trailing anomalies", "All instruments on their comparable z-score scale");
  chartRoot.append(section.block);
  renderLegend(section.block, items, true);
  lineChart(section.chart, visible, { valueKey: "z", yLabel: "Trailing z-score", thresholds: [-2, 2], domain: values => extent([...values, -2, 0, 2]), ariaLabel: "Combined trailing z-scores for all visible measurement series" });

  if (items.some(item => item.rows.some(row => Number.isFinite(row.rhythm_z)))) {
    const rhythm = chartSection("Combined frozen-rhythm anomalies", "Same series against each window’s frozen pre-window rhythm baseline");
    chartRoot.append(rhythm.block);
    lineChart(rhythm.chart, visible, { valueKey: "rhythm_z", yLabel: "Rhythm z-score", thresholds: [-2, 2], domain: values => extent([...values, -2, 0, 2]), ariaLabel: "Combined rhythm z-scores for all visible measurement series" });
  }
}

function renderScatterView() {
  const rows = rowsForWindow().filter(row => Number.isFinite(row.z) && Number.isFinite(row.rhythm_z));
  if (!rows.length) return renderEmpty("This result predates rhythm scoring or has no paired z-scores.");
  const ids = seriesIds();
  const width = Math.max(chartRoot.clientWidth || 720, 320);
  const height = Math.max(360, Math.min(620, width * 0.55));
  const margin = { top: 24, right: 24, bottom: 60, left: 72 };
  const xDomain = extent([...rows.map(row => row.z), -2, 0, 2]);
  const yDomain = extent([...rows.map(row => row.rhythm_z), -2, 0, 2]);
  const x = value => margin.left + (value - xDomain[0]) / (xDomain[1] - xDomain[0]) * (width - margin.left - margin.right);
  const y = value => margin.top + (yDomain[1] - value) / (yDomain[1] - yDomain[0]) * (height - margin.top - margin.bottom);
  const section = chartSection("Trailing versus frozen-rhythm anomaly", "Each point is one daily measurement; distance from the diagonal shows baseline disagreement");
  chartRoot.append(section.block);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Scatter plot of trailing z-score against rhythm z-score" });
  ticks(xDomain, 6).forEach(value => {
    svg.append(svgElement("line", { x1: x(value), x2: x(value), y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
    svg.append(svgElement("text", { x: x(value), y: height - margin.bottom + 21, "text-anchor": "middle", class: "tick-label" }, number(value)));
  });
  ticks(yDomain, 6).forEach(value => {
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: y(value), y2: y(value), class: "grid-line" }));
    svg.append(svgElement("text", { x: margin.left - 10, y: y(value) + 4, "text-anchor": "end", class: "tick-label" }, number(value)));
  });
  const diagonalMin = Math.max(xDomain[0], yDomain[0]);
  const diagonalMax = Math.min(xDomain[1], yDomain[1]);
  svg.append(svgElement("line", { x1: x(diagonalMin), x2: x(diagonalMax), y1: y(diagonalMin), y2: y(diagonalMax), class: "zero-line" }));
  svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: "axis" }));
  svg.append(svgElement("line", { x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom, class: "axis" }));
  svg.append(svgElement("text", { x: margin.left + (width - margin.left - margin.right) / 2, y: height - 10, "text-anchor": "middle", class: "axis-label" }, "Trailing z-score"));
  svg.append(svgElement("text", { x: 16, y: margin.top + (height - margin.top - margin.bottom) / 2, transform: `rotate(-90 16 ${margin.top + (height - margin.top - margin.bottom) / 2})`, "text-anchor": "middle", class: "axis-label" }, "Frozen-rhythm z-score"));
  rows.forEach(row => {
    const color = cssSeries(ids.indexOf(row.series_id));
    const point = svgElement("circle", { cx: x(row.z), cy: y(row.rhythm_z), r: row.state === "flagged" || row.rhythm_state === "flagged" ? 6 : 4, fill: color, class: "scatter-point" });
    const html = `<strong>${escapeHtml(row.series_id)}</strong><div class="tooltip-row"><span>${row.event_day}</span><span>trailing ${number(row.z)}</span></div><div class="tooltip-row"><span>rhythm</span><span>${number(row.rhythm_z)}</span></div>`;
    point.addEventListener("pointermove", event => showTooltip(event, html));
    point.addEventListener("pointerleave", hideTooltip);
    svg.append(point);
  });
  section.chart.replaceChildren(svg);
  renderLegend(section.block, ids.map((id, index) => ({ id, color: cssSeries(index) })), false);
}

function renderEmpty(message) {
  const empty = document.createElement("p");
  empty.className = "empty";
  empty.textContent = message;
  chartRoot.append(empty);
}

function renderSummary() {
  const { scenario, summary } = state.result;
  const alertKeys = ["protocol_alerts", "amber_alerts", "rhythm_alerts", "rhythm_amber_alerts"];
  const alertCount = alertKeys.reduce((total, key) => total + (Array.isArray(summary[key]) ? summary[key].length : 0), 0);
  const purpose = scenario.purpose ? scenario.purpose.replaceAll("_", " ") : "unspecified purpose";
  const mode = summary.measurement_mode || "legacy unspecified";
  summaryRoot.innerHTML = `<strong>${escapeHtml(scenario.scenario_id || "Unknown scenario")}</strong><span>${escapeHtml(purpose)}</span><span>${summary.n_feature_rows ?? state.result.features.length} feature rows</span><span>${seriesIds().length} series</span><span>${escapeHtml(summary.protocol_id || "unknown protocol")}</span><span class="mode-warning">${escapeHtml(mode.replaceAll("_", " "))}</span><span class="${alertCount ? "alert-count" : ""}">${alertCount} alert episode${alertCount === 1 ? "" : "s"}</span>`;
}

function render() {
  if (!state.result) return;
  chartRoot.replaceChildren();
  errorRoot.hidden = true;
  seriesControl.hidden = state.view !== "series";
  document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === state.view)));
  renderSummary();
  if (state.view === "series") renderSeriesView();
  else if (state.view === "all") renderAllView();
  else if (state.view === "combined") renderCombinedView();
  else renderScatterView();
}

function populateSelectors() {
  const windows = [...new Set(state.result.features.map(row => row.window_id))].sort((a, b) => a === "incident" ? -1 : b === "incident" ? 1 : a.localeCompare(b));
  state.windowId = windows.includes(state.windowId) ? state.windowId : windows[0];
  windowSelect.replaceChildren(...windows.map(id => new Option(id.replaceAll("-", " "), id, false, id === state.windowId)));
  const ids = seriesIds();
  state.seriesId = ids.includes(state.seriesId) ? state.seriesId : ids[0];
  seriesSelect.replaceChildren(...ids.map(id => new Option(id, id, false, id === state.seriesId)));
  state.visibleSeries = new Set(ids);
}

async function loadResult(key) {
  errorRoot.hidden = true;
  chartRoot.innerHTML = '<p class="empty">Loading result set…</p>';
  try {
    const response = await fetch(`/api/result?key=${encodeURIComponent(key)}`);
    if (!response.ok) throw new Error(`Could not load result (${response.status})`);
    state.result = await response.json();
    localStorage.setItem("wsd-dashboard-result", key);
    populateSelectors();
    render();
  } catch (error) {
    chartRoot.replaceChildren();
    errorRoot.textContent = error.message;
    errorRoot.hidden = false;
  }
}

async function initialize() {
  try {
    const response = await fetch("/api/results");
    if (!response.ok) throw new Error(`Could not discover results (${response.status})`);
    state.catalog = await response.json();
    if (!state.catalog.results.length) return renderEmpty("No measurement results found under scenarios/*/measurement/.");
    resultSelect.replaceChildren(...state.catalog.results.map(item => new Option(`${item.scenario_id} · ${item.measure_id.replace("measure-", "")}`, item.key)));
    const remembered = localStorage.getItem("wsd-dashboard-result");
    const initial = state.catalog.results.some(item => item.key === remembered) ? remembered : state.catalog.results[0].key;
    resultSelect.value = initial;
    await loadResult(initial);
  } catch (error) {
    errorRoot.textContent = error.message;
    errorRoot.hidden = false;
  }
}

resultSelect.addEventListener("change", () => loadResult(resultSelect.value));
windowSelect.addEventListener("change", () => {
  state.windowId = windowSelect.value;
  const ids = seriesIds();
  state.seriesId = ids[0];
  seriesSelect.replaceChildren(...ids.map(id => new Option(id, id)));
  state.visibleSeries = new Set(ids);
  render();
});
seriesSelect.addEventListener("change", () => { state.seriesId = seriesSelect.value; render(); });
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => { state.view = button.dataset.view; render(); }));
window.addEventListener("resize", () => { window.clearTimeout(window.__wsdResize); window.__wsdResize = window.setTimeout(render, 120); });

initialize();
