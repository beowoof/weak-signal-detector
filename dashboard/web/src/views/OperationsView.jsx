function HarvestCard({ harvest }) {
  if (!harvest) {
    return (
      <section className="notice-card">
        <h2>Corpus harvest</h2>
        <p className="notice-timing">No live collection running.</p>
      </section>
    );
  }
  const stalled = harvest.stalled || harvest.stale;
  return (
    <section className={`notice-card${stalled ? " harvest-stalled" : ""}`}>
      <h2>Corpus harvest</h2>
      <p className="notice-timing">
        {harvest.scenario_id} · {harvest.collection_id || "in progress"} · {harvest.elapsed || ""}
        {stalled ? " · stalled" : harvest.stale ? " · stale" : " · live"}
      </p>
      <dl>
        <div>
          <dt>Source</dt>
          <dd>
            {harvest.source || "—"}
            {harvest.window ? ` / ${harvest.window}` : ""}
            {harvest.job_index && harvest.job_count
              ? ` (${harvest.job_index}/${harvest.job_count})`
              : ""}
          </dd>
        </div>
        <div>
          <dt>Day</dt>
          <dd>
            {harvest.day_index && harvest.day_count
              ? `${harvest.day_index}/${harvest.day_count}`
              : "—"}
            {harvest.day ? ` · ${harvest.day}` : ""}
          </dd>
        </div>
        <div>
          <dt>AOI / tile</dt>
          <dd>
            {harvest.aoi || "—"}
            {harvest.tile ? ` · ${harvest.tile}` : ""}
          </dd>
        </div>
        <div>
          <dt>Step</dt>
          <dd>
            {harvest.step || harvest.phase || "—"}
            {harvest.bytes ? ` · ${(harvest.bytes / 1_000_000).toFixed(1)} MB` : ""}
          </dd>
        </div>
      </dl>
      {harvest.message ? <p>{harvest.message}</p> : null}
    </section>
  );
}

export default function OperationsView({
  catalog,
  notices,
  selectedNotice,
  resultKey,
  health,
  busy,
  log,
  error,
  harvest,
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
          Use the backtest runner for corpus collection, quality review and measurement. These controls act on existing results; maintenance and qualification commands remain in the CLI.
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

      <HarvestCard harvest={harvest} />

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
              aria-label="Scenario"
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
              aria-label="Measurement"
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
        <h2>Build watch packet</h2>
        <p className="notice-timing">
          Assemble the packet for a notice. Replay uses episode-end cutoff so a later harvest cannot
          leak into a historical alert.
        </p>
        <label>
          <span>Notice</span>
          <select
            aria-label="Notice"
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
            {replayDefault ? "Build watch packet (replay)" : "Build watch packet"}
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
