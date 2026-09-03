export function extent(values, padding = 0.08) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [-1, 1];
  let min = Math.min(...finite);
  let max = Math.max(...finite);
  if (min === max) {
    const delta = Math.abs(min || 1) * 0.5;
    return [min - delta, max + delta];
  }
  const delta = (max - min) * padding;
  return [min - delta, max + delta];
}

export function ticks([min, max], count = 5) {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) return [min];
  const rough = span / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const error = rough / power;
  const step = (error >= 7.5 ? 10 : error >= 3.5 ? 5 : error >= 1.5 ? 2 : 1) * power;
  const start = Math.ceil(min / step) * step;
  const output = [];
  for (let value = start; value <= max + step * 1e-6; value += step) output.push(value);
  return output;
}

export function spanXs(start, end, dates, xFn, plotLeft, plotRight) {
  if (!start || !end || !dates.length) return null;
  const indexOf = (day) => {
    const exact = dates.indexOf(day);
    if (exact >= 0) return exact;
    const next = dates.findIndex((item) => item >= day);
    if (next < 0) return dates.length - 1;
    return next;
  };
  const i0 = indexOf(start);
  const i1 = indexOf(end);
  const dayWidth =
    dates.length <= 1 ? plotRight - plotLeft : Math.abs(xFn(dates[Math.min(1, dates.length - 1)]) - xFn(dates[0]));
  const x0 = Math.max(plotLeft, xFn(dates[i0]) - dayWidth / 2);
  const x1 = Math.min(plotRight, xFn(dates[i1]) + dayWidth / 2);
  return { x0, x1: Math.max(x1, x0 + 4) };
}

export function lineSegments(rows, valueKey) {
  const segments = [];
  let current = [];
  rows.forEach((row) => {
    if (Number.isFinite(row[valueKey])) current.push(row);
    else if (current.length) {
      segments.push(current);
      current = [];
    }
  });
  if (current.length) segments.push(current);
  return segments;
}
