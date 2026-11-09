import { describe, expect, it } from "vitest";
import type { AiAssessment } from "../../core/types";
import { aiScoreExplanation, isAiFoldVote, patientAiDoctorReviewState } from "./patientAiPresentation";

function assessment(overrides: Partial<AiAssessment> = {}): AiAssessment {
  return {
    id: "assessment-1",
    patientId: "patient-1",
    predictedLabel: "Acne",
    confidence: 0.72,
    top3: [],
    uncertain: false,
    modelVersion: "efficientnet-test",
    sharedWithDoctor: false,
    imageAvailable: true,
    createdAt: "2026-08-01T03:00:00Z",
    ...overrides,
  };
}

describe("patient AI result presentation", () => {
  it("explains vote shares without presenting a disease probability", () => {
    expect(isAiFoldVote("dermai-eight-esg-v1-20261108")).toBe(true);
    expect(isAiFoldVote("efficientnet-test")).toBe(false);
    expect(aiScoreExplanation("dermai-eight-esg-v1-20261108")).toContain("mức đồng thuận");
    expect(aiScoreExplanation("dermai-eight-esg-v1-20261108")).toContain("không phải xác suất mắc bệnh");
  });
  it("does not claim a doctor reviewed an unshared result", () => {
    expect(patientAiDoctorReviewState(assessment()).label).toBe("Chưa gửi bác sĩ xem xét");
  });

  it("describes an appointment-linked result without faking a viewed state", () => {
    const state = patientAiDoctorReviewState(assessment({ sharedWithDoctor: true, appointmentId: "appointment-1" }));
    expect(state.label).toBe("Đã gửi cùng lịch hẹn");
    expect(state.detail).toContain("chưa ghi nhận trạng thái bác sĩ đã mở xem");
  });
});
