import { useEffect, useRef, useState } from "react";
import ChartSection from "../components/ChartSection.jsx";
import Legend from "../components/Legend.jsx";
import LineChart from "../components/LineChart.jsx";
import { cssSeries, number, seriesIds, seriesRows, rowsForWindow } from "../lib/format.js";
import { extent, ticks } from "../lib/chartMath.js";

export function SeriesView({ result, windowId, seriesId, onTooltip, focus = null }) {
  const rows = seriesRows(result, windowId, seriesId);
  if (!rows.length) return <p className="empty">No rows for this series and window.</p>;
  const metadata = rows[0];
  const normalizedSeries = [{ id: "trailing z", rows, color: cssSeries(0), key: "z" }];
  if (rows.some((row) => Number.isFinite(row.rhythm_z))) {
    normalizedSeries.push({ id: "rhythm z", rows, color: cssSeries(1), key: "rhythm_z" });
  }
  const flattened = normalizedSeries.map((item) => ({
    id: item.id,
    color: item.color,
    rows: item.rows.map((row) => ({ ...row, plotted: row[item.key] })),
  }));
  const contributed = Boolean(focus?.series?.includes(seriesId));
  const span = focus?.start && focus?.end ? { start: focus.start, end: focus.end, label: "alert" } : null;
  return (
    <>
      <ChartSection
        title={seriesId}
        note={`${metadata.causal_domain || metadata.family || "unclassified"} · ${metadata.source || "unknown source"}${contributed ? " · contributed to this alert" : ""}`}
        focused={contributed}
      >
        <LineChart
          series={[{ id: seriesId, rows, color: cssSeries(0) }]}
          valueKey="raw"
          yLabel="Raw measurement"
          ariaLabel={`${seriesId} raw values over time`}
          onTooltip={onTooltip}
          focusSpan={span}
        />
      </ChartSection>
      <ChartSection title="Normalized anomaly" note="Trailing and frozen-rhythm z-scores share a scale">
        <Legend items={flattened} />
        <LineChart
          series={flattened}
          valueKey="plotted"
          yLabel="Z-score"
          thresholds={[-2, 2]}
          domainFn={(values) => extent([...values, -2, 0, 2])}
          ariaLabel={`${seriesId} normalized anomaly scores`}
          onTooltip={onTooltip}
          focusSpan={span}
        />
      </ChartSection>
    </>
  );
}

export function AllSeriesView({ result, windowId, onTooltip, focus = null }) {
  const ids = seriesIds(result, windowId);
  const span = focus?.start && focus?.end ? { start: focus.start, end: focus.end, label: "alert" } : null;
  const contributing = new Set(focus?.series || []);
  return (
    <>
      <div className="chart-header">
        <div>
          <h2>All raw measurement series</h2>
          <p>Independent y-scales preserve each instrument’s shape; compare timing, not magnitude.</p>
        </div>
      </div>
      <div className="chart-grid">
        {ids.map((id, index) => {
          const rows = seriesRows(result, windowId, id);
          const contributed = contributing.has(id);
          return (
            <ChartSection
              key={id}
              title={id}
              note={`${rows[0]?.causal_domain || rows[0]?.family || ""}${contributed ? " · this alert" : ""}`}
              focused={contributed}
            >
              <LineChart
                series={[{ id, rows, color: cssSeries(index), muted: contributing.size > 0 && !contributed }]}
                valueKey="raw"
                yLabel="Raw"
                compact
                ariaLabel={`${id} raw values over time`}
                onTooltip={onTooltip}
                focusSpan={span}
              />
            </ChartSection>
          );
        })}
      </div>
    </>
  );
}

export function CombinedView({ result, windowId, visibleSeries, onToggle, onTooltip, focus = null }) {
  const contributing = new Set(focus?.series || []);
  const items = seriesIds(result, windowId).map((id, index) => ({
    id,
    rows: seriesRows(result, windowId, id),
    color: cssSeries(index),
    muted: contributing.size > 0 && !contributing.has(id),
  }));
  const visible = items.filter((item) => visibleSeries.has(item.id));
  const span = focus?.start && focus?.end ? { start: focus.start, end: focus.end, label: "alert" } : null;
  return (
    <>
      <ChartSection title="Combined trailing anomalies" note="All instruments on their comparable z-score scale">
        <Legend items={items} interactive visible={visibleSeries} onToggle={onToggle} />
        <LineChart
          series={visible}
          valueKey="z"
          yLabel="Trailing z-score"
          thresholds={[-2, 2]}
          domainFn={(values) => extent([...values, -2, 0, 2])}
          ariaLabel="Combined trailing z-scores"
          onTooltip={onTooltip}
          focusSpan={span}
        />
      </ChartSection>
      {items.some((item) => item.rows.some((row) => Number.isFinite(row.rhythm_z))) && (
        <ChartSection
          title="Combined frozen-rhythm anomalies"
          note="Same series against each window’s frozen pre-window rhythm baseline"
        >
          <LineChart
            series={visible}
            valueKey="rhythm_z"
            yLabel="Rhythm z-score"
            thresholds={[-2, 2]}
            domainFn={(values) => extent([...values, -2, 0, 2])}
            ariaLabel="Combined rhythm z-scores"
            onTooltip={onTooltip}
            focusSpan={span}
          />
        </ChartSection>
      )}
    </>
  );
}

export function ScatterView({ result, windowId, onTooltip }) {
  const rows = rowsForWindow(result, windowId).filter(
    (row) => Number.isFinite(row.z) && Number.isFinite(row.rhythm_z),
  );
  const ids = seriesIds(result, windowId);
  if (!rows.length) {
    return (
      <p className="empty">This result predates rhythm scoring or has no paired z-scores.</p>
    );
  }
  return (
    <ChartSection
      title="Trailing versus frozen-rhythm anomaly"
      note="Each point is one daily measurement; distance from the diagonal shows baseline disagreement"
    >
      <Legend items={ids.map((id, index) => ({ id, color: cssSeries(index) }))} />
      <ScatterChart rows={rows} ids={ids} onTooltip={onTooltip} />
    </ChartSection>
  );
}

function ScatterChart({ rows, ids, onTooltip }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(() => setWidth(Math.max(el.clientWidth || 720, 320)));
    ro.observe(el);
    setWidth(Math.max(el.clientWidth || 720, 320));
    return () => ro.disconnect();
  }, []);
  const height = Math.max(360, Math.min(620, width * 0.55));
  const margin = { top: 24, right: 24, bottom: 60, left: 72 };
  const xDomain = extent([...rows.map((row) => row.z), -2, 0, 2]);
  const yDomain = extent([...rows.map((row) => row.rhythm_z), -2, 0, 2]);
  const x = (value) =>
    margin.left + ((value - xDomain[0]) / (xDomain[1] - xDomain[0])) * (width - margin.left - margin.right);
  const y = (value) =>
    margin.top + ((yDomain[1] - value) / (yDomain[1] - yDomain[0])) * (height - margin.top - margin.bottom);
  const diagonalMin = Math.max(xDomain[0], yDomain[0]);
  const diagonalMax = Math.min(xDomain[1], yDomain[1]);
  return (
    <div ref={ref} className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Scatter plot of trailing z vs rhythm z">
        {ticks(xDomain, 6).map((value) => (
          <g key={`x-${value}`}>
            <line x1={x(value)} x2={x(value)} y1={margin.top} y2={height - margin.bottom} className="grid-line" />
            <text x={x(value)} y={height - margin.bottom + 21} textAnchor="middle" className="tick-label">
              {number(value)}
            </text>
          </g>
        ))}
        {ticks(yDomain, 6).map((value) => (
          <g key={`y-${value}`}>
            <line x1={margin.left} x2={width - margin.right} y1={y(value)} y2={y(value)} className="grid-line" />
            <text x={margin.left - 10} y={y(value) + 4} textAnchor="end" className="tick-label">
              {number(value)}
            </text>
          </g>
        ))}
        <line
          x1={x(diagonalMin)}
          x2={x(diagonalMax)}
          y1={y(diagonalMin)}
          y2={y(diagonalMax)}
          className="zero-line"
        />
        <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} className="axis" />
        <line x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} className="axis" />
        <text
          x={margin.left + (width - margin.left - margin.right) / 2}
          y={height - 10}
          textAnchor="middle"
          className="axis-label"
        >
          Trailing z-score
        </text>
        <text
          x={16}
          y={margin.top + (height - margin.top - margin.bottom) / 2}
          transform={`rotate(-90 16 ${margin.top + (height - margin.top - margin.bottom) / 2})`}
          textAnchor="middle"
          className="axis-label"
        >
          Frozen-rhythm z-score
        </text>
        {rows.map((row) => {
          const color = cssSeries(ids.indexOf(row.series_id));
          const r = row.state === "flagged" || row.rhythm_state === "flagged" ? 6 : 4;
          return (
            <circle
              key={`${row.series_id}-${row.event_day}`}
              cx={x(row.z)}
              cy={y(row.rhythm_z)}
              r={r}
              fill={color}
              className="scatter-point"
              onPointerMove={(event) =>
                onTooltip?.({
                  x: event.clientX + 14,
                  y: event.clientY + 14,
                  title: row.series_id,
                  rows: [
                    [row.event_day, `trailing ${number(row.z)}`],
                    ["rhythm", number(row.rhythm_z)],
                  ],
                })
              }
              onPointerLeave={() => onTooltip?.(null)}
            />
          );
        })}
      </svg>
    </div>
  );
}
