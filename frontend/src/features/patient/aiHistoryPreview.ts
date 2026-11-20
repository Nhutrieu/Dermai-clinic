import type { AiAssessment } from "../../core/types";

const previewKey = (identity: string) => `dermai-ai-history-preview:${identity}`;

export function readAiHistoryPreview(identity: string): string | undefined {
  try { return localStorage.getItem(previewKey(identity)) || undefined; }
  catch { return undefined; }
}

export function rememberAiHistoryPreview(identity: string, assessmentId?: string) {
  try {
    if (assessmentId) localStorage.setItem(previewKey(identity), assessmentId);
    else localStorage.removeItem(previewKey(identity));
  } catch { /* Viewing remains available when browser storage is disabled. */ }
}

export function recentAiAssessment(list: AiAssessment[], previewId?: string): AiAssessment | undefined {
  // A new analysis takes priority; an older result is shown only when explicitly selected for viewing.
  return list.find(item => item.latestForBooking === true)
    || (previewId ? list.find(item => item.id === previewId) : undefined);
}
