import { useEffect, useState } from 'react';
export default function FollowupCollection({ scenario, noticeId, reviewVersion, onComplete }) {
  const [options, setOptions] = useState(null), [choice, setChoice] = useState('');
  const [sources, setSources] = useState(''), [queries, setQueries] = useState(3), [documents, setDocuments] = useState(4), [seconds, setSeconds] = useState(120);
  const [jobId, setJobId] = useState(() => { try { return localStorage.getItem(`followup:${scenario}:${noticeId}`) || ''; } catch { return ''; } });
  const [job, setJob] = useState(null), [error, setError] = useState(''), [pending, setPending] = useState(false);
  async function read(url) { const r = await fetch(url); const d = await r.json(); if (!r.ok) throw Error(d.detail || 'Follow-up unavailable'); return d; }
  useEffect(() => {
    let gone = false;
    read(`/api/followup/options?${new URLSearchParams({scenario, notice_id: noticeId})}`).then(d => { if (!gone) { setOptions(d); setChoice(d.questions[0]?.id || ''); } }).catch(e => { if (!gone) setError(e.message); });
    return () => { gone = true; };
  }, [scenario, noticeId, reviewVersion]);
  useEffect(() => {
    if (!jobId) return;
    let gone = false;
    const tick = () => read(`/api/operator/job/${jobId}`).then(d => { if (!gone) setJob(d); }).catch(e => { if (!gone) setError(e.message); });
    tick(); const timer = setInterval(tick, 2000); return () => { gone = true; clearInterval(timer); };
  }, [jobId]);
  async function run() {
    setPending(true); setError('');
    try {
      const requestKey = `followup-request:${scenario}:${noticeId}`;
      const requestId = localStorage.getItem(requestKey) || crypto.randomUUID();
      localStorage.setItem(requestKey, requestId);
      const r = await fetch('/api/followup/run', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({scenario, notice_id:noticeId, request_id: requestId, review_version:options.review_version, question_id:choice, source_preference:sources, queries:Number(queries), documents:Number(documents), seconds:Number(seconds)}) });
      const d = await r.json(); if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
      setJobId(d.id); setJob({state:'running'}); try { localStorage.setItem(`followup:${scenario}:${noticeId}`, d.id); } catch { /* Server retains job */ }
    } catch(e) { setError(e.message); } finally { setPending(false); }
  }
  return <section aria-label="Requirement-specific follow-up"><h4>Plan follow-up collection</h4>
    <p>Select an unresolved collection question or hypothesis discriminator. Running this plan searches public sources and prepares new findings for review; your saved assessment is preserved.</p>
    {options?.questions.length ? <fieldset disabled={pending || job?.state === 'running'}>
      <label>Collection question<select value={choice} onChange={e => setChoice(e.target.value)}>{options.questions.map(q => <option key={q.id} value={q.id}>{q.question}</option>)}</select></label>
      <p>{options.questions.find(q => q.id === choice)?.reason}</p>
      <p>Mode: {options.clocks.mode} · Evidence cutoff: {options.clocks.knowledge_cutoff}. Actor and geography come from this notice's packet.</p>
      <label>Preferred source or geographic detail (search terms, not a strict source filter)<input maxLength={160} value={sources} onChange={e => setSources(e.target.value)} /></label>
      <label>Maximum search requests<input type="number" min={1} max={12} value={queries} onChange={e => setQueries(e.target.value)} /></label>
      <label>Maximum document attempts<input type="number" min={1} max={12} value={documents} onChange={e => setDocuments(e.target.value)} /></label>
      <label>Research scheduling budget (seconds)<input type="number" min={30} max={300} value={seconds} onChange={e => setSeconds(e.target.value)} /></label>
      <p>The budget bounds research scheduling; an in-flight request and subsequent model drafting may take longer. Source preferences are query terms. A saved request is not evidence of completed collection.</p>
      <button type="button" onClick={run}>Run this follow-up plan</button>
    </fieldset> : <p>No collection questions or discriminators recorded in this review.</p>}
    {error && <p role="alert">{error}</p>}
    {job && <div role="status"><p>Follow-up {job.state} · {job.progress?.stage}</p>{job.error && <p>{job.error}</p>}
      {job.state !== 'running' && <button type="button" onClick={() => { localStorage.removeItem(`followup-request:${scenario}:${noticeId}`); setJob(null); setJobId(''); }}>Plan another follow-up after inspecting this outcome</button>}
      {job.state === 'completed' && <><p>New findings are available. Changed proposals require renewed review; previous decisions remain in history.</p><button type="button" onClick={onComplete}>Open updated findings for review</button></>}
    </div>}
  </section>;
}
