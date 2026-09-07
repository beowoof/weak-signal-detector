import { sourceLabel } from "../lib/workspace.js";
import { useEffect, useState } from "react";
import ArtifactsView from "./ArtifactsView.jsx";

const drafts = new Map();
const keyFor = (id) => `wsd-scenario-draft:${id}`;
function readDraft(id) {
  if (drafts.has(id)) return drafts.get(id);
  try { return JSON.parse(localStorage.getItem(keyFor(id))); } catch { return null; }
}
async function request(url, body) {
  const response = await fetch(url, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  const data = await response.json();
  if (!response.ok) throw Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data;
}

function ScenarioEditor({ scenario, snapshot, onSaved }) {
  const [draft, setDraft] = useState(() => readDraft(scenario));
  const [mode, setMode] = useState("form");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [storageWarning, setStorageWarning] = useState("");
  const text = draft?.text ?? snapshot.text;
  const revision = draft?.revision ?? snapshot.revision;
  const dirty = text !== snapshot.text;
  let doc;
  try { doc = JSON.parse(text); } catch { /* Raw editor can repair invalid JSON. */ }
  const object = (value) => value && typeof value === "object" && !Array.isArray(value);
  const formReady = object(doc) && object(doc.actors) && object(doc.incident) &&
    Array.isArray(doc.actors.counterparts) && Array.isArray(doc.controls) && doc.controls.every(object) &&
    object(doc.sources) && Object.values(doc.sources).every(object);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function update(nextText) {
    const next = { text: nextText, revision };
    setDraft(next); drafts.set(scenario, next); setMessage(""); setError("");
    try { localStorage.setItem(keyFor(scenario), JSON.stringify(next)); setStorageWarning(""); }
    catch { setStorageWarning("Browser storage is unavailable. This draft is retained only until the page reloads."); }
  }
  function clear() {
    setDraft(null); drafts.delete(scenario);
    try { localStorage.removeItem(keyFor(scenario)); } catch { /* session cleared */ }
  }
  function edit(path, value) {
    const next = structuredClone(doc);
    let target = next;
    for (const key of path.slice(0, -1)) { target[key] ??= {}; target = target[key]; }
    target[path[path.length - 1]] = value;
    update(JSON.stringify(next, null, 2) + "\n");
  }
  async function submit(save) {
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await request(`/api/scenario/${save ? "save" : "validate"}`, { scenario, text, revision });
      if (save) { clear(); onSaved(data); }
      setMessage(`${save ? "Scenario saved. Existing artefacts are unchanged; no collection was started." : "Scenario is valid."} ${(data.warnings || []).join(" ")}`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  function field(label, path, value, type = "text") {
    return <label key={path.join(".")}><span>{label}</span><input aria-label={label} type={type} value={value ?? ""}
      onChange={(e) => edit(path, type === "number" ? Number(e.target.value) : e.target.value || (type === "date" ? null : ""))} /></label>;
  }
  return <section className="scenario-editor">
    <div className="section-heading"><div><h2>Scenario contract</h2><p className="notice-timing">scenario.json · {dirty ? "Unsaved local draft" : "Matches file on disk"}</p></div>
      <div className="notice-actions"><button type="button" disabled={busy} onClick={() => submit(false)}>Validate</button>
        <button type="button" className="primary-action" disabled={busy || !dirty || snapshot.frozen} onClick={() => submit(true)}>{busy ? "Working…" : "Save scenario"}</button>
        {draft && <button type="button" disabled={busy} onClick={() => { if (confirm("Discard this scenario draft and use the current file on disk?")) { clear(); setError(""); setMessage(""); } }}>Discard draft</button>}
      </div>
    </div>
    <p className="notice-timing">Editing changes the current contract for future work. Existing collections, reviews and measurements retain their original configuration. Advanced JSON preserves every field.</p>
    {snapshot.frozen && <p className="brief-callout">This scenario has a freeze record and is read-only here. Use a separate scenario for revised work.</p>}
    {draft && revision !== snapshot.revision && <p role="alert" className="brief-callout">The file changed since this draft began. Copy your draft before discarding it, then reconcile against the current file. Saving is blocked until revisions match.</p>}
    {storageWarning && <p role="alert" className="error">{storageWarning}</p>}
    <nav className="view-tabs" aria-label="Scenario editor mode"><button type="button" aria-pressed={mode === "form"} onClick={() => setMode("form")}>Fields</button><button type="button" aria-pressed={mode === "json"} onClick={() => setMode("json")}>Advanced JSON</button></nav>
    <fieldset disabled={busy || snapshot.frozen}>
      {mode === "json" || !formReady ? <label><span>Scenario JSON</span><textarea aria-label="Scenario JSON" className="scenario-json" spellCheck={false} value={text} onChange={(e) => update(e.target.value)} /></label> : <>
        <div className="scenario-fields">
          <label className="wide"><span>Research question</span><textarea aria-label="Research question" rows={2} value={doc.research_question || ""} onChange={(e) => edit(["research_question"], e.target.value)} /></label>
          <label><span>Purpose</span><select aria-label="Purpose" value={doc.purpose || "development_showcase"} onChange={(e) => edit(["purpose"], e.target.value)}>{['development_showcase', 'held_out', 'rehearsal'].map((item) => <option key={item} value={item}>{({ development_showcase: "Development case", held_out: "Held-out evaluation case", rehearsal: "Engineering rehearsal" })[item]}</option>)}</select></label>
          {field("Focal actor", ["actors", "focal"], doc.actors?.focal)}
          <label><span>Counterpart actors (comma separated)</span><input key={JSON.stringify(doc.actors.counterparts)} aria-label="Counterpart actors" defaultValue={doc.actors.counterparts.join(", ")} onBlur={(e) => edit(["actors", "counterparts"], e.target.value.split(",").map((v) => v.trim()).filter(Boolean))} /></label>
        </div>
        <h3>Incident and control windows</h3>
        {[{ value: doc.incident, path: ["incident"] }, ...(Array.isArray(doc.controls) ? doc.controls : []).map((value, index) => ({ value, path: ["controls", index] }))].map(({ value, path }) => value && <div className="scenario-window" key={path.join(".")}>
          <h4>{value.id || path[0]}</h4><div className="scenario-fields">
            {field(`${value.id} start`, [...path, "start"], value.start, "date")}
            {field(`${value.id} end`, [...path, "end"], value.end, "date")}
            {field(`${value.id} target start`, [...path, "target_start"], value.target_start, "date")}
            {field(`${value.id} target end`, [...path, "target_end"], value.target_end, "date")}
            {field(`${value.id} lookback days`, [...path, "lookback_days"], value.lookback_days, "number")}
            {field(`${value.id} selection reason`, [...path, "selection_reason"], value.selection_reason)}
          </div>
        </div>)}
        <h3>Enabled sources</h3><div className="source-toggles">{Object.entries(doc.sources || {}).map(([name, source]) => <label key={name}><input type="checkbox" checked={Boolean(source?.enabled)} onChange={(e) => edit(["sources", name, "enabled"], e.target.checked)} />{sourceLabel(name)}<small title="Source identifier">{name}</small></label>)}</div>
        <p className="notice-timing">Queries, corpus gates, model settings and additional fields are editable in Advanced JSON. Enabling a source does not fetch it.</p>
      </>}
    </fieldset>
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p role="status" className="brief-callout">{message}</p>}
  </section>;
}

export default function ScenariosView({ scenario, onSelect }) {
  const [items, setItems] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [tab, setTab] = useState("editor");
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let cancelled = false;
    request("/api/scenarios").then((data) => {
      if (cancelled) return;
      setItems(data.scenarios);
      if (!data.scenarios.some((item) => item.scenario_id === scenario) && data.scenarios[0]) onSelect(data.scenarios[0].scenario_id, true);
    }).catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [version, scenario, onSelect]);
  useEffect(() => {
    if (!scenario) return;
    let cancelled = false;
    setSnapshot(null); setError("");
    request(`/api/scenario?scenario=${encodeURIComponent(scenario)}`).then((data) => { if (!cancelled) setSnapshot(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [scenario, version]);
  return <div className="scenarios-page">
    <header className="page-heading"><p className="eyebrow">Configuration & collection record</p><h1>Scenarios</h1></header>
    <div className="scenario-picker"><label><span>Scenario</span><select aria-label="Scenario file" value={scenario || ""} onChange={(e) => onSelect(e.target.value)}>{items.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.scenario_id}{item.frozen ? " · frozen" : ""}</option>)}</select></label>
      <button type="button" onClick={() => setVersion((v) => v + 1)}>Reload from disk</button></div>
    <nav className="view-tabs" aria-label="Scenario workspace"><button type="button" aria-pressed={tab === "editor"} onClick={() => setTab("editor")}>Scenario editor</button><button type="button" aria-pressed={tab === "artifacts"} onClick={() => setTab("artifacts")}>Collection artefacts</button></nav>
    {error && <p className="error" role="alert">{error}</p>}
    {!snapshot && !error && <p>{items.length || scenario ? "Loading scenario…" : "No scenario files found."}</p>}
    {snapshot?.scenario_id === scenario && <>
      <div hidden={tab !== "editor"}><ScenarioEditor key={`${scenario}:${version}`} scenario={scenario} snapshot={snapshot} onSaved={(data) => setSnapshot((current) => current?.scenario_id === data.scenario_id ? data : current)} /></div>
      <div hidden={tab !== "artifacts"}><ArtifactsView key={`${scenario}:${version}`} scenario={scenario} /></div>
    </>}
  </div>;
}
