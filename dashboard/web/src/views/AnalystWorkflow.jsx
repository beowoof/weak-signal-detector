import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { readDraft, writeDraft, clearDraft } from "../lib/drafts.js";
import EvidenceReview from "./EvidenceReview.jsx";

export default function AnalystWorkflow({ scenario, noticeId, report, evidenceReview, dirty, busy, value, onAssemble, onReset }) {
  const [briefHost, setBriefHost] = useState(null);
  useEffect(() => { setBriefHost(document.getElementById(`brief-destination-${noticeId}`)); }, [noticeId]);
  const [workflow, setWorkflow] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [briefText, setBriefText] = useState(null);
  const [editorialBusy, setEditorialBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const query = new URLSearchParams({ scenario, notice_id: noticeId }).toString();
  useEffect(() => {
    let cancelled = false;
    setError("");
    fetch(`/api/analyst-workflow?${query}`).then(async r => {
      if (!r.ok) throw new Error("Could not load saved review decisions. Reload to retry.");
      const data = await r.json();
      if (!cancelled) { setWorkflow(data); setAcknowledged(false); }
    }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [query, evidenceReview, report?.updated_at]);
  useEffect(() => {
    if (!workflow?.preparing) return;
    const timer = setInterval(() => {
      fetch(`/api/analyst-workflow?${query}`).then(r => { if (!r.ok) throw new Error("Unable to refresh briefing status"); return r.json(); })
        .then(setWorkflow).catch(e => setError(e.message));
    }, 3000);
    return () => clearInterval(timer);
  }, [query, workflow?.preparing]);
  async function act(action, fields = {}) {
    if (!workflow || pending) return;
    setPending(true); setEditorialBusy(action === "prepare"); setError("");
    try {
      const response = await fetch("/api/analyst-workflow", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, notice_id: noticeId, revision: workflow.revision,
          review_version: workflow.review_version, action, ...fields }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Action was not saved");
      setWorkflow(data); setAcknowledged(false);
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
  const briefDraftKey = `brief:${scenario}:${noticeId}:${latest?.version}`;
  useEffect(() => { setBriefText(latest ? readDraft(briefDraftKey, localStorage) : null); }, [briefDraftKey]);
  useEffect(() => {
    if (briefText === null) return;
    const warn = event => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [briefText]);
  const disabled = pending || busy || workflow?.preparing || !workflow;
  return <section className="workflow-panel" aria-label="Assessment to intelligence brief">
    <div className="section-heading"><div><p className="eyebrow">Review → assessment → brief</p>
      <h3>{latest && !latest.stale ? (latest.signed_off ? "Brief signed off" : "Brief ready for review") : "Develop your assessment"}</h3></div>
      <span role="status">{reviewed} / {total} proposals reviewed</span></div>
    <nav className="workflow-steps" aria-label="Assessment workflow steps">
      <a href="#review-proposals">1. Review ({reviewed}/{total})</a>
      <a href="#assemble-assessment">2. Preview findings</a>
      <a href="#working-assessment">3. Edit & save assessment</a>
      <a href="#prepare-brief">4. Name & prepare brief</a>
    </nav>
    <div id="review-proposals" />
    {workflow?.stale_decisions > 0 && <p role="alert">The source draft has changed. {workflow.stale_decisions} previous decisions remain in history; review the new proposals.</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {!workflow && !error && <p role="status">Loading saved review…</p>}
    {workflow && !review && <p>No machine proposals yet. Use <strong>Machine draft</strong> to investigate and generate source-linked findings, or write your own assessment below.</p>}
    {review && <EvidenceReview key={workflow.review_version} review={review} decisions={decisions} busy={disabled}
      onReview={(fields) => act("review", fields)} />}
    {workflow && <>
      <a className="workflow-next" href="#assemble-assessment">Continue to step 2: preview retained findings →</a>
      <section className="brief-callout" id="assemble-assessment">
        <h4>2. Preview retained findings</h4>
        <p>{reviewed < total ? `${total - reviewed} proposals still to review. You can preview progress now or finish reviewing first.` : "Review complete. Preview the retained material, then add it to your assessment."}</p>
        <p>Retained findings and hypothesis changes become a cited starting point. Add your judgement, implications and alternative explanations in the assessment editor below. Rejections and unresolved issues remain visible in the annex.</p>
        <button type="button" disabled={disabled || !review || !reviewed} onClick={() => setPreview(!preview)}>Preview reviewed material</button>
        {preview && <><pre className="workflow-prose">{workflow.assembly}</pre>
          <button type="button" disabled={disabled} onClick={() => { onAssemble(workflow.assembly); setPreview(false); }}>Merge reviewed material into assessment</button>
          <p>This updates only the marked review section, preserving your writing outside it. Save the assessment below when ready.</p></>}
      </section>
      {briefHost && createPortal(<section className="brief-callout" id="prepare-brief" aria-label="Finished intelligence brief">
        <h4>4. Name and prepare the intelligence brief</h4>
        <p>First edit and save your assessment in step 3. Then choose a title here, prepare a version, preview it and sign off.</p>
        <p>The model edits your saved assessment and retained findings into a concise senior-leadership brief: key judgements, significance, alternatives and outlook. It makes no new searches. Review and amend its wording before sign-off; the evidence annex is preserved.</p>
        <label>Brief title<input value={title} placeholder={report?.context?.headline || "Public-source intelligence assessment"} onChange={e => setTitle(e.target.value)} /></label>
        {dirty && <p role="status">Save your assessment before preparing or signing off a brief.</p>}
        <button type="button" disabled={disabled || dirty || report?.empty || !value?.trim()} onClick={() => act("prepare", { title: title || report?.context?.headline })}>{(editorialBusy || workflow.preparing) ? "Model is drafting the brief…" : "Prepare new brief version"}</button>
        {(editorialBusy || workflow.preparing) && <p role="status">Editorial synthesis is running. This may take several minutes. Your assessment and existing briefs are retained; do not start another generation.</p>}
        {latest && <>
          <p><strong>Version {latest.version}</strong> · {latest.stale ? "Stale — prepare a new version" : latest.signed_off ? `Signed off by ${latest.signed_off.reviewer}` : "Awaiting sign-off"} · Not distributed</p>
          {latest.editorial && <p>Editorial model: {latest.editorial.model} · Input references checked; factual support and faithfulness require your review.</p>}
          {latest.body && <>
            <button type="button" disabled={disabled || latest.stale} onClick={() => { setBriefText(latest.body); writeDraft(briefDraftKey, latest.body, localStorage); }}>Edit brief wording</button>
            {briefText !== null && <div>
              <label>Brief wording<textarea aria-label="Brief wording" rows={18} value={briefText} onChange={e => { setBriefText(e.target.value); writeDraft(briefDraftKey, e.target.value, localStorage); }} /></label>
              <p>Edits are retained in this browser. Saving creates a new unsigned version and preserves the evidence annex.</p>
              <button type="button" disabled={disabled || dirty || latest.stale || !briefText.trim()} onClick={async () => {
                if (await act("revise_brief", { version: latest.version, text: briefText, title: title || latest.title })) { clearDraft(briefDraftKey, localStorage); setBriefText(null); }
              }}>Save revised brief</button>
              <button type="button" disabled={disabled} onClick={() => { clearDraft(briefDraftKey, localStorage); setBriefText(null); }}>Discard brief edits</button>
            </div>}
          </>}
          <details open><summary>Preview brief and evidence annex</summary><pre className="workflow-prose">{latest.markdown}</pre></details>
          {!latest.signed_off && !latest.stale && <div className="brief-signoff">
            <label>Reviewer name<input value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
            <label><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} /> I have checked the assessment, source support, alternatives and unresolved caveats.</label>
            {reviewed < total && <p>Review each proposal, including any you leave explicitly unresolved, before signing off.</p>}
            <button type="button" disabled={disabled || dirty || briefText !== null || !acknowledged || !reviewer.trim() || reviewed < total} onClick={() => act("sign_off", { version: latest.version, reviewer, acknowledged })}>Sign off this version</button>
          </div>}
        </>}
        {!!workflow.briefs.length && <details><summary>Versions and exports ({workflow.briefs.length})</summary>
          {workflow.briefs.slice().reverse().map(brief => <p key={brief.version}>Version {brief.version} · {brief.stale ? "Stale" : brief.signed_off ? "Signed off" : "Draft"} · {brief.created_at.slice(0, 19)} UTC · {" "}
            <a href={`/api/analyst-workflow/export?${query}&version=${brief.version}&format=md`}>Download Markdown</a>{" · "}
            <a href={`/api/analyst-workflow/export?${query}&version=${brief.version}&format=html`}>Download printable HTML</a>{" · "}
            <button type="button" disabled={disabled} onClick={async () => {
              if (!window.confirm(`Remove brief version ${brief.version} from this assessment? Its audit record will be kept.`)) return;
              if (await act("remove_brief", { version: brief.version })) clearDraft(`brief:${scenario}:${noticeId}:${brief.version}`, localStorage);
            }}>Remove version {brief.version}</button></p>)}
        </details>}
      </section>, briefHost)}
      <details className="brief-callout"><summary>Reset assessment for a fresh test</summary>
        <p>Clear this notice’s saved assessment, review decisions and active briefs, plus drafts in this browser. Previous saved work is archived. Evidence, research and machine proposals stay available.</p>
        <button type="button" disabled={disabled} onClick={() => {
          if (window.confirm("Reset this assessment, review decisions and briefs? Unsaved edits in this browser will be discarded. Saved work is archived; research and source proposals are retained.")) act("reset", { acknowledged: true });
        }}>Reset assessment</button>
      </details>
      <details><summary>Review history ({workflow.events.length})</summary><pre className="workflow-prose">{JSON.stringify(workflow.events, null, 2)}</pre></details>
    </>}
  </section>;
}
