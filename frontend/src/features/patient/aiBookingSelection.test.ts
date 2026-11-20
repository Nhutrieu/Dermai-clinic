import { describe, expect, it } from "vitest";
import type { AiAssessment } from "../../core/types";
import { bookingAiAssessment, canBookWithAi } from "./aiBookingSelection";

const older: AiAssessment = { id: "old", patientId: "patient", predictedLabel: "Acne", confidence: .8, top3: [], uncertain: false, modelVersion: "test", sharedWithDoctor: true, imageAvailable: true, createdAt: "2026-11-01T00:00:00Z", latestForBooking: false };
const newest: AiAssessment = { ...older, id: "new", createdAt: "2026-11-19T00:00:00Z", latestForBooking: true };

describe("AI result selection for booking", () => {
  it("uses only the server-marked newest result, regardless of list order", () => {
    expect(bookingAiAssessment([older, newest], null)?.id).toBe("new");
    expect(canBookWithAi(older)).toBe(false);
  });
  it("does not attach older shared images after deleting the newest result", () => {
    expect(bookingAiAssessment([older], null)).toBeUndefined();
    expect(bookingAiAssessment([older], JSON.stringify({ assessmentId: "new" }))).toBeUndefined();
  });
  it("never silently replaces a deleted or stale draft with another image", () => {
    expect(bookingAiAssessment([older, newest], JSON.stringify({ assessmentId: "deleted" }))).toBeUndefined();
    expect(bookingAiAssessment([older, newest], JSON.stringify({ assessmentId: "old" }))).toBeUndefined();
    expect(bookingAiAssessment([newest], "invalid JSON")).toBeUndefined();
  });
  it("attaches the explicitly selected newest result", () => {
    expect(bookingAiAssessment([older, newest], JSON.stringify({ assessmentId: "new" }))).toBe(newest);
  });
  it("respects disabled sharing and does not reuse an already linked result", () => {
    expect(bookingAiAssessment([{ ...newest, sharedWithDoctor: false }], null)).toBeUndefined();
    expect(bookingAiAssessment([{ ...newest, appointmentId: "appointment" }], null)).toBeUndefined();
  });
  it("does not infer eligibility from array position when the server flag is missing", () => {
    expect(bookingAiAssessment([{ ...older, latestForBooking: undefined }], null)).toBeUndefined();
  });
});
