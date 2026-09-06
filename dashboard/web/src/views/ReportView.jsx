import { useEffect, useRef, useState } from "react";
import { readDraft, writeDraft, clearDraft as removeDraft } from "../lib/drafts.js";
import AnalystWorkflow from "./AnalystWorkflow.jsx";

// A seed offered once must not replace edited text when this notice is remounted.
const handledMachineSeeds = new Set();

// Analyst content is always rendered as text, never interpreted as HTML.
function Prose({ text }) {
  return <div className="report-read">{text.split(/\n\s*\n/).map((part, index) =>
    /^#{1,6}\s/.test(part) ? <h4 key={index}>{part.replace(/^#{1,6}\s/, "")}</h4> : <p key={index}>{part}</p>)}</div>;
}

export default function ReportView({ scenario, noticeId, report, busy, onSave, onDraftChange, machineSeed, evidenceReview, onReset, step: routeStep, onStepChange }) {
  const panel = useRef(null);
  const [workflowStep, setWorkflowStep] = useState(() => readDraft(noticeId, localStorage) !== null ? "assessment" : "review");
  const step = routeStep || workflowStep;
  function onStep(id) {
    setWorkflowStep(id);
    onStepChange?.(id);
  }
  useEffect(() => { panel.current?.closest(".notice-body")?.scrollTo(0, 0); }, [step]);
  const [draft, setDraft] = useState(() => readDraft(noticeId, localStorage));
  const [editing, setEditing] = useState(draft !== null);
  const [storageError, setStorageError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [handledSeed, setHandledSeed] = useState("");
  const seedKey = machineSeed ? `${machineSeed.noticeId}:${machineSeed.at}` : "";
  const pendingSeed = machineSeed?.noticeId === noticeId && machineSeed.notes &&
    !handledMachineSeeds.has(seedKey) && handledSeed !== seedKey;
  const saved = report?.empty ? "" : report?.notes || "";
  const value = draft ?? saved;
  const dirty = draft !== null && draft !== saved;
  useEffect(() => { onDraftChange?.(noticeId, dirty); }, [noticeId, dirty, onDraftChange]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function change(text) {
    setDraft(text);
    const persisted = writeDraft(noticeId, text, localStorage);
    setStorageError(persisted ? "" : "Browser storage is unavailable. Your draft is retained for this session only; save before closing or reloading.");
  }
  function clearDraft() {
    setDraft(null);
    removeDraft(noticeId, localStorage);
    onDraftChange?.(noticeId, false);
  }
  async function save() {
    setSaveError("");
    const savedReport = await onSave(value);
    if (savedReport) { clearDraft(); setEditing(false); onStep("brief"); }
    else setSaveError("Notes were not saved. Your draft is retained; please retry.");
  }
  return <section ref={panel} className="assessment-panel">
    <div className="section-heading"><div><p className="eyebrow">Human assessment</p><h3>Your notes & assessment</h3></div>
      <span className={dirty ? "draft-badge" : "notice-timing"}>{dirty ? "Unsaved draft" : report?.updated_at && !report.empty ? `Saved ${String(report.updated_at).replace("T", " ").slice(0, 19)} UTC` : "No saved assessment"}</span>
    </div>
    <p className="notice-timing">Your interpretation, separate from the generated brief. Unsaved drafts are retained in this browser for each notice.</p>
    <AnalystWorkflow scenario={scenario} noticeId={noticeId} report={report} evidenceReview={evidenceReview}
      step={step} onStepChange={onStep} dirty={dirty} busy={busy} value={value} onReset={(resetReport) => { clearDraft(); setEditing(false); onReset(resetReport); }} onAssemble={(material) => {
        const start = "<!-- reviewed-material:start -->";
        const end = "<!-- reviewed-material:end -->";
        const block = `${start}\n${material}\n${end}`;
        const from = value.indexOf(start), to = value.indexOf(end);
        if (from >= 0 && to >= from) {
          if (!window.confirm("Update the reviewed material section? Edits inside that section will be replaced; your writing outside it is retained.")) return;
          change(value.slice(0, from) + block + value.slice(to + end.length));
        } else change([value.trim(), block].filter(Boolean).join("\n\n"));
        setEditing(true);
        onStep("assessment");
      }}>
    {pendingSeed && <section className="brief-callout" aria-label="Machine draft ready">
      <h3>Machine draft ready for review</h3>
      <p>This is the original, unfiltered machine draft. It does not incorporate your review decisions. Use reviewed material above to build from retained findings; check any whole-draft import for rejected claims.</p>
      <details><summary>Preview machine draft</summary><Prose text={machineSeed.notes} /></details>
      <div className="notice-actions">
        <button type="button" disabled={busy} onClick={() => {
          if (value.trim() && !window.confirm("Replace the editor text with this machine draft? Unsaved edits will be replaced; your saved report is unchanged.")) return;
          change(machineSeed.notes); setEditing(true);
          handledMachineSeeds.add(seedKey); setHandledSeed(seedKey);
        }}>Use machine draft</button>
        <button type="button" onClick={() => { handledMachineSeeds.add(seedKey); setHandledSeed(seedKey); }}>Keep my assessment</button>
      </div>
    </section>}
    <h3 id="working-assessment">3. Add your judgement and save the assessment</h3>
    <p>Develop the key judgement, implications and alternatives below. Saving enables the assessment PDF for intelligence colleagues and takes you to step 4 to prepare the senior-leadership brief.</p>
    {!report && <p role="status">Assessment unavailable or loading. You can still write a local draft.</p>}
    {editing ? <>
      <label className="sr-only" htmlFor="assessment-text">Your notes and assessment</label>
      <textarea id="assessment-text" className="report-single" value={value} disabled={busy} rows={18} onChange={(e) => change(e.target.value)} />
      {report?.empty && report.notes && !value && <button type="button" onClick={() => change(report.notes)}>Use generated template</button>}
      <div className="notice-actions">
        <button className="primary-action" type="button" disabled={busy || !report} onClick={save}>{busy ? "Saving…" : "Save assessment"}</button>
        <button type="button" onClick={() => setEditing(false)}>Preview</button>
        {dirty && <button type="button" disabled={busy} onClick={() => { if (window.confirm("Discard this notice’s unsaved draft? Saved notes will be kept.")) clearDraft(); }}>Discard draft</button>}
      </div>
    </> : <>
      <button type="button" className="primary-action" onClick={() => setEditing(true)}>{value ? "Edit assessment" : "Write assessment"}</button>
      {value ? <Prose text={value} /> : <p className="empty">No assessment yet. Record your interpretation, alternative explanations, and next questions here.</p>}
      {value && !dirty && <p className="notice-actions"><button type="button" className="primary-action" onClick={() => onStep("brief")}>Continue to intelligence brief →</button></p>}
    </>}
    </AnalystWorkflow>
    {storageError && <p role="alert" className="error">{storageError}</p>}
    {saveError && <p role="alert" className="error">{saveError}</p>}
  </section>;
}
