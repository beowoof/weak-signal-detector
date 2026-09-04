import { draftKey } from "./workspace.js";

// Keep a session copy too: quota errors must not lose a draft on notice navigation.
const sessionDrafts = new Map();
export function readDraft(noticeId, storage) {
  if (sessionDrafts.has(noticeId)) return sessionDrafts.get(noticeId);
  try { return storage.getItem(draftKey(noticeId)); } catch { return null; }
}
export function writeDraft(noticeId, text, storage) {
  sessionDrafts.set(noticeId, text);
  try { storage.setItem(draftKey(noticeId), text); return true; } catch { return false; }
}
export function clearDraft(noticeId, storage) {
  sessionDrafts.set(noticeId, null);
  try { storage.removeItem(draftKey(noticeId)); } catch { /* Session copy is still cleared. */ }
}
