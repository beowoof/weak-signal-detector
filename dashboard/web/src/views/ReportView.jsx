import { useEffect, useRef, useState } from "react";

export function NotesRead({ notes, updatedAt, onEdit }) {
  if (!notes) return null;
  return (
    <section className="brief-card report-card report-card-top">
      <h3>Notes</h3>
      {updatedAt ? (
        <p className="notice-timing">
          Saved {String(updatedAt).replace("T", " ").slice(0, 19)}Z
        </p>
      ) : null}
      <pre className="report-read">{notes}</pre>
      {onEdit ? (
        <p className="notice-actions">
          <button type="button" onClick={onEdit}>
            Edit notes
          </button>
        </p>
      ) : null}
    </section>
  );
}

export default function ReportView({ report, busy, onSave, onClose }) {
  const [notes, setNotes] = useState(report?.notes || "");
  const box = useRef(null);

  useEffect(() => {
    setNotes(report?.notes || "");
  }, [report?.report_id, report?.updated_at, report?.notes]);

  useEffect(() => {
    box.current?.focus();
  }, []);

  if (!report) {
    return (
      <section className="brief-card report-card report-card-top">
        <h3>Notes</h3>
        <p className="notice-timing">No notice selected.</p>
      </section>
    );
  }

  return (
    <section className="brief-card report-card report-card-top">
      <h3>Notes</h3>
      <p className="notice-timing">
        Template is pre-filled from the packet. Edit anything. Skip what you do not need.
      </p>
      <textarea
        ref={box}
        className="report-single"
        value={notes}
        rows={22}
        onChange={(event) => setNotes(event.target.value)}
      />
      <p className="notice-actions">
        <button type="button" disabled={busy} onClick={() => onSave?.(notes)}>
          {busy ? "Saving…" : "Save notes"}
        </button>
        {onClose ? (
          <button type="button" onClick={onClose}>
            Close
          </button>
        ) : null}
        {report.updated_at && !report.empty ? (
          <span className="notice-timing">
            Saved {String(report.updated_at).replace("T", " ").slice(0, 19)}Z
          </span>
        ) : null}
      </p>
    </section>
  );
}
