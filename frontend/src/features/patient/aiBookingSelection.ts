import type { AiAssessment } from "../../core/types";

export function canBookWithAi(assessment: AiAssessment | null | undefined): assessment is AiAssessment & { latestForBooking: true; appointmentId?: null } {
  return Boolean(assessment?.latestForBooking === true && assessment.appointmentId == null);
}

export function bookingAiAssessment(list: AiAssessment[], rawDraft: string | null): AiAssessment | undefined {
  const latest = list.find(item => canBookWithAi(item));
  if (!latest?.sharedWithDoctor) return undefined;
  if (rawDraft !== null) {
    try {
      const draft = JSON.parse(rawDraft) as { assessmentId?: unknown } | null;
      if (draft?.assessmentId !== latest.id) return undefined;
    } catch { return undefined; }
  }
  return latest;
}

export function clearAiBookingDraft(assessmentId: string) {
  const draft = sessionStorage.getItem("dermai-ai-booking");
  if (!draft) return;
  try {
    if (JSON.parse(draft)?.assessmentId !== assessmentId) return;
  } catch { /* Remove an unusable draft rather than choosing a different image. */ }
  sessionStorage.removeItem("dermai-ai-booking");
}
