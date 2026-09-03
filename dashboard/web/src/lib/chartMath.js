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
