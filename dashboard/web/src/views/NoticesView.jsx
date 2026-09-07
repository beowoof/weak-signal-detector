import { investigationNext, readinessSummary } from "../lib/workspace.js";
import { useEffect, useRef, useState } from "react";
import { humanize, noticeTitle, workflowLabel } from "../lib/workspace.js";
import { number } from "../lib/format.js";
import BriefView from "./BriefView.jsx";
import SecondaryCollection from "./SecondaryCollection.jsx";

const SOURCE_ROLE = {
  corpus: "In this collection",
  desk: "Desk harvests",
  open: "Analyst search",
};

const TERMINAL = new Set(["dismissed", "rejected", "closed"]);

const ACTIONS = [
  {
    id: "ack",
    label: "Mark as read",
    from: ["new", "watching", "context_requested", "in_packet"],
  },
  {
    id: "reexamine",
    label: "Re-examine signal",
    from: ["new", "acked", "watching", "context_requested", "in_packet"],
  },
  {
    id: "request_context",
    label: "Request more information",
    from: ["new", "acked", "watching", "in_packet"],
  },
  {
    id: "ignore",
    label: "Ignore",
    from: ["new", "acked", "watching", "context_requested", "in_packet"],
  },
  {
    id: "reject",
    label: "Flag incorrect signal",
    from: ["new", "acked", "watching", "context_requested", "in_packet"],
  },
];

function isLate(trigger) {
  return (trigger.days_before_window_end ?? 99) <= 2;
}

function AlertRow({ item, selected, onSelect, draft }) {
  const trigger = item.trigger || {};
  return <button type="button" className="alert-row" aria-current={selected ? "true" : undefined}
    onClick={() => onSelect(item.notice_id)}>
    <span className="row-heading"><strong>{noticeTitle(item)}</strong><span className="workflow-badge">{workflowLabel(item.workflow?.state)}</span></span>
    <span className="alert-row-dates">{trigger.start} → {trigger.end}</span>
    <span className="alert-row-cue">{(trigger.contributing_domains || []).map(humanize).join(" · ") || "Measurement cue"}</span>
    <span className="alert-row-meta">{isLate(trigger) ? "Near window end" : `${trigger.days_before_window_end ?? "—"} days before window end`}{draft && <span className="draft-badge"> · Draft</span>}</span>
  </button>;
}

function taskKindClass(status) {
  return `collect-status collect-status-${status || "pending"}`;
}

function CollectionPlan({ plan }) {
  if (!plan) return null;
  const window = plan.window || {};
  return (
    <div className="collect-plan">
      {plan.question ? <p className="notice-look">{plan.question}</p> : null}
      {window.evidence_start ? (
        <p className="notice-timing">
          Admissible dates: {window.evidence_start} → {window.evidence_end}. Cutoff{" "}
          {String(window.knowledge_cutoff || "").replace("T", " ").slice(0, 19)}Z.
        </p>
      ) : null}
      {window.admissible ? <p className="notice-timing">{window.admissible}</p> : null}
      {(window.notes || []).map((note) => (
        <p key={note} className="notice-timing">
          {note}
        </p>
      ))}
      {(plan.aois || []).length ? (
        <div className="brief-pills">
          {plan.aois.map((aoi) => (
            <span key={aoi.id || aoi.name} className="brief-pill">
              {aoi.name}
              {aoi.kind ? ` · ${aoi.kind.replaceAll("_", " ")}` : ""}
            </span>
          ))}
        </div>
      ) : null}
      {(plan.issuers || []).length ? (
        <p className="notice-timing">Issuers: {plan.issuers.join("; ")}.</p>
      ) : null}
      {(plan.sources || []).length ? (
        <div className="brief-table-wrap">
          <table className="brief-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Who</th>
                <th>Status</th>
                <th>What it answers</th>
              </tr>
            </thead>
            <tbody>
              {plan.sources.map((row) => (
                <tr key={row.id || row.name}>
                  <th>{row.name}</th>
                  <td>{SOURCE_ROLE[row.role] || row.role}</td>
                  <td>{(row.status || "").replaceAll("_", " ")}</td>
                  <td>
                    {row.answers}
                    {row.query ? <p className="notice-timing">{row.query}</p> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {(plan.discriminators || []).length ? (
        <div className="brief-table-wrap">
          <table className="brief-table">
            <thead>
              <tr>
                <th>Hypothesis</th>
                <th>What would discriminate</th>
              </tr>
            </thead>
            <tbody>
              {plan.discriminators.map((row) => (
                <tr key={row.hypothesis}>
                  <td>{row.hypothesis}</td>
                  <td>{row.look_for}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function CollectionPanel({ collection, busy, onRun }) {
  const tasks = collection?.tasks || [];
  if (!tasks.length && !busy) return null;
  return (
    <section className="brief-card collect-panel">
      <h3>Collection tasks</h3>
      <p className="notice-timing">
        Packet-scoped. Cutoff-safe. Does not vote in the notice.
      </p>
      {busy ? <p className="notice-timing">Running collection…</p> : null}
      {tasks.map((task) => (
        <details
          key={task.kind || task.task_id}
          className="collect-task"
        >
          <summary>
            <span className={taskKindClass(task.status)}>{task.status}</span> {task.title}
          </summary>
          <p>{task.summary}</p>
          <CollectionPlan plan={task.plan} />
          {!task.plan && task.analyst_question ? (
            <p className="notice-look">{task.analyst_question}</p>
          ) : null}
          {(task.notes || []).map((note) => (
            <p key={note} className="notice-timing">
              {note}
            </p>
          ))}
          {task.kind === "validate" ? (
            <ul className="collect-checklist">
              {(task.items || []).map((row) => (
                <li key={row.id} className={`collect-check collect-check-${row.status}`}>
                  {row.text}
                </li>
              ))}
            </ul>
          ) : null}
          {task.kind === "chronology" && task.items?.length ? (
            <div className="brief-table-wrap">
              <table className="brief-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>What was knowable</th>
                  </tr>
                </thead>
                <tbody>
                  {task.items.slice(-10).map((row) => (
                    <tr key={row.day}>
                      <td>{row.day}</td>
                      <td>
                        {(row.series || [])
                          .map(
                            (cell) =>
                              `${cell.series_id.split(".").slice(-1)[0]} ${number(cell.value)}${
                                cell.note ? ` (${cell.note})` : ""
                              }`,
                          )
                          .join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {task.kind === "refresh_physical" && task.items?.length ? (
            <>
              {task.items.some((row) => row.label && row.kind !== "catalogue_granule") ? (
                <div className="brief-table-wrap">
                  <table className="brief-table">
                    <thead>
                      <tr>
                        <th>Source</th>
                        <th>Day</th>
                        <th>Status</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {task.items
                        .filter((row) => row.label && row.kind !== "catalogue_granule")
                        .map((row) => (
                          <tr key={`${row.label}-${row.day}`}>
                            <td>{row.label}</td>
                            <td>{row.day}</td>
                            <td>{row.knowable ? row.quality : "awaiting"}</td>
                            <td>{row.knowable ? number(row.value) : "—"}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {task.items.some((row) => row.kind === "catalogue_granule") ? (
                <div className="brief-table-wrap">
                  <table className="brief-table">
                    <thead>
                      <tr>
                        <th>AOI</th>
                        <th>Sensor</th>
                        <th>Sensing</th>
                        <th>At cutoff</th>
                        <th>Product</th>
                      </tr>
                    </thead>
                    <tbody>
                      {task.items
                        .filter((row) => row.kind === "catalogue_granule")
                        .map((row) => (
                          <tr key={`${row.aoi_id}-${row.name}`}>
                            <td>{row.aoi_name}</td>
                            <td>{row.collection === "SENTINEL-1" ? "S1 GRD" : "S2 L1C"}</td>
                            <td>{row.sensing_date}</td>
                            <td>{row.knowable ? "knowable" : "not yet"}</td>
                            <td>
                              {row.url ? (
                                <a href={row.url} target="_blank" rel="noreferrer">
                                  {row.name}
                                </a>
                              ) : (
                                row.name
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          ) : null}
          {task.kind === "official_pack" && task.items?.length ? (
            <>
              {(task.items || []).some((row) => row.kind === "declared_posture") ? (
                <div className="brief-table-wrap">
                  <table className="brief-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Issuer</th>
                        <th>Action</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {task.items
                        .filter((row) => row.kind === "declared_posture")
                        .slice(-12)
                        .map((row) => (
                          <tr key={`${row.at}-${row.action}`}>
                            <td>{row.date}</td>
                            <td>
                              {row.government} {row.country}
                              {row.costly ? " · costly" : ""}
                            </td>
                            <td>{row.action}</td>
                            <td>{row.text}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {(task.items || []).some((row) => row.series_id === "nav.spatial_warnings") ? (
                <div className="brief-table-wrap">
                  <table className="brief-table">
                    <thead>
                      <tr>
                        <th>Day</th>
                        <th>NAVAREA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {task.items
                        .filter((row) => row.series_id === "nav.spatial_warnings")
                        .map((row) => (
                          <tr key={row.day}>
                            <td>{row.day}</td>
                            <td>{number(row.value)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          ) : null}
          {onRun ? (
            <p className="notice-actions">
              <button type="button" onClick={() => onRun(task.kind)} disabled={busy}>
                Re-run
              </button>
            </p>
          ) : null}
        </details>
      ))}
    </section>
  );
}

const TABS = [["overview", "Overview"], ["evidence", "Evidence"], ["collection", "Collection"], ["notes", "Notes & assessment"], ["brief", "Intelligence brief"]];

export default function NoticesView({
  notices, selectedId, onSelect, onOpenAnomaly, onBuildPacket, packet, collection,
  collectBusy, onCollect, onMachineDraft, onAction, actionError, activeTab, onTabChange,
  evidence, notes, loading, drafts, machineProgress, activeStep, journey,
}) {
  const [packetStatus, setPacketStatus] = useState("");
  useEffect(() => setPacketStatus(""), [selectedId]);
  const [query, setQuery] = useState("");
  const [researchLimits, setResearchLimits] = useState({ queries: 6, documents: 6, seconds: 180 });
  const [filter, setFilter] = useState("all");
  const [listOpen, setListOpen] = useState(!new URLSearchParams(window.location.search).has("notice"));
  const scrollBody = useRef(null);
  const heading = useRef(null);
  useEffect(() => { scrollBody.current?.scrollTo(0, 0); }, [selectedId, activeTab]);
  const selected = notices.find((item) => item.notice_id === selectedId) || notices[0];
  const filtered = notices.filter((item) => {
    const terms = [noticeTitle(item), item.notice_id, item.trigger?.start, item.trigger?.end,
      ...(item.trigger?.contributing_domains || []).map(humanize)].join(" ").toLowerCase();
    return terms.includes(query.toLowerCase()) && (filter === "all" ||
      (filter === "active" ? !TERMINAL.has(item.workflow?.state) : filter === "draft" ? drafts[item.notice_id] : item.workflow?.state === filter));
  });
  if (!notices.length) return <p className="empty">{loading ? "Loading notices…" : "No notices yet. Use Operations to emit notices from a measurement result."}</p>;
  const shownTab = activeTab === "notes" && activeStep === "brief" ? "brief" : activeTab;
  const openTab = (id) => onTabChange(id === "brief" ? "notes" : id, id === "brief" ? "brief" : id === "notes" ? "review" : undefined);
  const next = investigationNext({ packet, workflow: journey, dirty: drafts[selectedId] });
  const trigger = selected.trigger || {};
  const workflow = selected.workflow || {};
  return <div className={`alert-layout ${listOpen ? "show-list" : "show-detail"}`}>
    <aside className="alert-inbox" aria-label="Notice inbox">
      <div className="inbox-heading"><p className="eyebrow">Analyst queue</p><h1>Notices <span>{notices.length}</span></h1></div>
      <label className="inbox-search"><span className="sr-only">Search notices</span>
        <input type="search" placeholder="Search region, date, domain…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      <label className="inbox-filter"><span className="sr-only">Filter notices</span><select aria-label="Filter notices" value={filter} onChange={(e) => setFilter(e.target.value)}>
        <option value="all">All notices</option><option value="active">Active notices</option>
        <option value="new">New</option><option value="context_requested">Context requested</option>
        <option value="draft">With local drafts</option>
      </select></label>
      <p className="queue-count" role="status">{filtered.length} of {notices.length} notices</p>
      <div className="alert-row-list">{filtered.map((item) => <AlertRow key={item.notice_id} item={item}
        selected={selectedId === item.notice_id} draft={drafts[item.notice_id]}
        onSelect={(id) => { onSelect(id); setListOpen(false); requestAnimationFrame(() => heading.current?.focus()); }} />)}
        {!filtered.length && <p className="empty">No matching notices. Try another search or filter.</p>}
      </div>
    </aside>
    <article className="notice-card">
      <header className="notice-header">
        <button type="button" className="mobile-inbox-toggle" onClick={() => setListOpen(true)}>← Notices</button>
        <div className="notice-heading-line"><p className="eyebrow">{noticeTitle(selected)}</p>
        <div className="notice-management"><span className="workflow-badge">{workflowLabel(workflow.state)}</span>
          <details className="action-menu" key={selectedId}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.currentTarget.open = false;
                event.currentTarget.querySelector("summary")?.focus();
              }
            }}
            onClick={(event) => {
              if (event.target.closest("button, a")) event.currentTarget.open = false;
            }}><summary>Notice actions</summary><div className="action-menu-items">
            {!TERMINAL.has(workflow.state) && ACTIONS.map((action) => <button key={action.id} type="button"
              disabled={collectBusy || !action.from.includes(workflow.state || "new")} onClick={() => {
                onAction(selected, action.id);
                if (action.id === "reexamine") onOpenAnomaly();
              }}>{action.label}</button>)}
          </div></details>
        </div></div>
        <h2 ref={heading} tabIndex={-1}>{packet?.product?.headline || "Multi-domain activity cue"}</h2>
        <p className="notice-timing">{packet?.clocks?.knowledge_cutoff ? `Evidence cutoff: ${packet.clocks.knowledge_cutoff} · ` : "Evidence cutoff not loaded · "}{trigger.start} → {trigger.end} · {isLate(trigger) ? "Near window end" : `${trigger.days_before_window_end ?? "—"} days before window end`}</p>
        <nav className="notice-tabs" role="tablist" aria-label="Notice sections">
          {TABS.map(([id, label], index) => <button key={id} id={`tab-${id}`} role="tab" type="button"
            aria-selected={shownTab === id} aria-controls={`panel-${id === "brief" ? "notes" : id}`} tabIndex={shownTab === id ? 0 : -1}
            onClick={() => openTab(id)} onKeyDown={(event) => {
              const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
              const target = event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : offset ? (index + offset + TABS.length) % TABS.length : null;
              if (target !== null) { event.preventDefault(); openTab(TABS[target][0]); document.getElementById(`tab-${TABS[target][0]}`)?.focus(); }
            }}>{label}{id === "notes" && drafts[selectedId] ? " •" : ""}</button>)}
        </nav>
      </header>
      <div className="notice-body" ref={scrollBody}>
        {actionError && <p className="error" role="alert">{actionError}</p>}
        <section id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" hidden={activeTab !== "overview"}>
          <div className="cue-summary"><p className="eyebrow">Why this needs attention</p>
            <p>{packet?.product?.change || humanize(trigger.recommended_posture_reason) || "A multi-domain measurement cue requires contextual review."}</p>
            <p className="notice-timing">{(trigger.contributing_domains || []).map(humanize).join(" · ")}</p>
          </div>
          <section className="investigation-journey" aria-label="Investigation journey">
            <h3>Investigation → review → assessment → intelligence brief</h3>
            <p>{next.detail}</p><p role="status">{readinessSummary(journey)}</p>
            <button className="primary-action" type="button" onClick={() => onTabChange(next.tab, next.step)}>{next.label}</button>
          </section>
          <BriefView packet={packet} notice={selected} mode="overview" />
          <details className="notice-metadata"><summary>Notice metadata</summary><dl>
            <div><dt>Notice ID</dt><dd>{selected.notice_id}</dd></div>
            <div><dt>Policy</dt><dd>{trigger.policy_id || "—"}</dd></div>
            <div><dt>Peak energy</dt><dd>{number(trigger.derived?.max_energy)} σ</dd></div>
            <div><dt>Posture</dt><dd>{humanize(trigger.recommended_posture || "focused")}</dd></div>
            <div><dt>Window</dt><dd>{trigger.window_id}</dd></div>
            <div><dt>Imaging</dt><dd>{Object.values(trigger.imaging_status_by_day || {}).join(", ") || "—"}</dd></div>
          </dl></details>
        </section>
        <section id="panel-evidence" role="tabpanel" aria-labelledby="tab-evidence" hidden={activeTab !== "evidence"}>
          <section className="packet-tools" aria-label="Evidence packet tools">
            <div><h3>Evidence packet</h3><p className="notice-timing">Rebuild the source packet here. Prepare the finished intelligence brief in Notes & assessment.</p></div>
            <div className="notice-actions"><button type="button" disabled={collectBusy} onClick={async () => {
              setPacketStatus("Building evidence packet…");
              const result = await onBuildPacket(selected);
              setPacketStatus(result ? "Evidence packet updated below." : "Evidence packet was not rebuilt. See the error above.");
            }}>{collectBusy ? "Working…" : packet ? "Rebuild evidence packet" : "Build evidence packet"}</button>
            {packet?.packet_id && <a href={`/api/packet/pdf?scenario=${encodeURIComponent(selected.scenario_id || trigger.scenario_id)}&packet_id=${encodeURIComponent(packet.packet_id)}`} target="_blank" rel="noreferrer">Watch-summary PDF</a>}</div>
            {packetStatus && <p role="status">{packetStatus}</p>}
          </section>
          {evidence}<BriefView packet={packet} notice={selected} mode="evidence" />
        </section>
        <section id="panel-collection" role="tabpanel" aria-labelledby="tab-collection" hidden={activeTab !== "collection"}>
          <SecondaryCollection key={selectedId} noticeId={selectedId} cutoff={packet?.clocks?.knowledge_cutoff} busy={collectBusy} collection={collection} onRun={tasks => onCollect(selected, tasks)} />
          <details><summary>Detailed source results</summary><CollectionPanel key={selectedId} collection={collection} busy={collectBusy} /></details>
          <section className="brief-callout" aria-label="Research and draft assessment">
            <h3>3. Research and draft the assessment</h3>
            <p>Retrieve and check public documents, combine them with the collection above, then ask Ollama to draft findings for review in Notes & assessment.</p>
        <p>Research limits: {researchLimits.queries} queries · {researchLimits.documents} document attempts · {researchLimits.seconds}s. Failed retrievals count; Ollama drafting time is additional.</p>
        <details><summary>Change research limits</summary>
          <p>Application limits, unrelated to your Tavily credit balance. Each network request waits at most 30 seconds. Previously attempted URLs are skipped; another run can try remaining candidates.</p>
          {[ ["queries", "Search queries", [3, 6, 9, 12]], ["documents", "Document attempts per run", [6, 12, 24, 48]], ["seconds", "Research time (seconds)", [60, 180, 300, 600]] ].map(([key, label, choices]) =>
            <label key={key}>{label} <select disabled={collectBusy} value={researchLimits[key]} onChange={e => setResearchLimits(old => ({ ...old, [key]: Number(e.target.value) }))}>
              {choices.map(value => <option key={value} value={value}>{value}</option>)}
            </select> </label>)}
        </details>
        {machineProgress?.noticeId === selected.notice_id && <section aria-label="Machine draft progress">
          <p role="status">{machineProgress.elapsed_s}s elapsed · {machineProgress.stage}</p>
          <details><summary>Run activity and cutoffs</summary><ol>{machineProgress.history?.map((stage, i) => <li key={i}>{stage}</li>)}</ol></details>
        </section>}
            <button type="button" disabled={collectBusy} onClick={() => onMachineDraft(researchLimits)}>{collectBusy ? "Working…" : "Research and draft assessment"}</button>
          </section>
          <details><summary>Collection questions and cue validation</summary>
            <BriefView packet={packet} notice={selected} mode="collection" />
            <button type="button" disabled={collectBusy} onClick={() => onCollect(selected, ["validate"])}>Validate existing cue</button>
          </details>
        </section>
        <section id="panel-notes" role="tabpanel" aria-labelledby={shownTab === "brief" ? "tab-brief" : "tab-notes"} hidden={activeTab !== "notes"}>{notes}</section>
      </div>
    </article>
  </div>;
}
