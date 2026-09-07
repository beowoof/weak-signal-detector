import ReviewTimeline from "../components/ReviewTimeline.jsx";
import FollowupCollection from "./FollowupCollection.jsx";
import { MarkdownPreview, PDFPreview } from "../components/DocumentPreview.jsx";
import { useEffect, useState } from "react";
import { readDraft, writeDraft, clearDraft } from "../lib/drafts.js";
import { briefProduct } from "../lib/workspace.js";
import EvidenceReview from "./EvidenceReview.jsx";

function BriefDocument({ text }) {
  const blocks = String(text || "").trim().split(/\n\s*\n/);
  return <article className="intelligence-brief" aria-label="Intelligence brief">
    {blocks.map((part, index) => {
      if (/^#\s/.test(part)) return <h3 key={index}>{part.replace(/^#\s+/, "")}</h3>;
      if (/^##\s/.test(part)) return <h4 key={index}>{part.replace(/^##\s+/, "")}</h4>;
      if (/^- /.test(part)) return <p key={index} className="brief-judgement">{part.replace(/^- /, "")}</p>;
      return <p key={index}>{part}</p>;
    })}
  </article>;
}

function FormatDownload({ label, disabled, onPick, primary }) {
  return <div className="format-download">
    <button type="button" className={primary ? "primary-action" : undefined} disabled={disabled} onClick={() => onPick("pdf")}>{label}</button>
    <button type="button" className="format-download-toggle" disabled={disabled} aria-label={`${label} formats`} aria-haspopup="menu">▾</button>
    <div className="format-download-menu" role="menu">
      <button type="button" role="menuitem" disabled={disabled} onClick={() => onPick("pdf")}>PDF</button>
      <button type="button" role="menuitem" disabled={disabled} onClick={() => onPick("md")}>Markdown</button>
      <button type="button" role="menuitem" disabled={disabled} onClick={() => onPick("html")}>HTML</button>
    </div>
  </div>;
}

function BriefProgress({ progress }) {
  const [started] = useState(Date.now);
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const seconds = Math.max(0, Math.floor((now - (progress?.started_at ? Date.parse(progress.started_at) : started)) / 1000));
  const completed = progress?.completed ?? 0;
  return <div className="brief-generation-progress" role="status" aria-live="polite">
    <strong>{progress?.stage || "Sending the assessment to the briefing service…"}</strong>
    <progress aria-label="Brief preparation progress" max={4} value={completed === 1 || !progress ? undefined : completed} />
    <p>{Math.floor(seconds / 60)}m {String(seconds % 60).padStart(2, "0")}s elapsed · {completed} of 4 stages complete</p>
    <p>Prepare inputs → Model drafting → Check output → Save version</p>
    {completed === 1 && <p>The model does not report a completion percentage. The moving bar shows it is still running.</p>}
  </div>;
}

export default function AnalystWorkflow({ scenario, noticeId, report, evidenceReview, dirty, busy, value, onAssemble, onReset, step, onStepChange, onWorkflowChange, children }) {
  const [workflow, setWorkflow] = useState(null);
  useEffect(() => { onWorkflowChange?.(noticeId, workflow); }, [noticeId, workflow, onWorkflowChange]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [success, setSuccess] = useState("");
  const [title, setTitle] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [briefText, setBriefText] = useState(null);
  const [editorialBusy, setEditorialBusy] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [compare, setCompare] = useState(false);
  const [layout, setLayout] = useState(false);
  const [assessmentLayout, setAssessmentLayout] = useState(false);
  const [previewAnnex, setPreviewAnnex] = useState(false);
  const [preview, setPreview] = useState(false);
  const [signOffOpen, setSignOffOpen] = useState(false);
  const query = new URLSearchParams({ scenario, notice_id: noticeId }).toString();
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/analyst-workflow?${query}`).then(async r => {
      if (!r.ok) throw new Error("Could not load saved review decisions. Reload to retry.");
      const data = await r.json();
      if (!cancelled) { setWorkflow(current => current?.revision > data.revision ? current : data); setLoadError(""); }
    }).catch(e => { if (!cancelled) setLoadError(e.message); });
    return () => { cancelled = true; };
  }, [query, evidenceReview, report?.updated_at]);
  useEffect(() => {
    if (!workflow?.preparing && !editorialBusy) return;
    let cancelled = false;
    const timer = setInterval(() => {
      fetch(`/api/analyst-workflow?${query}`).then(r => { if (!r.ok) throw new Error("Unable to refresh briefing status"); return r.json(); })
        .then(data => { if (!cancelled) setWorkflow(current => current?.revision > data.revision ? current : data); })
        .catch(e => { if (!cancelled) setError(e.message); });
    }, 3000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [query, workflow?.preparing, editorialBusy]);
  async function act(action, fields = {}) {
    if (!workflow || pending) return;
    setPending(true); setEditorialBusy(action === "prepare"); setError(""); setSuccess("");
    if (action === "prepare") setWorkflow(current => ({ ...current, brief_progress: null }));
    try {
      const response = await fetch("/api/analyst-workflow", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, notice_id: noticeId, revision: workflow.revision,
          review_version: workflow.review_version, action, ...fields }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) throw new Error(data?.detail || `Briefing service could not save this action (${response.status}). Existing versions are retained.`);
      setWorkflow(data); setAcknowledged(false);
      if (action === "prepare") setSuccess(`Brief version ${data.briefs.at(-1).version} is ready for review.`);
      if (action === "sign_off") setSignOffOpen(false);
      if (action === "reset") {
        for (const b of workflow.briefs) clearDraft(`brief:${scenario}:${noticeId}:${b.version}`, localStorage);
        setBriefText(null); setTitle(""); setReviewer(""); setPreview(false); onReset(data.report);
      }
      return true;
    } catch (e) { setError(e.message); }
    finally { setPending(false); setEditorialBusy(false); }
  }
  const review = workflow?.review;
  const decisions = workflow?.active_decisions || {};
  const total = review ? (review.claims?.length || 0) + (review.hypothesis_updates?.length || 0) + 1 : 0;
  const reviewed = Object.keys(decisions).length;
  const latest = workflow?.briefs.at(-1);
  const selectedBrief = workflow?.briefs.find(b => b.version === selectedVersion) || latest;
  const signedPrior = workflow?.briefs.slice().reverse().find(item => item.signed_off && item.version !== latest?.version);
  useEffect(() => { setAcknowledged(false); setSignOffOpen(false); }, [latest?.version, latest?.stale, report?.updated_at, workflow?.review_version]);
  const briefDraftKey = `brief:${scenario}:${noticeId}:${latest?.version}`;
  useEffect(() => { setBriefText(latest ? readDraft(briefDraftKey, localStorage) : null); }, [briefDraftKey]);
  useEffect(() => {
    if (briefText === null) return;
    const warn = event => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [briefText]);
  const disabled = pending || busy || workflow?.preparing || !workflow;
  const assessmentReady = Boolean(value?.trim()) && !dirty && !report?.empty;
  function downloadBrief(version, format, annex = false) {
    const brief = workflow?.briefs.find(item => item.version === version);
    const kind = annex ? "brief-annex" : brief?.signed_off ? "brief" : "draft-brief";
    const link = document.createElement("a");
    const extra = annex ? "&annex=true" : "";
    link.href = `/api/analyst-workflow/export?${query}&version=${version}&format=${format}${extra}`;
    link.download = `${kind}-v${version}.${format === "md" ? "md" : format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
  function downloadAssessment(format) {
    const link = document.createElement("a");
    link.href = `/api/analyst-workflow/export-assessment?${query}&format=${format}`;
    link.download = `working-assessment.${format === "md" ? "md" : format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
  const canSign = Boolean(latest && !latest.signed_off && !latest.stale);
  return <section className="workflow-panel" aria-label="Assessment to intelligence brief">
    <div className="section-heading"><div><p className="eyebrow">Review → assessment → brief</p>
      <h3>{editorialBusy || workflow?.preparing ? "Preparing intelligence brief" : latest && !latest.stale ? (latest.signed_off ? "Brief signed off" : "Draft brief ready for sign-off") : "Develop your assessment"}</h3></div>
      <span role="status">{reviewed} / {total} proposals reviewed</span></div>
    <nav className="workflow-steps" aria-label="Assessment workflow steps">
      {[["review", `Review findings (${reviewed}/${total})`], ["findings", "Retained findings"], ["assessment", "Your assessment"], ["brief", "Intelligence brief"]].map(([id, label], index) =>
        <button key={id} type="button" aria-current={step === id ? "step" : undefined} onClick={() => onStepChange(id)}><span>{index + 1}</span>{label}</button>)}
    </nav>
    {assessmentReady && step !== "brief" && <p className="workflow-next-action" role="status">
      {latest && !latest.stale
        ? <>The senior-leadership brief is ready. <button type="button" onClick={() => onStepChange("brief")}>Open brief</button></>
        : <>Assessment saved. Next: <button type="button" className="primary-action" onClick={() => onStepChange("brief")}>Prepare the intelligence brief</button></>}
    </p>}
    {success && <p role="status" className="brief-success">{success}{step !== "brief" && <button type="button" onClick={() => onStepChange("brief")}>View prepared brief</button>}</p>}
    {(error || loadError) && <p role="alert" className="error">{error || loadError}</p>}
    {(editorialBusy || workflow?.preparing) && <BriefProgress progress={workflow?.brief_progress} />}
    {!error && !editorialBusy && !workflow?.preparing && workflow?.brief_progress?.stage?.startsWith("Failed") && <p role="alert" className="error">Brief preparation failed. Existing versions are retained. Open Intelligence brief to retry.</p>}
    {!workflow && !error && <p role="status">Loading saved review…</p>}
    <div hidden={step !== "review"} id="review-proposals">
    {workflow?.stale_decisions > 0 && <p role="alert">The source draft has changed. {workflow.stale_decisions} previous decisions remain in history; review the new proposals.</p>}

    {workflow && !review && <p>No machine proposals yet. Use Collection → Research and draft assessment to generate source-linked findings, or open Your assessment to write your own.</p>}
    {review && <EvidenceReview key={workflow.review_version} review={review} decisions={decisions} busy={disabled}
      onReview={(fields) => act("review", fields)} />}
      <button className="workflow-next" type="button" onClick={() => onStepChange("findings")}>Continue to retained findings →</button>
    </div>
    <section hidden={step !== "assessment"}>
      {children}
      {assessmentReady && <div className="brief-toolbar">
        <button type="button" onClick={() => setAssessmentLayout(!assessmentLayout)}>Preview assessment PDF</button>
        <FormatDownload label="Download assessment" disabled={disabled} onPick={downloadAssessment} />
        {assessmentLayout && <PDFPreview url={`/api/analyst-workflow/export-assessment?${query}&format=pdf`} title="Saved assessment PDF preview" />}
      </div>}
    </section>
    {workflow && <>
      <section hidden={step !== "findings"} className="brief-callout" id="assemble-assessment">
        <h4>2. Preview retained findings</h4>
        <p>{reviewed < total ? `${total - reviewed} proposals still to review. You can preview progress now or finish reviewing first.` : "Review complete. Preview the retained material, then add it to your assessment."}</p>
        <p>Retained findings and hypothesis changes become a cited starting point. Add your judgement, implications and alternative explanations in the Your assessment step. Rejections and unresolved issues remain visible in the annex.</p>
        <button type="button" disabled={disabled || !review || !reviewed} onClick={() => setPreview(!preview)}>Preview reviewed material</button>
        {preview && <><MarkdownPreview text={workflow.assembly} />
          <button type="button" disabled={disabled} onClick={() => { onAssemble(workflow.assembly); setPreview(false); }}>Merge reviewed material into assessment</button>
          <p>This updates only the marked review section, preserving your writing outside it. Save in Your assessment when ready.</p></>}
      </section>
      <section hidden={step !== "brief"} className="brief-callout" id="prepare-brief" aria-label="Finished intelligence brief">
        {!latest && <>
          {(dirty || report?.empty || !value?.trim())
            ? <p role="status">{dirty ? "Save your assessment first." : "Write and save an assessment first."} <button type="button" onClick={() => onStepChange("assessment")}>Go to assessment</button></p>
            : <>
              <label>Title<input value={title} placeholder={report?.context?.headline || "Public-source intelligence assessment"} onChange={e => setTitle(e.target.value)} /></label>
              <button className="primary-action" type="button" disabled={disabled} onClick={() => act("prepare", { title: title || report?.context?.headline })}>{(editorialBusy || workflow.preparing) ? "Model is drafting the brief…" : "Prepare intelligence brief"}</button>
            </>}
        </>}
        {latest && <>
          <div className="brief-toolbar-head">
            <div>
              <p className="eyebrow">Version {latest.version} · {latest.stale ? "Stale" : latest.signed_off ? `Signed off by ${latest.signed_off.reviewer}` : "Draft"}</p>
              <h4>{latest.title || "Intelligence brief"}</h4>
            </div>
            <div className="brief-toolbar">
              {canSign && <button className="primary-action" type="button" disabled={disabled} aria-expanded={signOffOpen} onClick={() => setSignOffOpen(open => !open)}>Sign off</button>}
              <FormatDownload
                label={latest.signed_off ? "Download" : "Download draft"}
                primary={Boolean(latest.signed_off)}
                disabled={disabled}
                onPick={(format) => downloadBrief(latest.version, format)}
              />
              {signedPrior && <FormatDownload
                label={`Signed v${signedPrior.version}`}
                disabled={disabled}
                onPick={(format) => downloadBrief(signedPrior.version, format)}
              />}
              {briefProduct(latest) && <button type="button" disabled={disabled || latest.stale} onClick={() => { const text = briefProduct(latest); setBriefText(text); writeDraft(briefDraftKey, text, localStorage); }}>Edit brief wording</button>}
            </div>
          </div>
          {canSign && signOffOpen && <div className="brief-signoff" role="region" aria-label="Sign off this draft">
            {reviewed < total && <p>Review each remaining proposal before signing off.</p>}
            {dirty && <p>Save the assessment first.</p>}
            {briefText !== null && <p>Save or discard wording edits first.</p>}
            <label>Reviewer name<input value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
            <label><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} /> I have checked the assessment, source support, alternatives and unresolved caveats.</label>
            <button type="button" disabled={disabled || dirty || briefText !== null || !acknowledged || !reviewer.trim() || reviewed < total} onClick={() => act("sign_off", { version: latest.version, reviewer, acknowledged })}>Sign off this version</button>
          </div>}
          {briefText !== null ? <div>
            <label>Brief wording<textarea aria-label="Brief wording" rows={18} value={briefText} onChange={e => { setBriefText(e.target.value); writeDraft(briefDraftKey, e.target.value, localStorage); }} /></label>
            <div className="brief-toolbar">
              <button type="button" disabled={disabled || dirty || latest.stale || !briefText.trim()} onClick={async () => {
                if (await act("revise_brief", { version: latest.version, text: briefText, title: title || latest.title })) { clearDraft(briefDraftKey, localStorage); setBriefText(null); }
              }}>Save revised brief</button>
              <button type="button" disabled={disabled} onClick={() => { clearDraft(briefDraftKey, localStorage); setBriefText(null); }}>Discard brief edits</button>
            </div>
          </div> : briefProduct(latest) ? <BriefDocument text={briefProduct(latest)} /> : <p role="status">This version has no editorial brief.</p>}
          {latest.annex && <details><summary>Evidence annex</summary>
            <MarkdownPreview text={latest.annex} />
            <button type="button" disabled={disabled} onClick={() => downloadBrief(latest.version, "pdf", true)}>Download annex PDF</button>
          </details>}
          <section aria-label="Version preview">
            <h4>Preview a saved version</h4>
            <label>Brief version<select value={selectedBrief?.version || ''} onChange={e => { setSelectedVersion(Number(e.target.value)); setLayout(false); }}>{workflow.briefs.map(b => <option key={b.version} value={b.version}>Version {b.version} · {b.stale ? 'Stale' : b.signed_off ? 'Signed off' : 'Draft'}</option>)}</select></label>
            <p>Previewing version {selectedBrief.version}. Editing and sign-off above apply to the latest version {latest.version}.</p>
            <button type="button" onClick={() => setLayout(!layout)}>Preview selected PDF layout</button>
            <button type="button" onClick={() => setPreviewAnnex(!previewAnnex)}>{previewAnnex ? 'Hide selected annex' : 'Preview selected annex'}</button>
            <FormatDownload label={`Download selected v${selectedBrief.version}`} onPick={format => downloadBrief(selectedBrief.version, format)} />
            {selectedBrief.version !== latest.version && <><MarkdownPreview text={briefProduct(selectedBrief)} /><button type="button" onClick={() => setCompare(!compare)}>Compare with latest version</button>{compare && <section aria-label="Version comparison"><h4>Selected version {selectedBrief.version}</h4><MarkdownPreview text={briefProduct(selectedBrief)} /><h4>Latest version {latest.version}</h4><MarkdownPreview text={briefProduct(latest)} /></section>}</>}
            {previewAnnex && <><MarkdownPreview text={selectedBrief.annex || 'No annex recorded.'} /><button type="button" onClick={() => downloadBrief(selectedBrief.version, 'pdf', true)}>Download selected annex PDF</button></>}
            {layout && <PDFPreview url={`/api/analyst-workflow/export?${query}&version=${selectedBrief.version}&format=pdf&annex=${previewAnnex}`} title={`Version ${selectedBrief.version} PDF preview${previewAnnex ? ' with annex' : ''}`} />}
          </section>
          {workflow.briefs.length > 1 && <details><summary>All versions ({workflow.briefs.length})</summary>
            {workflow.briefs.slice().reverse().map(brief => <p key={brief.version} className="workflow-version-row">
              Version {brief.version}{brief.version === latest.version ? " · open" : ""} · {brief.stale ? "Stale" : brief.signed_off ? "Signed off" : "Draft"} · {brief.created_at.slice(0, 19)} UTC
              {" "}<FormatDownload label="Download" disabled={disabled} onPick={(format) => downloadBrief(brief.version, format)} />
              {" "}<button type="button" disabled={disabled} onClick={async () => {
                if (!window.confirm(`Remove brief version ${brief.version} from this assessment? Its audit record will be kept.`)) return;
                if (await act("remove_brief", { version: brief.version })) clearDraft(`brief:${scenario}:${noticeId}:${brief.version}`, localStorage);
              }}>Remove version {brief.version}</button>
            </p>)}
          </details>}
          <details>
            <summary>Prepare another draft</summary>
            <label>Title<input value={title} placeholder={latest.title || report?.context?.headline || "Public-source intelligence assessment"} onChange={e => setTitle(e.target.value)} /></label>
            <button type="button" disabled={disabled || dirty || report?.empty || !value?.trim()} onClick={() => act("prepare", { title: title || latest.title || report?.context?.headline })}>{(editorialBusy || workflow.preparing) ? "Model is drafting the brief…" : "Prepare new brief version"}</button>
          </details>
        </>}
      </section>
      <details className="workflow-maintenance"><summary>Assessment maintenance</summary>
        <p>Clear this notice’s saved assessment, review decisions and active briefs, plus drafts in this browser. Previous saved work is archived. Evidence, research and machine proposals stay available.</p>
        <button type="button" disabled={disabled} onClick={() => {
          if (window.confirm("Reset this assessment, review decisions and briefs? Unsaved edits in this browser will be discarded. Saved work is archived; research and source proposals are retained.")) act("reset", { acknowledged: true });
        }}>Reset assessment</button>
      </details>
      <FollowupCollection scenario={scenario} noticeId={noticeId} reviewVersion={workflow.review_version} onComplete={async () => { const r = await fetch(`/api/analyst-workflow?${query}`); if (r.ok) { setWorkflow(await r.json()); onStepChange("review"); } else setError("Could not reload findings. Reopen this notice to retry."); }} />
    <ReviewTimeline events={workflow.events} reviewVersion={workflow.review_version} />
    </>}
  </section>;
}
