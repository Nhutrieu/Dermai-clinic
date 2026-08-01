import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { AiAssessment, AiPrediction } from "../../core/types";
import PatientAiResult from "./PatientAiResult";

const assessment: AiAssessment = {
  id: "assessment-1",
  patientId: "patient-1",
  predictedLabel: "Acne",
  confidence: 0.72,
  top3: [{ label: "Acne", probability: 0.72 }],
  uncertain: false,
  modelVersion: "efficientnet-test",
  sharedWithDoctor: false,
  imageAvailable: true,
  createdAt: "2026-08-01T03:00:00Z",
};

const prediction: AiPrediction = {
  disease: "Acne",
  confidence: 0.72,
  top3: [
    { label: "Acne", probability: 0.72 },
    { label: "Eczema", probability: 0.18 },
    { label: "Warts", probability: 0.1 },
  ],
  gradcam_image: "data:image/png;base64,example",
  model_version: "efficientnet-test",
  uncertain: false,
  disclaimer: "Kết quả chỉ nhằm hỗ trợ, không thay thế chẩn đoán của bác sĩ.",
};

function renderResult(nextPrediction = prediction, nextAssessment = assessment) {
  return renderToStaticMarkup(
    <PatientAiResult
      prediction={nextPrediction}
      assessment={nextAssessment}
      originalImageUrl="blob:patient-image"
      onBook={vi.fn()}
      onViewAppointment={vi.fn()}
    />,
  );
}

describe("patient AI result", () => {
  it("uses patient-safe wording instead of presenting a diagnosis", () => {
    const html = renderResult();
    expect(html).toContain("có thể liên quan đến");
    expect(html).not.toContain("Bạn mắc");
    expect(html).toContain("không thay thế chẩn đoán của bác sĩ da liễu");
  });

  it("keeps the text result visible when Grad-CAM is missing", () => {
    const html = renderResult({
      ...prediction,
      gradcam_image: "",
      guidance: {
        title: "Thông tin từ tài liệu y khoa",
        answer: "Tài liệu hiện có chưa cung cấp đủ thông tin đáng tin cậy.",
        citations: [],
        has_evidence: false,
      },
    });
    expect(html).toContain("Grad-CAM tạm thời chưa có");
    expect(html).toContain("Mụn trứng cá");
  });

  it("offers the appointment view when the result is linked to a booking", () => {
    const html = renderResult(prediction, {
      ...assessment,
      sharedWithDoctor: true,
      appointmentId: "appointment-1",
    });
    expect(html).toContain("Đã gửi cùng lịch hẹn");
    expect(html).toContain("Xem lịch hẹn");
  });
});
