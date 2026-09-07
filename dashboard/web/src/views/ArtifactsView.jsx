import { MarkdownPreview } from "../components/DocumentPreview.jsx";
import { useEffect, useMemo, useState } from "react";
import LineChart from "../components/LineChart.jsx";
import { gapRows, manifestRows, recordSeries } from "../lib/artifacts.js";
import { humanize } from "../lib/workspace.js";

const printable = (value) => value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);

function RecordCell({ value }) {
  if (typeof value === "object" && value !== null) return <details><summary>Inspect</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
  if (typeof value === "string" && value.length > 160) {
    let text = value;
    try { text = JSON.stringify(JSON.parse(value), null, 2); } catch { /* Long prose stays text. */ }
    return <details><summary>Inspect long field</summary><pre>{text}</pre></details>;
  }
  return printable(value);
}

function RecordsTable({ rows }) {
  const objects = rows.map((row) => row && typeof row === "object" && !Array.isArray(row) ? row : { value: row });
  const columns = [...new Set(objects.flatMap(Object.keys))];
  return <div className="brief-table-wrap"><table className="brief-table artifact-table"><thead><tr>
    {columns.map((key) => <th key={key}>{humanize(key)}</th>)}
  </tr></thead><tbody>{objects.map((row, index) => <tr key={index}>{columns.map((key) =>
    <td key={key}><RecordCell value={row[key]} /></td>)}</tr>)}</tbody></table></div>;
}

function Gaps({ data, rows }) {
  const [source, setSource] = useState("");
  const sources = [...new Set(rows.map((row) => row.source || "unspecified"))];
  const filtered = rows.filter((row) => !source || (row.source || "unspecified") === source);
  return <section>
    <h3>Recorded collection gaps</h3>
    <p className="notice-timing">{data.review_id} · {data.collection_id} · {humanize(data.decision || "")}</p>
    <p>These are collection and review findings, not signal strength or event predictions.</p>
    {!rows.length ? <p>No gaps recorded in this artefact. This does not establish complete coverage.</p> : <>
      <div className="gap-bars" aria-label="Recorded gaps by source">{sources.map((name) => {
        const count = rows.filter((row) => (row.source || "unspecified") === name).length;
        return <button key={name} type="button" aria-pressed={source === name} onClick={() => setSource(source === name ? "" : name)}>
          <span>{name}</span><span className="gap-track"><span style={{ width: `${100 * count / rows.length}%` }} /></span><span>{count} gaps</span>
        </button>;
      })}</div>
      <RecordsTable rows={filtered.map((row) => ({ source: row.source, window: row.window_id,
        severity: row.severity, reason: row.reason, requested_action: row.requested_action }))} />
    </>}
  </section>;
}

function Coverage({ data, rows, onOpen }) {
  return <section><h3>Source coverage</h3><p className="notice-timing">{data.collection_id} · {data.created_at}</p>
    <p>Coverage is the value recorded by the collector. Counts remain separate; not applicable is not observed coverage.</p>
    <div className="brief-table-wrap"><table className="brief-table"><thead><tr>
      {['Source / window', 'Recorded coverage', 'OK / expected', 'Missing', 'Source down', 'Details'].map((label) => <th key={label}>{label}</th>)}
    </tr></thead><tbody>{rows.map((row, i) => <tr key={row.item_id || i}>
      <th>{row.source}<small>{row.window_id}</small><small>{row.mode || "Mode not recorded"}</small></th>
      <td>{row.not_applicable ? "Not applicable" : Number.isFinite(row.coverage) ? <>
        <meter min="0" max="1" value={row.coverage} aria-label={`${row.source} ${row.window_id} coverage`} /> {Math.round(row.coverage * 1000) / 10}%
      </> : "Unknown"}</td>
      <td>{row.n_ok ?? "—"} / {row.n_expected ?? "—"}</td><td>{row.n_missing ?? "—"}</td><td>{row.n_source_down ?? "—"}</td>
      <td><details><summary>Provenance & notes</summary><p>{row.notes || "No notes"}</p>
        <p>Provenance complete: {printable(row.provenance_complete)} · Post-cutoff material: {printable(row.contains_post_cutoff_material)}</p>
        {['observations', 'provenance'].map((key) => row[key] && <button key={key} type="button" onClick={() => onOpen(row[key])}>{humanize(key)}</button>)}
      </details></td>
    </tr>)}</tbody></table></div>
  </section>;
}

function RecordPlot({ records }) {
  const fields = [...new Set(records.flatMap((row) => Object.keys(row || {}).filter((key) => typeof row[key] === "number")))];
  const [choice, setChoice] = useState("");
  const field = fields.includes(choice) ? choice : ['value', 'raw', 'z'].find((key) => fields.includes(key)) || fields[0];
  const series = useMemo(() => recordSeries(records, field), [records, field]);
  if (!series.length || !field) return null;
  return <section><label><span>Plot field (current page only)</span><select aria-label="Plot field" value={field} onChange={(e) => setChoice(e.target.value)}>
    {fields.map((key) => <option key={key}>{key}</option>)}
  </select></label>
    <LineChart series={series} valueKey="raw" yLabel={field} ariaLabel={`${field} by event day, current page only`} />
    <p className="notice-timing">{series.map((item) => item.id).join(" · ")}. Missing values remain gaps; this plot covers only the displayed records.</p>
  </section>;
}

export default function ArtifactsView({ scenario, route, onNavigate }) {
  const [items, setItems] = useState([]);
  const path = route.artifact || '', query = route.artifactQuery || '', group = route.artifactGroup || '', run = route.artifactRun || '';
  const offset = Math.max(0, Number(route.artifactOffset) || 0);
  const pages = (route.artifactPages || '').split(',').filter(Boolean).map(Number).filter(Number.isFinite);
  const setPath = value => onNavigate({ artifact: typeof value === 'function' ? value(path) : value });
  const setQuery = artifactQuery => onNavigate({ artifactQuery }, true);
  const setGroup = artifactGroup => onNavigate({ artifactGroup }, true);
  const setRun = artifactRun => onNavigate({ artifactRun }, true);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    setError(""); setLoading(true);
    fetch(`/api/scenario/artifacts?scenario=${encodeURIComponent(scenario)}`, { signal: abort.signal })
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw Error(data.detail); return data; })
      .then((data) => {
        setItems(data.artifacts);
        setPath((current) => current ||
          [...data.artifacts].reverse().find((item) => item.name === "missing.json")?.path || data.artifacts[0]?.path || "");
      }).catch((err) => { if (!abort.signal.aborted) setError(err.message); })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [scenario, refresh]);
  useEffect(() => {
    if (!path) return;
    const abort = new AbortController();
    setPayload(null); setError("");
    fetch(`/api/scenario/artifact?${new URLSearchParams({ scenario, path, offset, limit: 100 })}`, { signal: abort.signal })
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw Error(data.detail); return data; })
      .then(setPayload).catch((err) => { if (!abort.signal.aborted) setError(err.message); });
    return () => abort.abort();
  }, [scenario, path, offset, refresh]);
  function open(next) { onNavigate({ artifact: next, artifactOffset: "", artifactPages: "" }); }
  const filtered = items.filter((item) => (!group || item.group === group) && (!run || item.run === run) && item.path.toLowerCase().includes(query.toLowerCase()));
  const gaps = gapRows(payload?.data);
  const coverage = manifestRows(payload?.data);
  return <div className="artifact-workspace">
    <aside className="artifact-list">
      <label><span>Find artefacts</span><input type="search" aria-label="Find artefacts" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="missing, manifest, observations…" /></label>
      <label><span>Stage</span><select aria-label="Artefact stage" value={group} onChange={(e) => { setGroup(e.target.value); setRun(""); }}><option value="">All stages</option>
        {[...new Set(items.map((item) => item.group))].map((name) => <option key={name}>{name}</option>)}
      </select></label>
      <label><span>Run</span><select aria-label="Artefact run" value={run} onChange={(e) => setRun(e.target.value)}><option value="">All runs</option>
        {[...new Set(items.filter((item) => !group || item.group === group).map((item) => item.run).filter(Boolean))].reverse().map((name) => <option key={name}>{name}</option>)}
      </select></label>
      <div className="section-heading"><small>{filtered.length} files</small><button type="button" onClick={() => setRefresh((v) => v + 1)}>Refresh files</button></div>
      <div className="artifact-file-list">{filtered.map((item) => <button key={item.path} type="button" aria-current={path === item.path ? "true" : undefined} onClick={() => open(item.path)}>
        <strong>{item.name}</strong><small>{item.path}</small><small>{Math.ceil(item.size / 1024)} KB</small>
      </button>)}</div>
      {!loading && !filtered.length && <p>No matching artefacts.</p>}
    </aside>
    <section className="artifact-detail" aria-label="Artefact preview">
      <div className="section-heading"><h3>{path || "Collection artefacts"}</h3>{path && <a href={`/api/scenario/artifact/download?${new URLSearchParams({ scenario, path })}`}>Download original</a>}</div>
      {error && <p role="alert" className="error">{error}</p>}
      {!payload && !error && <p>{loading || path ? "Loading artefact…" : "No collection artefacts yet."}</p>}
      {payload && <>
        {payload.truncated && <p className="brief-callout">Partial preview. Download the original for the complete file{payload.next_offset != null ? ", or page through the records below" : ""}.</p>}
        {payload.parse_error && <p role="alert" className="error">Invalid JSON: {payload.parse_error}</p>}
        {gaps && <Gaps key={path} data={payload.data} rows={gaps} />}
        {coverage && <Coverage data={payload.data} rows={coverage} onOpen={(relative) => {
          const parent = path.slice(0, path.lastIndexOf("/") + 1);
          const target = parent + relative;
          if (items.some((item) => item.path === target)) { setGroup(""); setRun(""); setQuery(""); open(target); }
          else setError(`Referenced file is not available: ${target}`);
        }} />}
        {payload.records && <><p>Records {payload.records.length ? offset + 1 : 0}–{offset + payload.records.length}{payload.next_offset != null ? " · more available" : " · end of file"}</p>
          <RecordPlot key={path} records={payload.records} /><RecordsTable rows={payload.records} />
          <div className="notice-actions"><button type="button" disabled={!pages.length} onClick={() => { onNavigate({ artifactOffset: String(pages[pages.length - 1]), artifactPages: pages.slice(0, -1).join(",") }); }}>Previous page</button>
            <button type="button" disabled={payload.next_offset == null} onClick={() => { onNavigate({ artifactOffset: String(payload.next_offset), artifactPages: [...pages, offset].join(",") }); }}>Next page</button></div>
        </>}
        {!gaps && !coverage && payload.data && <>{Array.isArray(payload.data) ? <RecordsTable rows={payload.data.slice(0, 100)} /> :
          <dl className="artifact-properties">{Object.entries(payload.data).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{typeof value === "object" && value !== null ? <details><summary>Inspect {Array.isArray(value) ? `${value.length} entries` : "fields"}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details> : printable(value)}</dd></div>)}</dl>}
          {Array.isArray(payload.data) && payload.data.length > 100 && <p>Table shows the first 100 entries; the raw preview below contains the full array.</p>}</>}
        {payload.format === "md" && <MarkdownPreview text={payload.text} />}
        <details className="artifact-raw" open={Boolean(payload.parse_error) || (!payload.data && !payload.records)}><summary>Raw {payload.format.toUpperCase()}{payload.records ? " · current page" : ""}</summary><pre>{payload.text}</pre></details>
      </>}
    </section>
  </div>;
}
