export default function OperationsView({
  catalog,
  notices,
  selectedNotice,
  resultKey,
  health,
  busy,
  log,
  error,
  onEmit,
  onBuildPacket,
  onSelectResult,
  onSelectNotice,
}) {
  const results = catalog?.results || [];
  const scenarios = [...new Set(results.map((item) => item.scenario_id))];
  const selected = results.find((item) => item.key === resultKey) || results[0];
  const scenarioId = selected?.scenario_id || "";
  const measures = results.filter((item) => item.scenario_id === scenarioId);
  const replayDefault = Boolean(
    selectedNotice?.trigger?.end && new Date(selectedNotice.trigger.end).getFullYear() < 2024,
  );

  return (
    <div className="ops-grid">
      <section className="notice-card">
        <p className="eyebrow">Desk</p>
        <h2>Operations</h2>
        <p className="notice-timing">
          Day-to-day work is buttons. The CLI remains for tests and one-off harvests.
        </p>
        <dl>
          <div>
            <dt>API</dt>
            <dd>{health?.ok ? "healthy" : health ? "degraded" : "unknown"}</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd>{health?.db?.ok ? "up" : health?.db?.configured ? "down" : "not configured"}</dd>
          </div>
          <div>
            <dt>Agent</dt>
            <dd>
              {health?.agent
                ? `${health.agent.status}${health.agent.stale ? " (stale)" : ""}`
                : "not seen"}
            </dd>
          </div>
        </dl>
      </section>

      <section className="notice-card">
        <h2>Emit notices</h2>
        <p className="notice-timing">
          Persist K≥3 coupling episodes as alerts for a measurement. Does not rewrite existing
          triggers.
        </p>
        <div className="ops-fields">
          <label>
            <span>Scenario</span>
            <select
              value={scenarioId}
              onChange={(event) => {
                const next = results.find((item) => item.scenario_id === event.target.value);
                if (next) onSelectResult(next.key);
              }}
            >
              {scenarios.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Measurement</span>
            <select
              value={selected?.key || ""}
              onChange={(event) => onSelectResult(event.target.value)}
            >
              {measures.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.measure_id}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="notice-actions">
          <button
            type="button"
            disabled={busy || !selected}
            onClick={() => onEmit(selected.scenario_id, selected.measure_id)}
          >
            Emit notices
          </button>
        </p>
      </section>

      <section className="notice-card">
        <h2>Build brief</h2>
        <p className="notice-timing">
          Assemble the packet for a notice. Replay uses episode-end cutoff so a later harvest cannot
          leak into a historical alert.
        </p>
        <label>
          <span>Notice</span>
          <select
            value={selectedNotice?.notice_id || ""}
            onChange={(event) => onSelectNotice(event.target.value)}
          >
            {notices.map((item) => (
              <option key={item.notice_id} value={item.notice_id}>
                {item.trigger?.start} → {item.trigger?.end} · {item.scenario_id} ·{" "}
                {item.workflow?.state}
              </option>
            ))}
          </select>
        </label>
        <p className="notice-actions">
          <button
            type="button"
            disabled={busy || !selectedNotice}
            onClick={() =>
              onBuildPacket(
                selectedNotice.scenario_id || selectedNotice.trigger?.scenario_id,
                selectedNotice.notice_id,
                replayDefault,
              )
            }
          >
            {replayDefault ? "Build brief (replay)" : "Build brief"}
          </button>
        </p>
      </section>

      {(error || log) && (
        <section className="notice-card">
          <h2>Last run</h2>
          {error ? <p className="error">{error}</p> : null}
          {log ? <pre className="ops-log">{log}</pre> : null}
        </section>
      )}
    </div>
  );
}
