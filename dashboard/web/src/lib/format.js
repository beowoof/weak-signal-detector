export const cssSeries = (index) => `var(--series-${(index % 6) + 1})`;

export function number(value) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumSignificantDigits: 5 }).format(value);
}

export function rowsForWindow(result, windowId) {
  return (result?.features || []).filter((row) => row.window_id === windowId);
}

export function seriesIds(result, windowId) {
  return [...new Set(rowsForWindow(result, windowId).map((row) => row.series_id))].sort();
}

export function seriesRows(result, windowId, seriesId) {
  return rowsForWindow(result, windowId)
    .filter((row) => row.series_id === seriesId)
    .sort((a, b) => a.event_day.localeCompare(b.event_day));
}

export function windowsOf(result) {
  const ids = [...new Set((result?.features || []).map((row) => row.window_id))];
  return ids.sort((a, b) => (a === "incident" ? -1 : b === "incident" ? 1 : a.localeCompare(b)));
}
