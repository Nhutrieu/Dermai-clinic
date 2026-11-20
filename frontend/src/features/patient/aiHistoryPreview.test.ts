import { describe, expect, it } from "vitest";
import type { AiAssessment } from "../../core/types";
import { recentAiAssessment } from "./aiHistoryPreview";
import { canBookWithAi } from "./aiBookingSelection";

const previous: AiAssessment = { id: "previous", patientId: "patient", predictedLabel: "Acne", confidence: .8, top3: [], uncertain: false, modelVersion: "test", sharedWithDoctor: true, imageAvailable: true, createdAt: "2026-11-18T00:00:00Z", latestForBooking: false };

describe("remembering an older AI result for viewing", () => {
  it("restores the same selected result even if history order changes", () => {
    const older = { ...previous, id: "older" };
    expect(recentAiAssessment([older, previous], "previous")).toBe(previous);
    expect(canBookWithAi(recentAiAssessment([older, previous], "previous"))).toBe(false);
  });
  it("does not automatically show another older result if the selected one was deleted", () => {
    expect(recentAiAssessment([previous], "deleted")).toBeUndefined();
    expect(recentAiAssessment([previous])).toBeUndefined();
  });
  it("shows a newly analyzed result instead of staying on an old preview", () => {
    const newest = { ...previous, id: "newest", latestForBooking: true };
    expect(recentAiAssessment([previous, newest], "previous")).toBe(newest);
  });
});
