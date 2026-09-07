const isRecord = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
export function gapRows(data) {
  if (!data || typeof data !== "object") return null;
  if (Array.isArray(data.gaps)) return data.gaps.every(isRecord) ? data.gaps : null;
  if (!Array.isArray(data.critical_gaps) && !Array.isArray(data.warning_gaps)) return null;
  const critical = data.critical_gaps || [];
  const warnings = data.warning_gaps || [];
  if (!Array.isArray(critical) || !Array.isArray(warnings) || ![...critical, ...warnings].every(isRecord)) return null;
  return [...critical.map((row) => ({ ...row, severity: row.severity || "critical" })),
    ...warnings.map((row) => ({ ...row, severity: row.severity || "warning" }))];
}
export function manifestRows(data) {
  return Array.isArray(data?.items) && data.items.every(isRecord) && data.items.some((row) => "coverage" in row || "n_expected" in row) ? data.items : null;
}
export function recordSeries(records, field) {
  const series = new Map();
  for (const row of records) {
    if (!isRecord(row)) continue;
    const day = String(row.event_time || row.event_day || row.day || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
    const id = [row.series_id || row.source || field, row.window_id || row.period_id, row.aoi || row.aoi_id].filter(Boolean).join(" · ");
    if (!series.has(id)) series.set(id, []);
    series.get(id).push({ event_day: day, raw: Number.isFinite(row[field]) ? row[field] : null, quality: row.quality });
  }
  return [...series].map(([id, rows]) => ({ id, rows: rows.sort((a, b) => a.event_day.localeCompare(b.event_day)) }));
}

export function artifactTitle(item) {
  return ({ 'missing.json': 'Collection gaps and repair needs', 'manifest.json': 'Collection coverage and provenance', 'summary.json': 'Measurement summary', 'features.jsonl': 'Measured series records', 'observations.jsonl': 'Collected observations', 'decision.json': 'Corpus review outcome', 'workflow.json': 'Assessment and brief history', 'machine_draft.json': 'Machine proposals and research record', 'evidence.json': 'Watch packet evidence', 'status.json': 'Scenario lifecycle status', 'history.jsonl': 'Scenario activity history' })[item.name] || item.name.replace(/\.(jsonl?|md|txt)$/, '').replaceAll('_', ' ');
}
