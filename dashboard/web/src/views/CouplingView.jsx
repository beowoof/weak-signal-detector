import ChartSection from "../components/ChartSection.jsx";
import Legend from "../components/Legend.jsx";
import LineChart from "../components/LineChart.jsx";
import { cssSeries, number } from "../lib/format.js";
import { extent } from "../lib/chartMath.js";

export default function CouplingView({ result, windowId, onTooltip, focus = null }) {
  const coupling = result.coupling?.[windowId];
  if (!coupling?.daily_states?.length) {
    return <p className="empty">No multi-domain coupling data available for this window.</p>;
  }
  const k3Count = coupling.episodes_k3?.length || 0;
  const k3Days = coupling.days_ge3_domains_z15 || 0;
  const k2Count = coupling.episodes_k2?.length || 0;
  const k2Days = coupling.days_ge2_domains_z15 || 0;
  const taskingDays = coupling.tasking_order_days || 0;
  const energyRows = coupling.daily_states.map((st) => ({
    event_day: st.date,
    total_energy: st.total_energy,
    state: st.n_domains_z15 >= 3 ? "flagged" : "normal",
    rhythm_state: st.sensor_tasking_order ? "flagged" : "normal",
  }));
  const domainsPresent = Object.keys(coupling.daily_states[0]?.domain_energies || {}).sort();
  const focusDomains = new Set(focus?.domains || []);
  const domainSeries = domainsPresent.map((dom, idx) => ({
    id: dom.replaceAll("_", " "),
    color: cssSeries(idx),
    muted: focusDomains.size > 0 && !focusDomains.has(dom),
    rows: coupling.daily_states.map((st) => ({
      event_day: st.date,
      domain_energy: st.domain_energies[dom] || 0.0,
      state: (st.domain_energies[dom] || 0) >= 1.5 ? "flagged" : "normal",
    })),
  }));
  const focusSpan = focus?.start && focus?.end ? { start: focus.start, end: focus.end, label: "alert" } : null;

  return (
    <>
      <div className="metrics-grid">
        <div className={`metric-card ${k3Count ? "highlight-warning" : ""}`}>
          <div className="metric-label">Collection indicator (K ≥ 3)</div>
          <div className="metric-value">
            {k3Count} ep ({k3Days}d)
          </div>
          <div className="metric-sub">
            {k3Count
              ? "Independent channels unusual together — collect more"
              : "No multi-domain indicator"}
          </div>
        </div>
        <div className={`metric-card ${k2Count && !k3Count ? "highlight-cue" : ""}`}>
          <div className="metric-label">Watchlist (K ≥ 2)</div>
          <div className="metric-value">
            {k2Count} ep ({k2Days}d)
          </div>
          <div className="metric-sub">Two-domain co-movement; not a determination</div>
        </div>
        <div className={`metric-card ${taskingDays ? "highlight-tasking" : ""}`}>
          <div className="metric-label">Collect more (optical gap)</div>
          <div className="metric-value">{taskingDays} days</div>
          <div className="metric-sub">
            Chorus is up and VIIRS/SAR cannot see; cue other collection
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Peak Domain Energy</div>
          <div className="metric-value">{number(coupling.max_energy)} σ</div>
          <div className="metric-sub">Mean: {number(coupling.mean_energy)} σ</div>
        </div>
      </div>
      <ChartSection
        title="Multi-Domain Anomaly Energy (E_dom)"
        note="Sum of maximum standardized deviations across independent causal domains"
      >
        <LineChart
          series={[{ id: "Total Multi-Domain Energy", rows: energyRows, color: cssSeries(0) }]}
          valueKey="total_energy"
          yLabel="Domain Energy (σ)"
          thresholds={[4.5, 9.0]}
          domainFn={(values) => extent([...values, 0, 10])}
          ariaLabel="Multi-domain anomaly energy over time"
          onTooltip={onTooltip}
          focusSpan={focusSpan}
        />
      </ChartSection>
      {domainSeries.length > 0 && (
        <ChartSection
          title="Causal Domain Energy Contributions"
          note="Standardized anomaly score within each distinct causal mechanism"
        >
          <Legend items={domainSeries} />
          <LineChart
            series={domainSeries}
            valueKey="domain_energy"
            yLabel="Max z-score in domain"
            thresholds={[1.5]}
            domainFn={(values) => extent([...values, 0, 3])}
            ariaLabel="Domain energy breakdown over time"
            onTooltip={onTooltip}
            focusSpan={focusSpan}
          />
        </ChartSection>
      )}
      <section className="chart-block">
        <div className="chart-header">
          <div>
            <h2>Daily indicator matrix</h2>
            <p>Co-movement is a cue to gather news and tasked collection, not a call of what will happen</p>
          </div>
        </div>
        <div className="coupling-table-wrap">
          <table className="coupling-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Active Domains (z ≥ 1.5)</th>
                <th>Total Energy</th>
                <th>Optical/SAR Sensors</th>
                <th>Indicator</th>
                <th>Collect more</th>
              </tr>
            </thead>
            <tbody>
              {coupling.daily_states.map((st) => {
                const inAlert = Boolean(
                  focusSpan && st.date >= focusSpan.start && st.date <= focusSpan.end,
                );
                const verdict =
                  st.verdict === "strategic_coupling_warning" ? (
                    <span className="badge badge-warning">Collect more (K={st.n_domains_z15})</span>
                  ) : st.verdict === "soft_coupling_cue" ? (
                    <span className="badge badge-cue">Watchlist (K={st.n_domains_z15})</span>
                  ) : st.verdict === "single_domain_spike" ? (
                    <span className="badge badge-quiet">Single domain</span>
                  ) : (
                    <span className="badge badge-quiet">Quiet</span>
                  );
                return (
                  <tr key={st.date} className={inAlert ? "notice-focus-row" : undefined}>
                    <td>
                      <strong>{st.date}</strong>
                    </td>
                    <td>
                      {st.active_domains_z15.length ? (
                        st.active_domains_z15.map((d) => d.replaceAll("_", " ")).join(", ")
                      ) : (
                        <span style={{ color: "var(--muted)" }}>0</span>
                      )}
                    </td>
                    <td>{number(st.total_energy)} σ</td>
                    <td>
                      {st.costly_status === "unknown" ? (
                        <span style={{ color: "var(--accent-2)" }}>Cloudy / Unknown</span>
                      ) : st.costly_status === "flagged" ? (
                        <span style={{ color: "var(--danger)" }}>Elevated</span>
                      ) : (
                        <span style={{ color: "var(--muted)" }}>Normal</span>
                      )}
                    </td>
                    <td>{verdict}</td>
                    <td>
                      {st.sensor_tasking_order ? (
                        <span className="badge badge-tasking">Cue tasked collection</span>
                      ) : (
                        <span style={{ color: "var(--muted)" }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
