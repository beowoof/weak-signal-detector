import { useCallback, useEffect, useRef, useState } from "react";
import Tooltip from "./components/Tooltip.jsx";
import EvidenceCharts from "./components/EvidenceCharts.jsx";
import NoticesView from "./views/NoticesView.jsx";
import OperationsView from "./views/OperationsView.jsx";
import ScenariosView from "./views/ScenariosView.jsx";
import ReportView from "./views/ReportView.jsx";
import useWorkspaceRoute from "./lib/useWorkspaceRoute.js";
import { readDraftStream } from "./lib/draftStream.js";

const SURFACES = [["notices", "Desk"], ["anomaly", "Explorer"], ["scenarios", "Scenarios"], ["operations", "Operations"]];
const POLL_MS = 8000;
const NOTICE_KEY = "wsd-alert-id";
const RESULT_KEY = "wsd-dashboard-result";

export default function App() {
  const [machineProgress, setMachineProgress] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [notices, setNotices] = useState([]);
  const [route, navigate] = useWorkspaceRoute();
  const selectScenario = useCallback((scenario, replace = false) => navigate({ scenario }, replace), [navigate]);
  const selectedNoticeId = route.notice;
  const surface = route.surface;
  const selectedNotice = notices.find((item) => item.notice_id === selectedNoticeId) || notices[0];
  const resultKey = surface === "notices" ? selectedNotice?.key || route.result : route.result;
  const selectedRef = useRef(selectedNoticeId);
  selectedRef.current = selectedNoticeId;
  const resultRequest = useRef(0);
  const reportRevision = useRef(0);
  const evidenceRevision = useRef(0);
  const [loadedKey, setLoadedKey] = useState("");
  const [resourceOwner, setResourceOwner] = useState("");
  const [resourceError, setResourceError] = useState("");
  const ownerRef = useRef("");
  const [refreshState, setRefreshState] = useState("Connecting…");
  const [drafts, setDrafts] = useState(() => {
    const found = {};
    try { for (const key of Object.keys(localStorage)) {
      if (key.startsWith("wsd-notes-draft:")) found[key.slice("wsd-notes-draft:".length)] = true;
    } } catch { /* browser storage may be unavailable */ }
    return found;
  });
  const onDraftChange = useCallback((id, dirty) => setDrafts((current) =>
    current[id] === dirty ? current : { ...current, [id]: dirty }), []);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [tooltip, setTooltip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [packet, setPacket] = useState(null);
  const [collection, setCollection] = useState(null);
  const [collectBusy, setCollectBusy] = useState(false);
  const [report, setReport] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [machineSeed, setMachineSeed] = useState(null);
  const [evidenceReview, setEvidenceReview] = useState(null);
  const [actionError, setActionError] = useState("");
  const [health, setHealth] = useState(null);
  const [opsBusy, setOpsBusy] = useState(false);
  const [opsLog, setOpsLog] = useState("");
  const [opsError, setOpsError] = useState("");
  const [harvest, setHarvest] = useState(null);

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
    const request = ++resultRequest.current;
    if (!silent) setLoading(true);
    try {
      const response = await fetch(`/api/result?key=${encodeURIComponent(key)}`);
      if (!response.ok) throw new Error(`Could not load result (${response.status})`);
      const payload = await response.json();
      if (request !== resultRequest.current) return;
      setLoadedKey(key);
      setResult(payload);
      localStorage.setItem(RESULT_KEY, key);
      setError("");
    } catch (err) {
      if (request === resultRequest.current) setError(err.message);
    } finally {
      if (request === resultRequest.current) setLoading(false);
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
        const remembered = new URLSearchParams(window.location.search).get("notice") || localStorage.getItem(NOTICE_KEY);
        const initialNotice = items.some((item) => item.notice_id === remembered)
          ? remembered
          : items[0]?.notice_id || "";
        if (initialNotice) localStorage.setItem(NOTICE_KEY, initialNotice);
        const notice = items.find((item) => item.notice_id === initialNotice);
        const initialKey =
          new URLSearchParams(window.location.search).get("result") ||
          notice?.key ||
          (catalogPayload.results.some((item) => item.key === localStorage.getItem(RESULT_KEY))
            ? localStorage.getItem(RESULT_KEY)
            : catalogPayload.results[0]?.key || "");
        if (initialKey) {
          navigate({ notice: initialNotice, result: initialKey }, true);
          setRefreshState("Up to date");
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
  }, [loadCatalog, loadHealth, loadNotices, navigate]);

  useEffect(() => { if (resultKey) loadResult(resultKey); }, [resultKey, loadResult]);

  useEffect(() => {
    const id = window.setInterval(() => {
      loadNotices()
        .then((data) => { setNotices(data.notices || []); setRefreshState("Up to date"); })
        .catch(() => setRefreshState("Offline · showing last update"));
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

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      fetch("/api/collection/progress")
        .then((response) => (response.ok ? response.json() : null))
        .then((payload) => {
          if (!cancelled) setHarvest(payload?.active || null);
        })
        .catch(() => undefined);
    };
    tick();
    const id = window.setInterval(tick, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const noticeFocus = surface === "notices" && selectedNotice ? {
    noticeId: selectedNotice.notice_id,
    start: selectedNotice.trigger?.start,
    end: selectedNotice.trigger?.end,
    windowId: selectedNotice.trigger?.window_id,
    series: selectedNotice.trigger?.contributing_series || [],
    domains: selectedNotice.trigger?.contributing_domains || [],
  } : null;

  useEffect(() => {
    const notice = notices.find((item) => item.notice_id === selectedNoticeId) || notices[0];
    if (ownerRef.current !== selectedNoticeId) {
      ownerRef.current = selectedNoticeId;
      setResourceOwner(selectedNoticeId);
      setPacket(null); setCollection(null); setReport(null); setEvidenceReview(null);
      setActionError(""); setResourceError("");
    }
    const packetId = notice?.workflow?.packet_id;
    const scenario = notice?.scenario_id || notice?.trigger?.scenario_id;
    if (!notice || !scenario) return;
    let cancelled = false;
    const reportReadRevision = reportRevision.current;
    const evidenceReadRevision = evidenceRevision.current;
    const read = async (path, label) => {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`${label} could not be loaded (${response.status}).`);
      return response.json();
    };
    const tasks = [
      read(`/api/report?scenario=${encodeURIComponent(scenario)}&notice_id=${encodeURIComponent(notice.notice_id)}`, "Assessment")
        .then((payload) => {
          if (!cancelled && reportRevision.current === reportReadRevision) setReport(payload);
        }),
    ];
    if (packetId) {
      tasks.push(
        read(`/api/packet/draft/review?scenario=${encodeURIComponent(scenario)}&notice_id=${encodeURIComponent(notice.notice_id)}`, "Draft evidence review")
          .then((payload) => { if (!cancelled && evidenceRevision.current === evidenceReadRevision) setEvidenceReview(payload.review || null); }),
        read(`/api/packet?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(packetId)}`, "Brief")
          .then((payload) => { if (!cancelled) setPacket(payload); }),
        read(`/api/packet/collection?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(packetId)}`, "Collection")
          .then((payload) => { if (!cancelled) setCollection(payload); }),
      );
    } else { setPacket(null); setCollection(null); }
    Promise.allSettled(tasks).then((outcomes) => {
      if (!cancelled) setResourceError(outcomes.filter((item) => item.status === "rejected")
        .map((item) => item.reason.message).join(" "));
    });
    return () => { cancelled = true; };
  }, [notices, selectedNoticeId]);

  function selectNotice(noticeId) {
    navigate({ notice: noticeId, surface: "notices" });
    localStorage.setItem(NOTICE_KEY, noticeId);
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
      if (payload.collection && selectedRef.current === notice.notice_id) setCollection(payload.collection);
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
      if (selectedRef.current === notice.notice_id) setCollection(payload);
      const data = await loadNotices();
      setNotices(data.notices || []);
      if (payload.packet_id) {
        const packetResponse = await fetch(
          `/api/packet?scenario=${encodeURIComponent(scenario)}&packet_id=${encodeURIComponent(payload.packet_id)}`,
        );
        if (packetResponse.ok) {
          const nextPacket = await packetResponse.json();
          if (selectedRef.current === notice.notice_id) setPacket(nextPacket);
        }
      }
      return payload;
    } catch (err) {
      setActionError(err.message);
    } finally {
      setCollectBusy(false);
    }
  }

  async function saveReport(notice, notes) {
    reportRevision.current += 1;
    setActionError("");
    setReportBusy(true);
    const scenario = notice.scenario_id || notice.trigger?.scenario_id;
    try {
      const payload = await postJson("/api/report", {
        scenario,
        notice_id: notice.notice_id,
        notes,
      });
      if (selectedRef.current === notice.notice_id) setReport(payload);
      return payload;
    } catch (err) {
      if (selectedRef.current === notice.notice_id) setActionError(err.message);
    } finally {
      setReportBusy(false);
      reportRevision.current += 1;
    }
  }

  function openNotes() {
    if (!selectedNotice) return;
    navigate({ surface: "notices", tab: "notes" });
  }

  async function runMachineDraft(notice, researchLimits) {
    setActionError("");
    setCollectBusy(true);
    setMachineProgress({ noticeId: notice.notice_id, stage: "Starting research", elapsed_s: 0, history: [] });
    const scenario = notice.scenario_id || notice.trigger?.scenario_id;
    const replay = Boolean(notice.trigger?.end && new Date(notice.trigger.end).getFullYear() < 2024);
    try {
      const body = {
        scenario,
        notice_id: notice.notice_id,
        replay,
        search: true,
        apply: false,
        research_limits: researchLimits,
      };
      const response = await fetch("/api/packet/draft/stream", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const payload = await readDraftStream(response, event => setMachineProgress(previous => ({
        ...event, noticeId: notice.notice_id,
        history: previous?.stage === event.stage ? previous.history :
          [...(previous?.history || []), event.stage],
      })));
      setMachineProgress(previous => ({ ...previous, stage: "Complete — review the collection result below" }));
      if (selectedRef.current === notice.notice_id && payload.leakage && payload.leakage.length) {
        setActionError(`Machine draft flagged leakage: ${payload.leakage.join(", ")}. Edit before saving.`);
      }
      setMachineSeed({ noticeId: notice.notice_id, notes: payload.notes || "", at: Date.now() });
      if (selectedRef.current === notice.notice_id) {
        evidenceRevision.current += 1;
        setEvidenceReview(payload.review || null);
      }
      if (payload.collection || payload.packet_id) {
        const data = await loadNotices();
        setNotices(data.notices || []);
      }
      if (selectedRef.current === notice.notice_id) openNotes();
    } catch (err) {
      setActionError(err.message);
      setMachineProgress(previous => ({ ...previous, stage: `Stopped: ${err.message}` }));
    } finally {
      setCollectBusy(false);
    }
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
        if (packetResponse.ok) {
          const nextPacket = await packetResponse.json();
          if (selectedRef.current === noticeId) setPacket(nextPacket);
        }
      }
      return payload;
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

  function openAnomaly() {
    navigate({ surface: "notices", tab: "evidence" });
  }

  async function refresh() {
    setRefreshState("Refreshing…");
    try {
      const [data, catalogData, healthData] = await Promise.all([loadNotices(), loadCatalog(), loadHealth()]);
      setNotices(data.notices || []); setCatalog(catalogData); setHealth(healthData);
      if (resultKey) await loadResult(resultKey, { silent: true });
      setRefreshState("Up to date");
    } catch (err) { setRefreshState("Refresh failed"); setError(err.message); }
  }

  const ownResources = resourceOwner === selectedNoticeId;
  const currentPacket = ownResources ? packet : null;
  const currentReport = ownResources ? report : null;
  const currentResult = loadedKey === resultKey ? result : null;
  const evidence = <EvidenceCharts key={surface === "notices" ? selectedNoticeId : resultKey}
    scopeKey={surface === "notices" ? selectedNoticeId : resultKey}
    result={currentResult} focus={noticeFocus} onTooltip={setTooltip} />;

  return <div className="desk-shell">
    <nav className="desk-nav" aria-label="Workspace">
      <span className="desk-brand">WSD <span>INTELLIGENCE DESK</span></span>
      <div className="surface-links">{SURFACES.map(([id, label]) =>
        <button key={id} type="button" aria-current={surface === id ? "page" : undefined}
          onClick={() => navigate({ surface: id })}>{label}</button>)}</div>
      <div className="refresh-status"><span role="status">{refreshState}</span>
        <button type="button" onClick={refresh} aria-label="Refresh workspace" title="Automatically checks every 8 seconds">↻</button>
      </div>
    </nav>
    <main className={surface === "notices" ? "desk-main notice-main" : "desk-main standalone-main"}>
      {harvest && !harvest.stale ? (
        <div className={`harvest-banner${harvest.stalled ? " harvest-banner-stall" : ""}`}>
          Collecting {harvest.scenario_id}
          {harvest.source ? ` · ${harvest.source}` : ""}
          {harvest.window ? `/${harvest.window}` : ""}
          {harvest.day_index && harvest.day_count
            ? ` · day ${harvest.day_index}/${harvest.day_count}`
            : ""}
          {harvest.aoi ? ` · ${harvest.aoi}` : ""}
          {harvest.tile ? ` ${harvest.tile}` : ""}
          {harvest.step ? ` · ${harvest.step}` : ""}
          {harvest.bytes ? ` · ${(harvest.bytes / 1_000_000).toFixed(1)} MB` : ""}
          {harvest.elapsed ? ` · ${harvest.elapsed}` : ""}
          {harvest.stalled ? " · stalled (no new bytes)" : ""}
        </div>
      ) : null}
      {error && <p className="error" role="alert">{error}</p>}
      {surface === "notices" && <NoticesView
        notices={notices} selectedId={selectedNotice?.notice_id} onSelect={selectNotice}
        onOpenAnomaly={openAnomaly} onBuildPacket={buildPacketFromNotice}
        packet={currentPacket} collection={ownResources ? collection : null}
        collectBusy={collectBusy || opsBusy} onCollect={runCollect}
        onMachineDraft={limits => selectedNotice && runMachineDraft(selectedNotice, limits)}
        machineProgress={machineProgress}
        onAction={runAction} actionError={[actionError, ownResources ? resourceError : ""].filter(Boolean).join(" ")}
        activeTab={route.tab} onTabChange={(tab) => navigate({ tab })}
        loading={loading && !notices.length} drafts={drafts}
        evidence={evidence}
        notes={selectedNotice && <ReportView key={selectedNoticeId} noticeId={selectedNoticeId}
          scenario={selectedNotice.scenario_id || selectedNotice.trigger?.scenario_id}
          report={currentReport} busy={reportBusy || collectBusy} onDraftChange={onDraftChange}
          machineSeed={machineSeed}
          evidenceReview={ownResources ? evidenceReview : null}
          onReset={(payload) => { reportRevision.current += 1; setReport(payload); setMachineSeed(null); }}
          onSave={(notes) => saveReport(selectedNotice, notes)} />}
      />}
      {surface === "anomaly" && <>
        <header className="page-heading"><p className="eyebrow">Independent measurement exploration</p><h1>Explorer</h1>
          <p className="notice-timing">Browse result sets independently of your notice and assessment.</p></header>
        <label className="result-picker"><span>Result set</span>
          <select aria-label="Result set" value={route.result} onChange={(e) => navigate({ result: e.target.value })}>
            {(catalog?.results || []).map((item) => <option key={item.key} value={item.key}>
              {item.scenario_id} · {item.measure_id.replace("measure-", "")}
            </option>)}
          </select>
        </label>
        {evidence}
      </>}
      {surface === "operations" && <>
        <header className="page-heading"><p className="eyebrow">Workspace administration</p><h1>Operations</h1></header>
        <OperationsView catalog={catalog} notices={notices} selectedNotice={selectedNotice}
          resultKey={route.result} health={health} busy={opsBusy} log={opsLog} error={opsError}
          harvest={harvest}
          onEmit={emitNotices} onBuildPacket={buildPacket}
          onSelectResult={(key) => navigate({ result: key })} onSelectNotice={(notice) => navigate({ notice })} />
      </>}
      {surface === "scenarios" && <ScenariosView scenario={route.scenario || ""} onSelect={selectScenario} />}
    </main>
    <Tooltip tooltip={tooltip} />
  </div>;
}
