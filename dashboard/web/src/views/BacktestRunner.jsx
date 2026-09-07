import JobHistory from "./JobHistory.jsx";
import { useEffect, useState } from "react";
import { sourceLabel, humanize } from "../lib/workspace.js";
const STAGES = ['validate', 'collect', 'review', 'measure', 'emit'];
const LABELS = { validate: 'Validate configuration', collect: 'Collect corpus', review: 'Review corpus quality', measure: 'Measure signals', emit: 'Emit notices' };
async function request(url, body) {
  const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const data = await r.json();
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
export default function BacktestRunner({ onOpen, initialScenario }) {
  const [scenarios, setScenarios] = useState([]), [scenario, setScenario] = useState('');
  const [start, setStart] = useState('validate'), [through, setThrough] = useState('emit');
  const [only, setOnly] = useState(''), [focus, setFocus] = useState('');
  const [mock, setMock] = useState(false), [exploratory, setExploratory] = useState(true);
  const [workers, setWorkers] = useState(4), [plan, setPlan] = useState(null);
  const [job, setJob] = useState(null), [jobId, setJobId] = useState(() => { try { return localStorage.getItem('wsd-backtest-job') || ''; } catch { return ''; } });
  const [error, setError] = useState(''), [pending, setPending] = useState(false), [name, setName] = useState('');
  useEffect(() => { request('/api/scenarios').then(d => { setScenarios(d.scenarios); setScenario(d.scenarios.some(s => s.scenario_id === initialScenario) ? initialScenario : d.scenarios[0]?.scenario_id || ''); }).catch(e => setError(e.message)); }, []);
  useEffect(() => { setPlan(null); }, [scenario, start, through, only, focus, mock, exploratory, workers]);
  useEffect(() => {
    if (!jobId) return;
    try { localStorage.setItem('wsd-backtest-job', jobId); } catch { /* history remains on server */ }
    let cancelled = false;
    const tick = () => request(`/api/operator/job/${jobId}`).then(d => { if (!cancelled) setJob(d); }).catch(e => { if (!cancelled) setError(e.message); });
    tick(); const id = setInterval(tick, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, [jobId]);
  const body = { scenario, start, through, only: only.split(',').map(s => s.trim()).filter(Boolean), focus, mock, exploratory, source_workers: Number(workers) };
  async function action(fn) { setPending(true); setError(''); try { await fn(); } catch(e) { setError(e.message); } finally { setPending(false); } }
  const running = pending || job?.state === 'running';
  return <><section className="notice-card" aria-label="Backtest runner">
    <h2>Run a historical backtest</h2><p>Finite historical replay. Continuous realtime watch is not implemented; an agent heartbeat does not mean collection is scheduled.</p>
    <details><summary>Create scenario</summary><label>New scenario name<input value={name} onChange={e => setName(e.target.value)} placeholder="example-case" /></label>
      <button type="button" disabled={running || !name} onClick={() => action(async () => { await request('/api/operator/create', { scenario: name }); onOpen({ surface: 'scenarios', scenario: name }); })}>Create and edit scenario</button></details>
    <fieldset disabled={running}><div className="ops-fields">
      <label>Backtest scenario<select value={scenario} onChange={e => setScenario(e.target.value)}>{scenarios.map(s => <option key={s.scenario_id}>{s.scenario_id}</option>)}</select></label>
      <label>First stage<select value={start} onChange={e => setStart(e.target.value)}>{STAGES.map(s => <option key={s} value={s}>{LABELS[s]}</option>)}</select></label>
      <label>Last stage<select value={through} onChange={e => setThrough(e.target.value)}>{STAGES.map(s => <option key={s} value={s}>{LABELS[s]}</option>)}</select></label>
      <label>Gap repair review path<input value={focus} onChange={e => setFocus(e.target.value)} placeholder="reviews/review-id/missing.json (optional)" /></label>
    </div><details><summary>Sources and execution options</summary>
      <label>Source IDs (comma separated; blank uses enabled sources)<input value={only} onChange={e => setOnly(e.target.value)} /></label>
      <label>Concurrent sources<input type="number" min="1" max="8" value={workers} onChange={e => setWorkers(e.target.value)} /></label>
      <label><input type="checkbox" checked={mock} onChange={e => setMock(e.target.checked)} />Synthetic rehearsal (stops before measurement)</label>
      <label><input type="checkbox" checked={exploratory} onChange={e => setExploratory(e.target.checked)} />Allow exploratory measurement without a real freeze</label>
    </details><button type="button" disabled={!scenario} onClick={() => action(async () => setPlan(await request('/api/operator/plan', body)))}>Preview run plan</button></fieldset>
    {error && <p role="alert" className="error">{error}</p>}
    {plan && <section aria-label="Run plan"><h3>{plan.mode}</h3><p>{plan.stages.map(s => LABELS[s]).join(' → ')}</p><p>{plan.measurement}</p>
      <p>Sources: {plan.sources.map(sourceLabel).join(', ')}</p>
      <ul>{plan.windows.map(w => <li key={w.id}>{w.id}: {w.start}–{w.end}, lookback {w.lookback_days} days</li>)}</ul>
      <p>Historical evidence uses the scenario windows; notice packet replay uses episode-end cutoff. This action ends at {LABELS[through]}; it does not generate an assessment or finished brief.</p>
      <details><summary>Input identities and options</summary><pre>{JSON.stringify(plan, null, 2)}</pre></details>
      <button type="button" disabled={running} onClick={() => action(async () => { setJob(null); const d = await request('/api/operator/run', { ...body, revision: plan.revision }); setJobId(d.id); })}>Run this backtest plan</button>
    </section>}
    {job && <section aria-label="Backtest output"><h3>{humanize(job.state)}</h3><p role="status">{job.progress?.message || 'Starting'} · {job.progress?.elapsed_s ?? 0}s</p>
      {job.error && <p role="alert">{job.error}</p>}
      {job.result && <><p>Completed stages: {job.result.stages.map(s => LABELS[s]).join(' → ')}</p>
        {job.result.emit && <p>{job.result.emit.n_notices} notices. Zero notices is a valid outcome.</p>}
        {job.result.measure && <button type="button" onClick={() => onOpen({ surface: 'anomaly', result: `${(job.plan?.scenario || job.inputs.scenario)}/${job.result.measure.measure_id}` })}>Open measurement results</button>}
        <button type="button" onClick={() => onOpen({ surface: 'scenarios', scenario: (job.plan?.scenario || job.inputs.scenario), scenarioTab: 'artifacts' })}>Inspect collection and review artefacts</button>
        {job.result.emit?.notices.map(n => <button key={n.notice_id} type="button" onClick={() => onOpen({ surface: 'notices', notice: n.notice_id, tab: 'overview' })}>Open notice {n.start}</button>)}
        {job.result.review?.review_id && <button type="button" onClick={() => { setStart('collect'); setFocus(`reviews/${job.result.review.review_id}/missing.json`); setPlan(null); }}>Plan focused gap repair</button>}
      </>}
      <details><summary>Raw command output</summary><pre>{JSON.stringify(job.result || {}, null, 2)}</pre></details>
    </section>}
  </section><JobHistory onOpen={onOpen} onSelectJob={setJobId} /></>;
}
