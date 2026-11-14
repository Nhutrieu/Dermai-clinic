import type { AiAssessment } from "../../core/types";

const PATIENT_AI_LABELS: Record<string, string> = {
  Acne: "Mụn trứng cá",
  Candidiasis: "Nhiễm nấm Candida ở da",
  Eczema: "Chàm / viêm da dạng chàm",
  Lupus: "Tổn thương da gợi ý lupus",
  Psoriasis: "Vảy nến",
  SkinCancer: "Tổn thương nghi ngờ ác tính",
  Tinea: "Nấm da",
  Warts: "Mụn cóc",
};

export function patientAiLabel(value: string) {
  return PATIENT_AI_LABELS[value] || value;
}

export function formatAiPercentage(value: number) {
  return `${(value * 100).toFixed(1).replace(".", ",")}%`;
}

export function isAiFoldVote(modelVersion: string) {
  return modelVersion.startsWith("dermai-eight-esg-v1-");
}

export function isAiResearchEnsemble(modelVersion: string) {
  return isAiFoldVote(modelVersion) || modelVersion.startsWith("dermai-eight-single-fold");
}

export function aiScoreExplanation(modelVersion: string) {
  return isAiFoldVote(modelVersion)
    ? "Các điểm thể hiện mức đồng thuận giữa năm bộ mô hình, không phải xác suất mắc bệnh. Nhãn đầu tiên có thể được ưu tiên theo quy tắc bảo vệ nhóm nghi ngờ ác tính."
    : "Các điểm thể hiện mức đánh giá của mô hình, không phải xác suất mắc bệnh. Nhãn đầu tiên được chọn theo quy tắc của mô hình nên có thể không có điểm cao nhất.";
}

export function patientAiDoctorReviewState(assessment: AiAssessment) {
  if (assessment.sharedWithDoctor && assessment.appointmentId) {
    return {
      tone: "sent" as const,
      label: "Đã gửi cùng lịch hẹn",
      detail: "Bác sĩ phụ trách có thể xem ảnh và kết quả này trong lịch hẹn. Hệ thống chưa ghi nhận trạng thái bác sĩ đã mở xem.",
    };
  }
  if (assessment.sharedWithDoctor) {
    return {
      tone: "ready" as const,
      label: "Sẵn sàng chia sẻ khi đặt lịch",
      detail: "Kết quả chưa được gắn với bác sĩ cụ thể và chưa có xác nhận chuyên môn.",
    };
  }
  return {
    tone: "not-shared" as const,
    label: "Chưa gửi bác sĩ xem xét",
    detail: "Bạn có thể đặt lịch để chia sẻ riêng ảnh và kết quả với bác sĩ phụ trách.",
  };
}
