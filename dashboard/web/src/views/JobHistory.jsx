import { useEffect, useState } from 'react';
import { humanize } from '../lib/workspace.js';
export default function JobHistory({ onOpen, onSelectJob }) {
  const [jobs, setJobs] = useState([]), [error, setError] = useState('');
  const [scenario, setScenario] = useState('');
  useEffect(() => {
    let gone = false;
    const tick = () => fetch('/api/operator/jobs').then(async r => { if (!r.ok) throw Error('Command history could not be refreshed'); return r.json(); }).then(d => { if (!gone) { setJobs(d.jobs); setError(''); } }).catch(e => { if (!gone) setError(e.message); });
    tick(); const id = setInterval(tick, 3000); return () => { gone = true; clearInterval(id); };
  }, []);
  return <section className="notice-card operator-panel" aria-label="Command history"><h2>Command history</h2><p>Latest 100 commands, retained across reloads. Outcomes describe execution, not analytical truth.</p>
    {error && <p role="alert">{error}</p>}
    <label>History scenario<select value={scenario} onChange={e => setScenario(e.target.value)}><option value="">All scenarios</option>{[...new Set(jobs.map(j => j.inputs.scenario))].map(s => <option key={s}>{s}</option>)}</select></label>
    {!jobs.length && <p>No command receipts yet. Historical artefacts remain available in Scenarios.</p>}
    {jobs.filter(j => !scenario || j.inputs.scenario === scenario).map(j => {
      const result = j.result || {}, scenarioId = j.inputs.scenario;
      const measure = result.measure?.measure_id || j.inputs.measurement_id;
      const notices = result.emit?.notices?.map(n => n.notice_id) || result.notice_ids || (result.notice_id ? [result.notice_id] : []);
      return <details key={j.id}><summary>{j.action} · {scenarioId} · {humanize(j.state)} · {j.started_at}</summary>
        <p>Started {j.started_at}{j.finished_at ? ` · Finished ${j.finished_at}` : ''}</p>
        {j.error && <p role="alert">{j.error}</p>}
        {j.inputs.notice_id && <button type="button" onClick={() => onOpen({ surface: 'notices', notice: j.inputs.notice_id, tab: 'notes', step: 'review' })}>Open notice review and current findings</button>}
        {j.state !== 'running' && ['research and draft', 'secondary collection'].includes(j.action) && <button type="button" onClick={() => { try { localStorage.removeItem(`wsd-machine-request:${j.inputs.notice_id}`); localStorage.removeItem(`wsd-collection-request:${j.inputs.notice_id}`); localStorage.removeItem(`wsd-machine-job:${j.inputs.notice_id}`); } catch { /* no browser receipt */ } onOpen({ surface: 'notices', notice: j.inputs.notice_id, tab: 'collection' }); }}>Plan a new research attempt after inspecting outputs</button>}
        {j.state === 'running' && j.action !== 'backtest' && <p>This request may continue if the browser disconnects. Reopen this receipt to observe it; cancelling an in-flight research/model request is not supported.</p>}

        {j.action === 'backtest' && <button type="button" onClick={() => onSelectJob(j.id)}>Open run progress and outputs</button>}
        {result.stages && <p>Completed stages: {result.stages.join(' → ')}</p>}
        {(result.n_notices != null || result.emit) && <p>{result.n_notices ?? result.emit.n_notices} notices returned. Existing notices may be included.</p>}
        {measure && <button type="button" onClick={() => onOpen({ surface: 'anomaly', result: `${scenarioId}/${measure}`, scenario: scenarioId })}>Open measurement</button>}
        {notices.map(id => <button key={id} type="button" onClick={() => onOpen({ surface: 'notices', notice: id, tab: 'overview' })}>Open {id}</button>)}
        <button type="button" onClick={() => onOpen({ surface: 'scenarios', scenario: scenarioId, scenarioTab: 'artifacts' })}>Open scenario outputs</button>
        <details><summary>Inputs and raw receipt</summary><pre className="ops-log">{JSON.stringify(j, null, 2)}</pre></details>
      </details>;
    })}
  </section>;
}
