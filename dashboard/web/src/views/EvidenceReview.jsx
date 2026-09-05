import { useEffect, useState } from "react";

const text = (value) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
const rows = (value) => Array.isArray(value) ? value : [];
const link = (url) => typeof url === "string" && /^https?:\/\//i.test(url) ? url : null;

function ProposalCard({ label, decision, children }) {
  const [open, setOpen] = useState(!decision);
  useEffect(() => { setOpen(!decision); }, [decision]);
  return <details className="brief-callout proposal-card" open={open} onToggle={e => setOpen(e.currentTarget.open)}>
    <summary><strong>{decision ? ({ accepted: "Accepted", rejected: "Rejected", edited: "Edited", unresolved: "Unresolved" }[decision.status]) : "To review"}</strong> · {label}{decision && <span> · Saved · Open to revisit</span>}</summary>
    {children}
  </details>;
}

function ReviewControls({ id, proposal, decision, busy, onReview }) {
  const [reason, setReason] = useState(decision?.reason || "");
  const [edited, setEdited] = useState(decision?.text || proposal.statement || proposal.rationale || "");
  const [showEdit, setShowEdit] = useState(false);
  const submit = status => onReview({ proposal_id: id, status, reason, text: edited });
  return <div className="review-controls">
    <p role="status">{decision ? `${decision.status === "accepted" ? "Retained for assessment" : decision.status} · Saved` : "Not reviewed"}</p>
    <label>Review reason<input value={reason} onChange={e => setReason(e.target.value)} placeholder="Required for edits, rejection or unresolved" /></label>
    <div className="notice-actions">
      <button type="button" disabled={busy} onClick={() => submit("accepted")}>Accept finding</button>
      <button type="button" disabled={busy || !reason.trim()} onClick={() => submit("rejected")}>Reject finding</button>
      <button type="button" disabled={busy} onClick={() => setShowEdit(!showEdit)}>Edit proposal</button>
      <button type="button" disabled={busy || !reason.trim()} onClick={() => submit("unresolved")}>Leave unresolved</button>
    </div>
    {showEdit && <><label>Revised proposal<textarea rows={4} value={edited} onChange={e => setEdited(e.target.value)} /></label>
      <button type="button" disabled={busy || !reason.trim() || !edited.trim()} onClick={() => submit("edited")}>Save edited finding</button></>}
    {decision?.text && <p>Retained wording: {decision.text}</p>}
  </div>;
}

export default function EvidenceReview({ review, decisions = {}, busy = false, onReview }) {
  const evidence = new Map(rows(review.evidence).map((item) => [item.id, item]));
  function source(id) {
    const item = evidence.get(id);
    if (!item) return <p key={text(id)}>Unresolved reference: {text(id)}</p>;
    const url = link(item.data?.archive_url || item.data?.url);
    return <details key={id}>
      <summary>{id} · {item.kind} · {item.verification}</summary>
      <p>{item.source_ref}</p>
      <p>Available: {item.available_at} · Retrieved: {item.retrieved_at || "Not recorded"}</p>
      {url && <a href={url} target="_blank" rel="noreferrer">Open source version</a>}
      <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{text(item.data)}</pre>
    </details>;
  }
  return <section className="brief-callout" aria-label="Evidence and assessment review">
    <h3>1. Review findings and proposed changes</h3>
    <p>{review.notice}</p>
    <p>{rows(review.evidence).length} included · {rows(review.excluded).length} excluded · {rows(review.omitted).length} omitted by budget</p>
    <p>Proposed decision: <strong>{text(review.proposed_decision)}</strong> · {review.status}</p>
    <p>Decisions are saved against this evidence version. Preview and merge retained material into your assessment below; no report is sent by reviewing a proposal.</p>
    {!!rows(review.issues).length && <details open><summary>Needs your attention</summary>
      <ul>{review.issues.map((issue, i) => <li key={i}>{text(issue)}</li>)}</ul>
    </details>}
    <details><summary>Original cue (unchanged)</summary><pre style={{ whiteSpace: "pre-wrap" }}>{text(review.initial_cue)}</pre></details>
    {review.research && <section aria-label="Research outcome">
      <h4>Research outcome</h4>
      <p><strong>{review.research.stop_reason || (review.research.limit_reached ? `Stopped at the application ${review.research.limit_reached} limit.` : review.research.blocked || "Stopping reason was not recorded in this older run.")}</strong></p>
      <p>{review.research.usage?.search_requests ?? "Unknown"} recorded queries · {review.research.usage?.document_attempts ?? "Unknown"} recorded document attempts · {review.research.admitted_documents ?? "Not recorded"} usable documents · {review.research.usage?.elapsed_s ?? "Unknown"}s accumulated research time.</p>
      <p>{Object.entries(review.research.requests || {}).filter(([key, value]) => key.startsWith("document-") && value.status === "failed").length} failed document retrievals. Tavily credit balance was not checked.</p>
      {!!review.research.run_usage && <p>This run: {review.research.run_usage.search_requests} new search requests, {review.research.run_usage.search_cache_hits} cached searches and {review.research.run_usage.document_attempts} new document attempts.</p>}
      {!!rows(review.research.collection_outcomes).filter(row => row.status === "not_attempted").length && <p><strong>{rows(review.research.collection_outcomes).filter(row => row.status === "not_attempted").length} collection questions were not attempted. See the reasons below.</strong></p>}
      {review.research.limits && <p>Selected limits: {review.research.limits.queries} queries, {review.research.limits.documents} document attempts per run, {review.research.limits.seconds}s per run.</p>}
      <details><summary>Source failures and collection gaps</summary><ul>{Object.entries(review.research.requests || {}).filter(([,value]) => value.reason).map(([key,value]) => <li key={key}>{key}: {value.reason}</li>)}</ul>
        {rows(review.research.collection_outcomes).map((row, i) => <p key={i}>{row.question}: {row.status} — {row.reason}</p>)}
      </details>
      <details><summary>Full research record</summary><pre style={{ whiteSpace: "pre-wrap" }}>{text(review.research)}</pre></details>
    </section>}
    <h4>Findings and source passages</h4>
    {!rows(review.claims).length && <p>No grounded findings supplied. Treat draft prose as unverified.</p>}
    {rows(review.claims).map((claim) => <ProposalCard key={claim.claim_id} label={text(decisions[claim.claim_id]?.text || claim.statement)} decision={decisions[claim.claim_id]}>
      <p>{text(claim.statement)} {claim.inference === true && <em> · Model inference</em>}</p>
      <p>{claim.reference_check}</p>
      {rows(claim.evidence_ids).map(source)}
      {claim.quotes && <details><summary>Claimed supporting passages</summary><pre style={{ whiteSpace: "pre-wrap" }}>{text(claim.quotes)}</pre></details>}
      <ReviewControls id={claim.claim_id} proposal={claim} decision={decisions[claim.claim_id]} busy={busy} onReview={onReview} />
    </ProposalCard>)}
    <h4>What changes the explanation?</h4>
    {rows(review.hypothesis_updates).map((item) => <ProposalCard key={item.hypothesis} label={`${item.hypothesis} · ${text(item.change)}`} decision={decisions[`hypothesis:${item.hypothesis}`]}>
      <p>{text(item.rationale)}</p>
      <p>Confidence: {text(item.confidence || "Unresolved")}</p>
      <h5>Supporting evidence</h5>{rows(item.supporting_evidence).map(source)}
      <h5>Contradicting evidence</h5>{rows(item.contradicting_evidence).map(source)}
      <p>Unknowns: {text(item.unknowns || [])}</p>
      <p>What would discriminate: {text(item.discriminators || [])}</p>
      <ReviewControls id={`hypothesis:${item.hypothesis}`} proposal={item} decision={decisions[`hypothesis:${item.hypothesis}`]} busy={busy} onReview={onReview} />
    </ProposalCard>)}
    <h4>Proposed next action: {text(review.proposed_decision)}</h4>
    <ProposalCard label={`Next action: ${text(review.proposed_decision)}`} decision={decisions.decision}>
    <ReviewControls id="decision" proposal={{ statement: review.proposed_decision }} decision={decisions.decision} busy={busy} onReview={onReview} />
    </ProposalCard>
    <p>A collection decision records your recommendation. Run the public-source jobs from the Collection tab to gather more evidence, then regenerate and review the assessment.</p>
    <details><summary>Evidence catalogue</summary>{rows(review.evidence).map((item) => source(item.id))}</details>
    <details><summary>Excluded and omitted inputs</summary><pre style={{ whiteSpace: "pre-wrap" }}>{text([...rows(review.excluded), ...rows(review.omitted)])}</pre></details>
    <details><summary>Provenance cautions</summary><ul>{rows(review.cautions).map((item, i) => <li key={i}>{text(item)}</li>)}</ul></details>
  </section>;
}
