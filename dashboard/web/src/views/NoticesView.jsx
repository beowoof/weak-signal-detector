import { number } from "../lib/format.js";

export default function NoticesView({ result, windowId }) {
  const notices = (result.notices || []).filter((item) => {
    const id = item.trigger?.window_id;
    return !id || id === windowId;
  });
  if (!notices.length) {
    return (
      <p className="empty">
        No persisted notices for this window. Run `wsd notice emit --scenario &lt;id&gt;`.
      </p>
    );
  }
  return (
    <>
      <p className="notice-intro">
        Immutable collection cues. Trigger facts do not change. This is not a determination of
        intent.
      </p>
      <div className="notice-list">
        {notices.map((item) => {
          const trigger = item.trigger || {};
          const workflow = item.workflow || {};
          const late = (trigger.days_before_window_end ?? 99) <= 2;
          const domains = (trigger.contributing_domains || [])
            .map((d) => d.replaceAll("_", " "))
            .join(", ");
          const series = (trigger.contributing_series || []).join(", ");
          return (
            <article
              key={item.notice_id}
              className={`notice-card${late ? " notice-late" : " notice-early"}`}
            >
              <header>
                <p className="eyebrow">{trigger.policy_id || "policy"}</p>
                <h2>
                  {trigger.start} → {trigger.end}
                </h2>
                <p className="notice-timing">
                  {late
                    ? "Near window end (often information-saturated)"
                    : `${trigger.days_before_window_end} days before window end (earlier cue)`}
                </p>
              </header>
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
                  <dd>{trigger.recommended_posture_reason || ""}</dd>
                </div>
                <div>
                  <dt>Domains</dt>
                  <dd>{domains}</dd>
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
                  <dd>{series}</dd>
                </div>
              </dl>
              <p className="notice-id">{item.notice_id}</p>
            </article>
          );
        })}
      </div>
    </>
  );
}
