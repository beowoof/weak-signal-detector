import { humanize } from '../lib/workspace.js';
export default function ReviewTimeline({ events, reviewVersion }) {
  return <details><summary>Review history ({events.length})</summary>
    {!events.length ? <p>No review actions recorded yet.</p> : <ol>{[...events].reverse().map((event, i) => <li key={`${event.at}:${i}`}>
      <strong>{humanize(event.action)}{event.decision ? ` · ${humanize(event.decision.status)}` : ''}</strong>
      <p>{event.at}{event.reviewer ? ` · ${event.reviewer}` : ''}{event.version ? ` · Brief version ${event.version}` : ''}</p>
      {event.decision && <p>{event.decision.review_version === reviewVersion ? 'Current review version' : 'Earlier review version — retained for audit'}</p>}
      {event.proposal && <p>{event.proposal.statement || event.proposal.rationale || event.proposal_id}</p>}
      {event.decision?.reason && <p>Reason: {event.decision.reason}</p>}
      {event.decision?.text && <p>Retained wording: {event.decision.text}</p>}
      <details><summary>Original event and identifiers</summary><pre className="workflow-prose">{JSON.stringify(event,null,2)}</pre></details>
    </li>)}</ol>}
  </details>;
}
