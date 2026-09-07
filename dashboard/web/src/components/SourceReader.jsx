import { humanize } from '../lib/workspace.js';
export default function SourceReader({ item }) {
  const data = item.data || {};
  const url = [data.archive_url, data.url].find(value => typeof value === 'string' && /^https?:\/\//i.test(value));
  const passage = typeof data.text === 'string' ? data.text : null;
  const fields = ['series_id', 'evidence_time', 'geographic_scope', 'aoi_name', 'aoi_id', 'value', 'quality', 'sensing_at', 'version_at', 'originating_source', 'source_tier', 'offset_start', 'offset_end', 'parent_id'];
  return <details><summary>{data.title || humanize(item.kind)} · {humanize(item.verification || 'Verification not recorded')}</summary>
    <section aria-label="Source reader"><p>{item.source_ref}</p>
      <p>Available: {item.available_at || 'Not recorded'} · Retrieved: {item.retrieved_at || data.retrieved_at || 'Not recorded'}</p>
      <p>Shared source dependency: {item.dependency_group || 'Not recorded; independence is not established'}</p>
      {url && <a href={url} target="_blank" rel="noreferrer">Open recorded source version</a>}
      {passage ? <><h5>{item.kind === 'document_passage' ? 'Recorded source passage' : 'Recorded evidence text'}</h5><blockquote style={{whiteSpace:'pre-wrap', overflowWrap:'anywhere'}}>{passage}</blockquote></> : <p>No passage text is included in this evidence item. Inspect the linked version or recorded data; absence here does not establish absence in the source.</p>}
      <dl>{fields.filter(k => k in data).map(k => <div key={k}><dt>{humanize(k)}</dt><dd>{data[k] == null ? 'Unknown' : typeof data[k] === 'object' ? JSON.stringify(data[k]) : String(data[k])}</dd></div>)}</dl>
      <details><summary>Evidence ID and original record</summary><p>{item.id}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(item,null,2)}</pre></details>
    </section>
  </details>;
}
