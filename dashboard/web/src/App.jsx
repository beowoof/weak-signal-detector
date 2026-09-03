import { useCallback, useEffect, useMemo, useState } from "react";
import Tooltip from "./components/Tooltip.jsx";
import { seriesIds, windowsOf } from "./lib/format.js";
import CouplingView from "./views/CouplingView.jsx";
import NoticesView from "./views/NoticesView.jsx";
import { AllSeriesView, CombinedView, ScatterView, SeriesView } from "./views/SeriesViews.jsx";

const SURFACES = [
  ["notices", "Notices"],
  ["anomaly", "Anomaly"],
];

const CHARTS = [
  ["coupling", "Multi-domain coupling"],
  ["series", "Individual series"],
  ["all", "All series"],
  ["combined", "Combined z-scores"],
  ["scatter", "Z-score scatter"],
];

const POLL_MS = 8000;
const NOTICE_KEY = "wsd-alert-id";
const RESULT_KEY = "wsd-dashboard-result";

export default function App() {
  const [catalog, setCatalog] = useState(null);
  const [notices, setNotices] = useState([]);
  const [selectedNoticeId, setSelectedNoticeId] = useState(localStorage.getItem(NOTICE_KEY) || "");
  const [resultKey, setResultKey] = useState(localStorage.getItem(RESULT_KEY) || "");
  const [result, setResult] = useState(null);
  const [windowId, setWindowId] = useState(null);
  const [seriesId, setSeriesId] = useState(null);
  const [surface, setSurface] = useState("notices");
  const [chart, setChart] = useState("coupling");
  const [visibleSeries, setVisibleSeries] = useState(() => new Set());
  const [error, setError] = useState("");
  const [tooltip, setTooltip] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadCatalog = useCallback(async () => {
    const response = await fetch("/api/results");
    if (!response.ok) throw new Error(`Could not discover results (${response.status})`);
    return response.json();
  }, []);

  const loadNotices = useCallback(async () => {
    const response = await fetch("/api/notices");
    if (!response.ok) throw new Error(`Could not load notices (${response.status})`);
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
      localStorage.setItem(RESULT_KEY, key);
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
        const [noticePayload, catalogPayload] = await Promise.all([loadNotices(), loadCatalog()]);
        if (cancelled) return;
        const items = noticePayload.notices || [];
        setNotices(items);
        setCatalog(catalogPayload);
        const remembered = localStorage.getItem(NOTICE_KEY);
        const initialNotice = items.some((item) => item.notice_id === remembered)
          ? remembered
          : items[0]?.notice_id || "";
        setSelectedNoticeId(initialNotice);
        if (initialNotice) localStorage.setItem(NOTICE_KEY, initialNotice);
        const notice = items.find((item) => item.notice_id === initialNotice);
        const initialKey =
          notice?.key ||
          (catalogPayload.results.some((item) => item.key === localStorage.getItem(RESULT_KEY))
            ? localStorage.getItem(RESULT_KEY)
            : catalogPayload.results[0]?.key || "");
        if (initialKey) {
          setResultKey(initialKey);
          await loadResult(initialKey);
        } else {
          setLoading(false);
        }
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
  }, [loadCatalog, loadNotices, loadResult]);

  useEffect(() => {
    const id = window.setInterval(() => {
      loadNotices()
        .then((data) => setNotices(data.notices || []))
        .catch(() => undefined);
      loadCatalog()
        .then((data) => setCatalog(data))
        .catch(() => undefined);
      if (resultKey) loadResult(resultKey, { silent: true });
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [resultKey, loadCatalog, loadNotices, loadResult]);

  const windowOptions = useMemo(() => windowsOf(result), [result]);
  const selectedNotice = notices.find((item) => item.notice_id === selectedNoticeId) || notices[0];
  const noticeFocus = useMemo(() => {
    if (!selectedNotice) return null;
    const trigger = selectedNotice.trigger || {};
    if (selectedNotice.key && resultKey && selectedNotice.key !== resultKey) return null;
    if (!trigger.start || !trigger.end) return null;
    return {
      noticeId: selectedNotice.notice_id,
      start: trigger.start,
      end: trigger.end,
      windowId: trigger.window_id,
      series: trigger.contributing_series || [],
      domains: trigger.contributing_domains || [],
    };
  }, [selectedNotice, resultKey]);

  useEffect(() => {
    if (!result) return;
    const preferred = noticeFocus?.windowId;
    const nextWindow = windowOptions.includes(preferred)
      ? preferred
      : windowOptions.includes(windowId)
        ? windowId
        : windowOptions[0];
    if (nextWindow !== windowId) setWindowId(nextWindow);
    const ids = seriesIds(result, nextWindow);
    const focused = (noticeFocus?.series || []).filter((id) => ids.includes(id));
    if (focused.length) {
      setVisibleSeries(new Set(focused));
      setSeriesId((current) => (focused.includes(current) ? current : focused[0]));
    } else {
      setVisibleSeries(new Set(ids));
      setSeriesId((current) => (ids.includes(current) ? current : ids[0]));
    }
  }, [
    result,
    windowOptions,
    windowId,
    noticeFocus?.noticeId,
    noticeFocus?.windowId,
    noticeFocus?.series?.join(),
  ]);

  const ids = seriesIds(result, windowId);
  const purpose = result?.scenario?.purpose?.replaceAll("_", " ") || "unspecified purpose";
  const mode = result?.summary?.measurement_mode || "legacy unspecified";

  function selectNotice(noticeId) {
    setSelectedNoticeId(noticeId);
    localStorage.setItem(NOTICE_KEY, noticeId);
    const notice = notices.find((item) => item.notice_id === noticeId);
    if (notice?.key && notice.key !== resultKey) {
      setResultKey(notice.key);
      loadResult(notice.key);
    }
  }

  function openAnomaly(notice) {
    if (notice?.key) {
      setResultKey(notice.key);
      loadResult(notice.key);
    }
    const trigger = notice?.trigger || {};
    if (trigger.window_id) setWindowId(trigger.window_id);
    setChart("coupling");
    setSurface("anomaly");
  }

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
          <p className="eyebrow">Collection cueing desk</p>
          <h1>Notices</h1>
        </div>
        <div className="header-actions">
          <p className="header-note">
            A notice is an alert: look here. It is not a brief and not a determination of intent.
          </p>
          <button type="button" onClick={() => loadNotices().then((data) => setNotices(data.notices || []))}>
            Refresh
          </button>
          <span className="poll-hint">polls every {POLL_MS / 1000}s</span>
        </div>
      </header>
      <main>
        <nav className="view-tabs" aria-label="Desk surfaces">
          {SURFACES.map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={String(surface === id)}
              onClick={() => setSurface(id)}
            >
              {id === "notices" ? `${label}${notices.length ? ` (${notices.length})` : ""}` : label}
            </button>
          ))}
        </nav>
        {surface === "anomaly" && (
          <section className="controls" aria-label="Anomaly selection">
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
            <label hidden={chart !== "series"}>
              <span>Measurement series</span>
              <select value={seriesId || ""} onChange={(event) => setSeriesId(event.target.value)}>
                {ids.map((id) => (
                  <option key={id} value={id}>
                    {noticeFocus?.series?.includes(id) ? `● ${id}` : id}
                  </option>
                ))}
              </select>
            </label>
          </section>
        )}
        {surface === "anomaly" && result && (
          <section className="result-summary" aria-live="polite">
            <strong>{result.scenario?.scenario_id || "Unknown scenario"}</strong>
            <span>{purpose}</span>
            <span>{result.summary?.n_feature_rows ?? result.features.length} feature rows</span>
            <span>{ids.length} series</span>
            <span className="mode-warning">{mode.replaceAll("_", " ")}</span>
          </section>
        )}
        {surface === "anomaly" && noticeFocus && (
          <p className="anomaly-focus-banner">
            Alert <strong>{noticeFocus.start} → {noticeFocus.end}</strong>
            {noticeFocus.domains.length
              ? ` · look at ${noticeFocus.domains.map((d) => d.replaceAll("_", " ")).join(", ")}`
              : ""}
            {noticeFocus.series.length ? ` · ${noticeFocus.series.join(", ")}` : ""}
          </p>
        )}
        {surface === "anomaly" && (
          <nav className="view-tabs" aria-label="Anomaly charts">
            {CHARTS.map(([id, label]) => (
              <button
                key={id}
                type="button"
                aria-pressed={String(chart === id)}
                onClick={() => setChart(id)}
              >
                {label}
              </button>
            ))}
          </nav>
        )}
        <section aria-live="polite">
          {error ? <p className="error">{error}</p> : null}
          {loading && surface === "anomaly" && !result ? <p className="empty">Loading anomaly…</p> : null}
          {surface === "notices" && (
            <NoticesView
              notices={notices}
              selectedId={selectedNotice?.notice_id}
              onSelect={selectNotice}
              onOpenAnomaly={openAnomaly}
            />
          )}
          {surface === "anomaly" && result && chart === "coupling" && (
            <CouplingView
              result={result}
              windowId={windowId}
              onTooltip={setTooltip}
              focus={noticeFocus}
            />
          )}
          {surface === "anomaly" && result && chart === "series" && (
            <SeriesView
              result={result}
              windowId={windowId}
              seriesId={seriesId}
              onTooltip={setTooltip}
              focus={noticeFocus}
            />
          )}
          {surface === "anomaly" && result && chart === "all" && (
            <AllSeriesView
              result={result}
              windowId={windowId}
              onTooltip={setTooltip}
              focus={noticeFocus}
            />
          )}
          {surface === "anomaly" && result && chart === "combined" && (
            <CombinedView
              result={result}
              windowId={windowId}
              visibleSeries={visibleSeries}
              onToggle={toggleSeries}
              onTooltip={setTooltip}
              focus={noticeFocus}
            />
          )}
          {surface === "anomaly" && result && chart === "scatter" && (
            <ScatterView result={result} windowId={windowId} onTooltip={setTooltip} />
          )}
        </section>
      </main>
      <Tooltip tooltip={tooltip} />
    </>
  );
}
