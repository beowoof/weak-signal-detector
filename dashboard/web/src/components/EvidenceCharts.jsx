import { useEffect, useMemo, useRef, useState } from "react";
import { seriesIds, windowsOf } from "../lib/format.js";
import CouplingView from "../views/CouplingView.jsx";
import { AllSeriesView, CombinedView, ScatterView, SeriesView } from "../views/SeriesViews.jsx";

const CHARTS = [["coupling", "Coupling"], ["series", "Individual series"], ["all", "All series"],
  ["combined", "Combined z-scores"], ["scatter", "Scatter"]];

export default function EvidenceCharts({ result, scopeKey, focus, onTooltip }) {
  const windows = useMemo(() => windowsOf(result), [result]);
  const [windowId, setWindowId] = useState(null);
  const [seriesId, setSeriesId] = useState(null);
  const [chart, setChart] = useState("coupling");
  const [visible, setVisible] = useState(new Set());
  const initialized = useRef("");
  const activeWindow = windows.includes(windowId) ? windowId : windows.includes(focus?.windowId) ? focus.windowId : windows[0];
  const ids = seriesIds(result, activeWindow);
  const signature = ids.join("|");
  useEffect(() => {
    if (!result) return;
    const key = `${scopeKey}:${activeWindow}`;
    if (initialized.current !== key) {
      initialized.current = key;
      const focused = (focus?.series || []).filter((id) => ids.includes(id));
      setVisible(new Set(focused.length ? focused : ids));
      setSeriesId(focused[0] || ids[0]);
    } else {
      // Poll updates must not reset the analyst's choices.
      setVisible((current) => new Set([...current].filter((id) => ids.includes(id))));
      setSeriesId((current) => ids.includes(current) ? current : ids[0]);
    }
  }, [scopeKey, activeWindow, signature]);
  if (!result) return <p className="empty">Loading evidence…</p>;
  const activeFocus = activeWindow === focus?.windowId ? focus : null;
  const shared = { result, windowId: activeWindow, focus: activeFocus, onTooltip };
  return <section className="evidence-charts" aria-label="Measurement charts">
    <div className="result-summary">
      <strong>{result.scenario?.scenario_id || "Unknown scenario"}</strong>
      <span>{result.scenario?.purpose?.replaceAll("_", " ")}</span>
      <span className="mode-warning">{(result.summary?.measurement_mode || "legacy unspecified").replaceAll("_", " ")}</span>
      {result.summary?.scientific_result === false && <span>Not a scientific result</span>}
    </div>
    {focus && <p className="notice-timing">Notice interval: {focus.start} → {focus.end}. {activeFocus ? "Highlighting shows the cue within its measurement window." : "Comparison window selected; notice highlighting is hidden."}</p>}
    <div className="chart-controls">
      <label><span>Window</span><select aria-label="Window" value={activeWindow || ""} onChange={(e) => setWindowId(e.target.value)}>
        {windows.map((id) => <option key={id} value={id}>{id.replaceAll("-", " ")}</option>)}
      </select></label>
      {chart === "series" && <label><span>Measurement series</span><select aria-label="Measurement series" value={seriesId || ""} onChange={(e) => setSeriesId(e.target.value)}>
        {ids.map((id) => <option key={id} value={id}>{id}</option>)}
      </select></label>}
    </div>
    <nav className="view-tabs" aria-label="Chart type">{CHARTS.map(([id, label]) =>
      <button key={id} type="button" aria-pressed={chart === id} onClick={() => setChart(id)}>{label}</button>)}</nav>
    {chart === "coupling" && <CouplingView {...shared} />}
    {chart === "series" && <SeriesView {...shared} seriesId={seriesId} />}
    {chart === "all" && <AllSeriesView {...shared} />}
    {chart === "combined" && <CombinedView {...shared} visibleSeries={visible} onToggle={(id) => setVisible((current) => {
      const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next;
    })} />}
    {chart === "scatter" && <ScatterView {...shared} />}
  </section>;
}
