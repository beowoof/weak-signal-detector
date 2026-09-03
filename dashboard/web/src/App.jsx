import { useCallback, useEffect, useMemo, useState } from "react";
import Tooltip from "./components/Tooltip.jsx";
import { seriesIds, windowsOf } from "./lib/format.js";
import CouplingView from "./views/CouplingView.jsx";
import NoticesView from "./views/NoticesView.jsx";
import OperationsView from "./views/OperationsView.jsx";
import ReportView, { NotesRead } from "./views/ReportView.jsx";
import { AllSeriesView, CombinedView, ScatterView, SeriesView } from "./views/SeriesViews.jsx";

const SURFACES = [
  ["notices", "Notices"],
  ["anomaly", "Anomaly"],
  ["operations", "Operations"],
];

const TITLES = {
  notices: "Notices",
  anomaly: "Anomaly",
  operations: "Operations",
};

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
  const [packet, setPacket] = useState(null);
  const [collection, setCollection] = useState(null);
  const [collectBusy, setCollectBusy] = useState(false);
  const [report, setReport] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [actionError, setActionError] = useState("");
  const [health, setHealth] = useState(null);
  const [opsBusy, setOpsBusy] = useState(false);
  const [opsLog, setOpsLog] = useState("");
  const [opsError, setOpsError] = useState("");

  const loadCatalog = useCallback(async () => {
    const response = await fetch("/api/results");
    if (!response.ok) throw new Error(`Could not discover results (${response.status})`);
    return response.json();
  }, []);

  const loadHealth = useCallback(async () => {
    const response = await fetch("/api/health");
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
        const [noticePayload, catalogPayload, healthPayload] = await Promise.all([
          loadNotices(),
          loadCatalog(),
          loadHealth(),
        ]);
        if (cancelled) return;
        const items = noticePayload.notices || [];
        setNotices(items);
        setCatalog(catalogPayload);
        if (healthPayload) setHealth(healthPayload);
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
  }, [loadCatalog, loadHealth, loadNotices, loadResult]);

  useEffect(() => {
    const id = window.setInterval(() => {
      loadNotices()
        .then((data) => setNotices(data.notices || []))
        .catch(() => undefined);
      loadCatalog()
        .then((data) => setCatalog(data))
        .catch(() => undefined);
      if (resultKey) loadResult(resultKey, { silent: true });
      loadHealth()
        .then((data) => data && setHealth(data))
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [resultKey, loadCatalog, loadHealth, loadNotices, loadResult]);

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

  useEffect(() => {
    const notice = notices.find((item) => item.notice_id === selectedNoticeId) || notices[0];
    const packetId = notice?.workflow?.packet_id;
    const scenario = notice?.scenario_id || notice?.trigger?.scenario_id;
    if (!notice || !scenario) {
      setPacket(null);
      setCollection(null);
      setReport(null);
      return undefined;
    }
    let cancelled = false;
    fetch(
      `/api/report?scenario=${encodeURIComponent(scenario)}&notice_id=${encodeURIComponent(notice.notice_id)}`,
    )
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!cancelled) setReport(payload);
      })
      .catch(() => {
        if (!cancelled) setReport(null);
      });
    if (!packetId) {
      setPacket(null);
      setCollection(null);
      return () => {
        cancelled = true;
      };
    }
    fetch(`/api/packet?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(packetId)}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!cancelled) setPacket(payload);
      })
      .catch(() => {
        if (!cancelled) setPacket(null);
      });
    fetch(
      `/api/packet/collection?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(packetId)}`,
    )
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!cancelled) setCollection(payload);
      })
      .catch(() => {
        if (!cancelled) setCollection(null);
      });
    return () => {
      cancelled = true;
    };
  }, [notices, selectedNoticeId]);

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

  async function runAction(notice, action) {
    setActionError("");
    const scenario = notice.scenario_id || notice.trigger?.scenario_id;
    try {
      const response = await fetch("/api/notice/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario,
          notice_id: notice.notice_id,
          action,
          replay: Boolean(notice.trigger?.end && new Date(notice.trigger.end).getFullYear() < 2024),
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        setActionError(payload.detail || `Could not ${action}`);
        return;
      }
      setNotices((current) =>
        current.map((item) => (item.notice_id === payload.notice_id ? { ...item, ...payload } : item)),
      );
      if (payload.collection) setCollection(payload.collection);
    } catch (err) {
      setActionError(err.message);
    }
  }

  async function runCollect(notice, tasks, requestContext = false) {
    setActionError("");
    setCollectBusy(true);
    const scenario = notice.scenario_id || notice.trigger?.scenario_id;
    const replay = Boolean(notice.trigger?.end && new Date(notice.trigger.end).getFullYear() < 2024);
    try {
      const payload = await postJson("/api/packet/collect", {
        scenario,
        notice_id: notice.notice_id,
        tasks,
        replay,
        request_context: requestContext,
      });
      setCollection(payload);
      const data = await loadNotices();
      setNotices(data.notices || []);
      if (payload.packet_id) {
        const packetResponse = await fetch(
          `/api/packet?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(payload.packet_id)}`,
        );
        if (packetResponse.ok) setPacket(await packetResponse.json());
      }
    } catch (err) {
      setActionError(err.message);
    } finally {
      setCollectBusy(false);
    }
  }

  async function saveReport(notice, notes) {
    setActionError("");
    setReportBusy(true);
    const scenario = notice.scenario_id || notice.trigger?.scenario_id;
    try {
      const payload = await postJson("/api/report", {
        scenario,
        notice_id: notice.notice_id,
        notes,
      });
      setReport(payload);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setReportBusy(false);
    }
  }

  function openNotes() {
    if (!selectedNotice) return;
    setNotesOpen(true);
  }

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.detail;
      throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
    }
    return payload;
  }

  async function emitNotices(scenario, measurementId) {
    setOpsBusy(true);
    setOpsError("");
    try {
      const payload = await postJson("/api/notice/emit", {
        scenario,
        measurement_id: measurementId,
      });
      setOpsLog(JSON.stringify(payload, null, 2));
      const data = await loadNotices();
      setNotices(data.notices || []);
    } catch (err) {
      setOpsError(err.message);
    } finally {
      setOpsBusy(false);
    }
  }

  async function buildPacket(scenario, noticeId, replay) {
    setOpsBusy(true);
    setOpsError("");
    setActionError("");
    try {
      const payload = await postJson("/api/packet/build", {
        scenario,
        notice_id: noticeId,
        replay,
      });
      setOpsLog(JSON.stringify(payload, null, 2));
      const data = await loadNotices();
      setNotices(data.notices || []);
      if (payload.packet_id) {
        const packetResponse = await fetch(
          `/api/packet?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(payload.packet_id)}`,
        );
        if (packetResponse.ok) setPacket(await packetResponse.json());
      }
    } catch (err) {
      setOpsError(err.message);
      setActionError(err.message);
    } finally {
      setOpsBusy(false);
    }
  }

  function buildPacketFromNotice(notice) {
    const end = notice.trigger?.end;
    const replay = Boolean(end && new Date(end).getFullYear() < 2024);
    return buildPacket(
      notice.scenario_id || notice.trigger?.scenario_id,
      notice.notice_id,
      replay,
    );
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
    <div className="desk-shell">
      <nav className="desk-nav" aria-label="Desk">
        <p className="eyebrow">WSD desk</p>
        {SURFACES.map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-current={surface === id ? "page" : undefined}
            onClick={() => setSurface(id)}
          >
            {id === "notices" ? `${label}${notices.length ? ` (${notices.length})` : ""}` : label}
          </button>
        ))}
      </nav>
      <div className="desk-main">
      <header className="app-header">
        <div>
          <p className="eyebrow">Collection cueing desk</p>
          <h1>{TITLES[surface]}</h1>
        </div>
        <div className="header-actions">
          <p className="header-note">
            {surface === "operations"
              ? "Emit notices and build briefs here. CLI is for tests and harvests."
              : surface === "anomaly"
                ? "Charts for the selected notice window."
                : "Inbox. Open an alert to read the brief."}
          </p>
          <button type="button" onClick={() => loadNotices().then((data) => setNotices(data.notices || []))}>
            Refresh
          </button>
          <span className="poll-hint">polls every {POLL_MS / 1000}s</span>
        </div>
      </header>
      <main>
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
          <div className="anomaly-focus-banner">
            <span>
              Alert <strong>{noticeFocus.start} → {noticeFocus.end}</strong>
              {noticeFocus.domains.length
                ? ` · look at ${noticeFocus.domains.map((d) => d.replaceAll("_", " ")).join(", ")}`
                : ""}
              {noticeFocus.series.length ? ` · ${noticeFocus.series.join(", ")}` : ""}
            </span>
            {selectedNotice ? (
              <button type="button" className="collect-inline" onClick={openNotes}>
                {report && !report.empty ? "Edit notes" : "Add Notes"}
              </button>
            ) : null}
          </div>
        )}
        {selectedNotice && (surface === "notices" || surface === "anomaly") ? (
          notesOpen ? (
            <ReportView
              report={report}
              busy={reportBusy}
              onSave={(notes) => saveReport(selectedNotice, notes)}
              onClose={() => setNotesOpen(false)}
            />
          ) : report && !report.empty ? (
            <NotesRead
              notes={report.notes}
              updatedAt={report.updated_at}
              onEdit={openNotes}
            />
          ) : null
        ) : null}
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
              onBuildPacket={buildPacketFromNotice}
              packet={packet}
              collection={collection}
              collectBusy={collectBusy}
              onCollect={runCollect}
              onAddNotes={openNotes}
              onAction={runAction}
              actionError={actionError}
            />
          )}
          {surface === "operations" && (
            <OperationsView
              catalog={catalog}
              notices={notices}
              selectedNotice={selectedNotice}
              resultKey={resultKey}
              health={health}
              busy={opsBusy}
              log={opsLog}
              error={opsError}
              onEmit={emitNotices}
              onBuildPacket={buildPacket}
              onSelectResult={(key) => {
                setResultKey(key);
                loadResult(key);
              }}
              onSelectNotice={selectNotice}
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
      </div>
      <Tooltip tooltip={tooltip} />
    </div>
  );
}
