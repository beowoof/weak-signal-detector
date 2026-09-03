import { number } from "../lib/format.js";

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

function AlertDetail({ item, onOpenAnomaly }) {
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
            ? "near window end (often information-saturated)"
            : `${trigger.days_before_window_end} days before window end`}
        </p>
      </header>
      <p className="notice-look">Look here: {domains || "no domains listed"}.</p>
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
      {item.key && onOpenAnomaly ? (
        <p className="notice-actions">
          <button type="button" onClick={() => onOpenAnomaly(item)}>
            Open anomaly
          </button>
        </p>
      ) : null}
    </article>
  );
}

export default function NoticesView({ notices, selectedId, onSelect, onOpenAnomaly }) {
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
        <p className="notice-intro">
          A notice is an alert: the desk is interrupting you to look. It is not a brief and not a
          finding of intent.
        </p>
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
      <AlertDetail item={selected} onOpenAnomaly={onOpenAnomaly} />
    </div>
  );
}
