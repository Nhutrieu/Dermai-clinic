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
