import { useCallback, useEffect, useMemo, useState } from "react";
import Tooltip from "./components/Tooltip.jsx";
import { seriesIds, windowsOf } from "./lib/format.js";
import CouplingView from "./views/CouplingView.jsx";
import NoticesView from "./views/NoticesView.jsx";
import { AllSeriesView, CombinedView, ScatterView, SeriesView } from "./views/SeriesViews.jsx";

const VIEWS = [
  ["notices", "Notice inbox"],
  ["coupling", "Multi-domain coupling"],
  ["series", "Individual series"],
  ["all", "All series"],
  ["combined", "Combined z-scores"],
  ["scatter", "Z-score scatter"],
];

const POLL_MS = 8000;

export default function App() {
  const [catalog, setCatalog] = useState(null);
  const [resultKey, setResultKey] = useState(localStorage.getItem("wsd-dashboard-result") || "");
  const [result, setResult] = useState(null);
  const [windowId, setWindowId] = useState(null);
  const [seriesId, setSeriesId] = useState(null);
  const [view, setView] = useState("notices");
  const [visibleSeries, setVisibleSeries] = useState(() => new Set());
  const [error, setError] = useState("");
  const [tooltip, setTooltip] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadCatalog = useCallback(async () => {
    const response = await fetch("/api/results");
    if (!response.ok) throw new Error(`Could not discover results (${response.status})`);
    return response.json();
  }, []);

  const loadResult = useCallback(async (key, { silent = false } = {}) => {
    if (!key) return;
    if (!silent) setLoading(true);
    try {
      const response = await fetch(`/api/result?key=${encodeURIComponent(key)}`);
      if (!response.ok) throw new Error(`Could not load result (${response.status})`);
      const payload = await response.json();
      setResult(payload);
      localStorage.setItem("wsd-dashboard-result", key);
      setError("");
    } catch (err) {
      if (!silent) setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await loadCatalog();
        if (cancelled) return;
        setCatalog(data);
        if (!data.results.length) {
          setLoading(false);
          return;
        }
        const remembered = localStorage.getItem("wsd-dashboard-result");
        const initial = data.results.some((item) => item.key === remembered)
          ? remembered
          : data.results[0].key;
        setResultKey(initial);
        await loadResult(initial);
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadCatalog, loadResult]);

  useEffect(() => {
    if (!resultKey) return undefined;
    const id = window.setInterval(() => {
      loadCatalog()
        .then((data) => setCatalog(data))
        .catch(() => undefined);
      loadResult(resultKey, { silent: true });
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [resultKey, loadCatalog, loadResult]);

  const windowOptions = useMemo(() => windowsOf(result), [result]);
  useEffect(() => {
    if (!result) return;
    const nextWindow = windowOptions.includes(windowId) ? windowId : windowOptions[0];
    if (nextWindow !== windowId) setWindowId(nextWindow);
    const ids = seriesIds(result, nextWindow);
    setVisibleSeries(new Set(ids));
    setSeriesId((current) => (ids.includes(current) ? current : ids[0]));
  }, [result, windowOptions, windowId]);

  const ids = seriesIds(result, windowId);
  const alertKeys = ["protocol_alerts", "amber_alerts", "rhythm_alerts", "rhythm_amber_alerts"];
  const alertCount = alertKeys.reduce(
    (total, key) => total + (Array.isArray(result?.summary?.[key]) ? result.summary[key].length : 0),
    0,
  );
  const winCoupling = result?.coupling?.[windowId];
  const k3Count = winCoupling?.episodes_k3?.length || 0;
  const taskingDays = winCoupling?.tasking_order_days || 0;
  const purpose = result?.scenario?.purpose?.replaceAll("_", " ") || "unspecified purpose";
  const mode = result?.summary?.measurement_mode || "legacy unspecified";

  function toggleSeries(id) {
    setVisibleSeries((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <>
      <header className="app-header">
        <div>
          <p className="eyebrow">Weak Signal Fusion</p>
          <h1>Collection cueing desk</h1>
        </div>
        <div className="header-actions">
          <p className="header-note">
            When several weak public series rise together, this is a cue to collect more — not a
            determination of what is happening.
          </p>
          <button type="button" onClick={() => loadResult(resultKey)}>
            Refresh
          </button>
          <span className="poll-hint">polls every {POLL_MS / 1000}s</span>
        </div>
      </header>
      <main>
        <section className="controls" aria-label="Result selection">
          <label>
            <span>Result set</span>
            <select
              value={resultKey}
              onChange={(event) => {
                setResultKey(event.target.value);
                loadResult(event.target.value);
              }}
            >
              {(catalog?.results || []).map((item) => (
                <option key={item.key} value={item.key}>
                  {item.scenario_id} · {item.measure_id.replace("measure-", "")}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Window</span>
            <select value={windowId || ""} onChange={(event) => setWindowId(event.target.value)}>
              {windowOptions.map((id) => (
                <option key={id} value={id}>
                  {id.replaceAll("-", " ")}
                </option>
              ))}
            </select>
          </label>
          <label hidden={view !== "series"}>
            <span>Measurement series</span>
            <select value={seriesId || ""} onChange={(event) => setSeriesId(event.target.value)}>
              {ids.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
        </section>
        {result && (
          <section className="result-summary" aria-live="polite">
            <strong>{result.scenario?.scenario_id || "Unknown scenario"}</strong>
            <span>{purpose}</span>
            <span>{result.summary?.n_feature_rows ?? result.features.length} feature rows</span>
            <span>{ids.length} series</span>
            <span className="mode-warning">{mode.replaceAll("_", " ")}</span>
            {(result.notices || []).length > 0 && (
              <span className="badge badge-warning">
                {result.notices.length} notice{result.notices.length === 1 ? "" : "s"}
              </span>
            )}
            {k3Count > 0 && (
              <span className="badge badge-warning">{k3Count} collection indicator ep</span>
            )}
            {taskingDays > 0 && (
              <span className="badge badge-tasking">{taskingDays}d collect more</span>
            )}
            <span className={alertCount ? "alert-count" : ""}>
              {alertCount} alert episode{alertCount === 1 ? "" : "s"}
            </span>
          </section>
        )}
        <nav className="view-tabs" aria-label="Chart views">
          {VIEWS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={String(view === id)}
              onClick={() => setView(id)}
            >
              {label}
            </button>
          ))}
        </nav>
        <section aria-live="polite">
          {error ? <p className="error">{error}</p> : null}
          {loading && !result ? <p className="empty">Loading result set…</p> : null}
          {!loading && catalog && !catalog.results.length ? (
            <p className="empty">No measurement results found under scenarios/*/measurement/.</p>
          ) : null}
          {result && view === "notices" && <NoticesView result={result} windowId={windowId} />}
          {result && view === "coupling" && (
            <CouplingView result={result} windowId={windowId} onTooltip={setTooltip} />
          )}
          {result && view === "series" && (
            <SeriesView
              result={result}
              windowId={windowId}
              seriesId={seriesId}
              onTooltip={setTooltip}
            />
          )}
          {result && view === "all" && (
            <AllSeriesView result={result} windowId={windowId} onTooltip={setTooltip} />
          )}
          {result && view === "combined" && (
            <CombinedView
              result={result}
              windowId={windowId}
              visibleSeries={visibleSeries}
              onToggle={toggleSeries}
              onTooltip={setTooltip}
            />
          )}
          {result && view === "scatter" && (
            <ScatterView result={result} windowId={windowId} onTooltip={setTooltip} />
          )}
        </section>
      </main>
      <Tooltip tooltip={tooltip} />
    </>
  );
}
