import { useEffect, useState } from "react";

const SOURCES = [
  ["official_pack", "Government actions", "Retrieve published travel-advice changes and assemble official measures."],
  ["refresh_physical", "Satellite availability and recorded observations", "Check imagery catalogues and assemble existing FIRMS, VIIRS and SAR observations. This does not analyse new imagery."],
  ["chronology", "Signal chronology", "Assemble the dated observations already collected for this notice."],
  ["open_source_search", "Public reporting leads", "Search for dated public reports. Full document retrieval and cutoff checks follow in assessment research."],
];

export default function SecondaryCollection({ cutoff, busy, onRun, collection }) {
  const [selected, setSelected] = useState(["official_pack", "refresh_physical", "open_source_search"]);
  const [run, setRun] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (run?.status !== "running") return;
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - run.started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [run]);
  async function start(event) {
    event.preventDefault();
    setElapsed(0);
    setRun({ status: "running", started: Date.now(), sources: [...selected] });
    try {
      const result = await onRun(selected);
      setRun(previous => ({ ...previous, status: result?.job_id ? "queued" : result ? "returned" : "failed", result: result?.job_id ? null : result }));
    } catch {
      setRun(previous => ({ ...previous, status: "failed" }));
    }
  }
  const running = run?.status === "running";
  const results = run?.result || collection;
  return <section className="brief-callout" aria-label="Start secondary collection">
    <h3>1. Start secondary collection</h3>
    <p>Gather supporting material for this notice. Choose the source jobs to run again, then inspect their results below.</p>
    <p>Information cutoff: {cutoff || "Recorded on the notice"}. Each job keeps this cutoff.</p>
    <form onSubmit={start}>
      <fieldset disabled={busy || running}>
        <legend>Sources to collect</legend>
        {SOURCES.map(([kind, title, description]) => <label key={kind} style={{ display: "block", marginBottom: "12px" }}>
          <input type="checkbox" checked={selected.includes(kind)} onChange={event => setSelected(current => event.target.checked ? [...current, kind] : current.filter(item => item !== kind))} /> <strong>{title}</strong>
          <span style={{ display: "block", marginLeft: "24px", textTransform: "none", letterSpacing: "normal", fontWeight: "normal", fontSize: "14px" }}>{description}</span>
        </label>)}
      </fieldset>
      <p>The document-research limits in step 3 apply to that later search, not these source jobs.</p>
      <div className="notice-actions"><button className="primary-action" type="submit" disabled={busy || running || !selected.length}>
        {running ? "Collecting selected sources…" : "Start secondary collection"}
      </button></div>
    </form>
    {run && <p role="status">{running ? `${elapsed}s elapsed · Waiting for ${run.sources.length} source jobs. Results appear when they return.` : run.status === "queued" ? "Collection job recorded. Progress and outcomes reconnect after reload; inspect each source result below." : run.status === "failed" ? "Collection did not complete. See the error above; previous results are retained." : "Source jobs returned. Check each status and explanation below; a returned job may contain gaps or failures."}</p>}
    <h3>2. Review collection results</h3>
    {!results?.tasks?.length ? <p>No source-job results for this notice yet.</p> : <ul>
      {results.tasks.map(task => <li key={task.kind}>
        <strong>{SOURCES.find(([kind]) => kind === task.kind)?.[1] || task.title}: {task.status}</strong>
        <p>{task.summary}</p>
        <small>Last run: {task.ran_at || "Not recorded"}</small>
      </li>)}
    </ul>}
  </section>;
}
