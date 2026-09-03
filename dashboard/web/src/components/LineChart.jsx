import { useEffect, useRef, useState } from "react";
import { cssSeries, number } from "../lib/format.js";
import { extent, lineSegments, ticks } from "../lib/chartMath.js";

export default function LineChart({
  series,
  valueKey,
  yLabel,
  thresholds = [],
  domainFn,
  compact = false,
  ariaLabel,
  onTooltip,
}) {
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

  const height = compact ? 230 : 300;
  const margin = { top: 16, right: 22, bottom: 52, left: 68 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const allRows = series.flatMap((item) => item.rows);
  const dates = [...new Set(allRows.map((row) => row.event_day))].sort();
  const values = allRows.map((row) => row[valueKey]).filter(Number.isFinite);
  const domain = domainFn ? domainFn(values) : extent(values);
  const x = (date) =>
    margin.left +
    (dates.length <= 1 ? plotWidth / 2 : (dates.indexOf(date) / (dates.length - 1)) * plotWidth);
  const y = (value) => margin.top + ((domain[1] - value) / (domain[1] - domain[0])) * plotHeight;
  const tickCount = width < 480 ? 3 : 5;
  const tickIndices = [
    ...new Set(
      Array.from({ length: Math.min(tickCount, dates.length) }, (_, index) =>
        Math.round(
          (index * (dates.length - 1)) / (Math.min(tickCount, dates.length) - 1 || 1),
        ),
      ),
    ),
  ];

  return (
    <div ref={ref} className={`chart-wrap${compact ? " small" : ""}`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel || "Line chart"}>
        <title>{ariaLabel || "Line chart"}</title>
        {ticks(domain, 5).map((value) => (
          <g key={`y-${value}`}>
            <line
              x1={margin.left}
              x2={width - margin.right}
              y1={y(value)}
              y2={y(value)}
              className="grid-line"
            />
            <text x={margin.left - 10} y={y(value) + 4} textAnchor="end" className="tick-label">
              {number(value)}
            </text>
          </g>
        ))}
        {domain[0] < 0 && domain[1] > 0 && (
          <line
            x1={margin.left}
            x2={width - margin.right}
            y1={y(0)}
            y2={y(0)}
            className="zero-line"
          />
        )}
        {thresholds
          .filter((value) => value > domain[0] && value < domain[1])
          .map((value) => (
            <line
              key={`t-${value}`}
              x1={margin.left}
              x2={width - margin.right}
              y1={y(value)}
              y2={y(value)}
              className="threshold-line"
            />
          ))}
        {tickIndices.map((index) => {
          const px = x(dates[index]);
          const anchor = index === 0 ? "start" : index === dates.length - 1 ? "end" : "middle";
          return (
            <g key={`x-${dates[index]}`}>
              <line
                x1={px}
                x2={px}
                y1={height - margin.bottom}
                y2={height - margin.bottom + 5}
                className="axis"
              />
              <text x={px} y={height - margin.bottom + 21} textAnchor={anchor} className="tick-label">
                {dates[index]}
              </text>
            </g>
          );
        })}
        <line
          x1={margin.left}
          x2={width - margin.right}
          y1={height - margin.bottom}
          y2={height - margin.bottom}
          className="axis"
        />
        <line
          x1={margin.left}
          x2={margin.left}
          y1={margin.top}
          y2={height - margin.bottom}
          className="axis"
        />
        <text
          x={margin.left + plotWidth / 2}
          y={height - 8}
          textAnchor="middle"
          className="axis-label"
        >
          Event day
        </text>
        <text
          x={15}
          y={margin.top + plotHeight / 2}
          transform={`rotate(-90 15 ${margin.top + plotHeight / 2})`}
          textAnchor="middle"
          className="axis-label"
        >
          {yLabel || valueKey}
        </text>
        {series.map((item, index) => {
          const color = item.color || cssSeries(index);
          return (
            <g key={item.id} data-series={item.id}>
              {lineSegments(item.rows, valueKey).map((segment, segIndex) => {
                const d = segment
                  .map(
                    (row, rowIndex) =>
                      `${rowIndex ? "L" : "M"}${x(row.event_day)},${y(row[valueKey])}`,
                  )
                  .join(" ");
                return <path key={segIndex} d={d} className="series-line" stroke={color} />;
              })}
              {item.rows
                .filter((row) => Number.isFinite(row[valueKey]))
                .map((row) => (
                  <g
                    key={`${item.id}-${row.event_day}`}
                    onPointerMove={(event) =>
                      onTooltip?.({
                        x: Math.min(event.clientX + 14, window.innerWidth - 280),
                        y: Math.min(event.clientY + 14, window.innerHeight - 120),
                        title: item.id,
                        rows: [
                          [row.event_day, `${yLabel || valueKey} ${number(row[valueKey])}`],
                          ["state", row.state || row.rhythm_state || row.quality || "—"],
                        ],
                      })
                    }
                    onPointerLeave={() => onTooltip?.(null)}
                  >
                    {(row.state === "flagged" || row.rhythm_state === "flagged") && (
                      <circle cx={x(row.event_day)} cy={y(row[valueKey])} r={7} className="flag-ring" />
                    )}
                    <circle
                      cx={x(row.event_day)}
                      cy={y(row[valueKey])}
                      r={3.5}
                      fill={color}
                      className="series-point"
                    />
                    <circle
                      cx={x(row.event_day)}
                      cy={y(row[valueKey])}
                      r={12}
                      className="hover-target"
                    />
                  </g>
                ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
