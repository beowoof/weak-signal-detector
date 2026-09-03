import { number } from "../lib/format.js";
import BriefView from "./BriefView.jsx";

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

function AlertRow({ item, selected, onSelect }) {
  const trigger = item.trigger || {};
  const workflow = item.workflow || {};
  const late = isLate(trigger);
  return (
    <button
      type="button"
      className={`alert-row${late ? " notice-late" : " notice-early"}`}
      aria-current={selected ? "true" : undefined}
      onClick={() => onSelect(item.notice_id)}
    >
      <span className="alert-row-dates">
        {trigger.start} → {trigger.end}
      </span>
      <span className="alert-row-meta">
        {item.scenario_id || trigger.scenario_id} · {workflow.state || "new"}
      </span>
    </button>
  );
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
          open={task.kind === "validate" || Boolean(task.plan)}
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
                  {task.items.map((row) => (
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

function AlertDetail({
  item,
  packet,
  collection,
  collectBusy,
  onCollect,
  onAddNotes,
  onOpenAnomaly,
  onBuildPacket,
  onAction,
  actionError,
}) {
  const trigger = item.trigger || {};
  const workflow = item.workflow || {};
  const late = isLate(trigger);
  const domains = (trigger.contributing_domains || []).map((d) => d.replaceAll("_", " ")).join(", ");
  const series = (trigger.contributing_series || []).join(", ");
  return (
    <article className={`notice-card${late ? " notice-late" : " notice-early"}`}>
      <header>
        <p className="eyebrow">Alert</p>
        <h2>
          {trigger.start} → {trigger.end}
        </h2>
        <p className="notice-timing">
          {item.scenario_id || trigger.scenario_id} · {trigger.window_id} ·{" "}
          {late
            ? "near window end"
            : `${trigger.days_before_window_end} days before window end`}
        </p>
      </header>
      <p className="notice-look">
        Look here:{" "}
        {(packet?.product?.keys || []).length
          ? packet.product.keys.join(" · ")
          : domains || "no domains listed"}
        .
      </p>
      {packet?.product?.geographic_frame ? (
        <p className="notice-timing">{packet.product.geographic_frame}</p>
      ) : null}
      <p className="notice-actions">
        {onAddNotes ? (
          <button type="button" onClick={() => onAddNotes(item)}>
            Add Notes
          </button>
        ) : null}
        {item.key && onOpenAnomaly ? (
          <button type="button" onClick={() => onOpenAnomaly(item)}>
            Open anomaly
          </button>
        ) : null}
        {onBuildPacket ? (
          <button type="button" onClick={() => onBuildPacket(item)}>
            Build brief
          </button>
        ) : null}
        {packet?.packet_id ? (
          <a
            className="notice-pdf"
            href={`/api/packet/pdf?scenario=${encodeURIComponent(
              item.scenario_id || trigger.scenario_id,
            )}&packet_id=${encodeURIComponent(packet.packet_id)}`}
            target="_blank"
            rel="noreferrer"
          >
            Download PDF
          </a>
        ) : null}
        {onCollect ? (
          <button
            type="button"
            disabled={collectBusy}
            onClick={() => onCollect(item, ["validate"])}
          >
            Validate cue
          </button>
        ) : null}
        {!TERMINAL.has(workflow.state) &&
          ACTIONS.map((action) => {
            const allowed = action.from.includes(workflow.state || "new");
            return (
              <button
                key={action.id}
                type="button"
                disabled={!allowed || !onAction}
                title={allowed ? undefined : "Not available in this state"}
                onClick={() => {
                  if (!allowed || !onAction) return;
                  onAction(item, action.id);
                  if (action.id === "reexamine") onOpenAnomaly?.(item);
                }}
              >
                {action.label}
              </button>
            );
          })}
      </p>
      {actionError ? <p className="error">{actionError}</p> : null}
      <dl>
        <div>
          <dt>State</dt>
          <dd>{workflow.state || "new"}</dd>
        </div>
        <div>
          <dt>Recommended posture</dt>
          <dd>{trigger.recommended_posture || "focused"}</dd>
        </div>
        <div>
          <dt>Why</dt>
          <dd>{(trigger.recommended_posture_reason || "").replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Policy</dt>
          <dd>{trigger.policy_id || "—"}</dd>
        </div>
        <div>
          <dt>Peak energy</dt>
          <dd>{number(trigger.derived?.max_energy)} σ</dd>
        </div>
        <div>
          <dt>Imaging</dt>
          <dd>{Object.values(trigger.imaging_status_by_day || {}).join(", ") || "—"}</dd>
        </div>
        <div>
          <dt>Unknowns</dt>
          <dd>{(trigger.unknowns || []).join(", ") || "none"}</dd>
        </div>
        <div>
          <dt>Series</dt>
          <dd>{series || "—"}</dd>
        </div>
      </dl>
      <p className="notice-id">{item.notice_id}</p>
      <CollectionPanel
        collection={collection}
        busy={collectBusy}
        onRun={onCollect ? (kind) => onCollect(item, [kind]) : undefined}
      />
      <BriefView
        packet={packet}
        notice={item}
        onCollect={onCollect ? (kind) => onCollect(item, [kind]) : undefined}
        collectBusy={collectBusy}
      />
    </article>
  );
}

export default function NoticesView({
  notices,
  selectedId,
  onSelect,
  onOpenAnomaly,
  onBuildPacket,
  packet,
  collection,
  collectBusy,
  onCollect,
  onAddNotes,
  onAction,
  actionError,
}) {
  if (!notices.length) {
    return (
      <p className="empty">
        No notices. An anomaly becomes an alert only after `wsd notice emit`.
      </p>
    );
  }
  const selected = notices.find((item) => item.notice_id === selectedId) || notices[0];
  return (
    <div className="alert-layout">
      <aside className="alert-inbox" aria-label="Notice inbox">
        <p className="notice-intro">Inbox</p>
        <div className="alert-row-list">
          {notices.map((item) => (
            <AlertRow
              key={item.notice_id}
              item={item}
              selected={item.notice_id === selected.notice_id}
              onSelect={onSelect}
            />
          ))}
        </div>
      </aside>
      <AlertDetail
        item={selected}
        packet={packet}
        collection={collection}
        collectBusy={collectBusy}
        onCollect={onCollect}
        onAddNotes={onAddNotes}
        onOpenAnomaly={onOpenAnomaly}
        onBuildPacket={onBuildPacket}
        onAction={onAction}
        actionError={actionError}
      />
    </div>
  );
}
