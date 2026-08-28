import {
  BookOpenText,
  CalendarCheck2,
  CalendarDays,
  Info,
  Stethoscope,
} from "lucide-react";
import type { AiAssessment, AiDiseaseGuidance, AiPrediction } from "../../core/types";
import {
  formatAiPercentage,
  patientAiDoctorReviewState,
  patientAiLabel,
} from "./patientAiPresentation";

type PatientAiResultProps = {
  prediction: AiPrediction;
  assessment: AiAssessment;
  onBook: () => void;
  onViewAppointment: () => void;
};

function formatAnalysisDate(value: string) {
  return new Date(value).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function DoctorReviewStatus({ assessment }: { assessment: AiAssessment }) {
  // The current API records sharing and appointment linkage, but not whether a doctor opened the result.
  const state = patientAiDoctorReviewState(assessment);
  return (
    <div className={`patient-ai-review-status is-${state.tone}`} role="status" aria-live="polite">
      <Stethoscope aria-hidden="true" />
      <div>
        <strong>{state.label}</strong>
        <p>{state.detail}</p>
      </div>
    </div>
  );
}

function MedicalAiNotice() {
  return (
    <div className="patient-ai-result-notice" role="note" aria-label="Lưu ý y tế về kết quả AI">
      <Info aria-hidden="true" />
      <p>Kết quả này được tạo bởi hệ thống hỗ trợ phân tích hình ảnh và không thay thế chẩn đoán của bác sĩ da liễu.</p>
    </div>
  );
}

function AiObservationSummary({ prediction }: { prediction: AiPrediction }) {
  return (
    <section className="patient-ai-observation" aria-labelledby="patient-ai-observation-title">
      <div className="patient-ai-result-section-heading">
        <h3 id="patient-ai-observation-title">Tóm tắt kết quả hỗ trợ</h3>
        <p>Thông tin dưới đây mô tả mức độ tương đồng hình ảnh, không phải kết luận bệnh.</p>
      </div>
      <p className="patient-ai-observation-lead">
        Hệ thống nhận thấy các đặc điểm hình ảnh có thể liên quan đến <strong>{patientAiLabel(prediction.disease)}</strong>.
        Kết quả này cần được bác sĩ đánh giá cùng với triệu chứng và tiền sử.
      </p>
      <div className="patient-ai-observation-grid">
        <div>
          <h4>Các nhóm hình ảnh gần nhất</h4>
          <ol>
            {prediction.top3.map((item, index) => (
              <li key={`${item.label}-${index}`}>
                <span><b>{index + 1}</b>{patientAiLabel(item.label)}</span>
                <strong>{formatAiPercentage(item.probability)}</strong>
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h4>Điều AI chưa thể đánh giá</h4>
          <p>Hình ảnh không cho biết đầy đủ triệu chứng, thời gian xuất hiện, tiền sử, thuốc đang dùng hoặc kết quả khám trực tiếp.</p>
          <h4>Khuyến nghị tiếp theo</h4>
          <p>Trao đổi với bác sĩ da liễu nếu tổn thương kéo dài, thay đổi hoặc khiến bạn lo lắng.</p>
        </div>
      </div>
    </section>
  );
}

function PatientGuidance({ guidance }: { guidance?: AiDiseaseGuidance }) {
  return (
    <section className="patient-ai-guidance" aria-labelledby="patient-ai-guidance-title">
      <div className="patient-ai-result-section-heading">
        <h3 id="patient-ai-guidance-title">Thông tin tham khảo</h3>
        <p>Nội dung được truy xuất từ tài liệu y khoa để giải thích kết quả theo cách dễ hiểu hơn.</p>
      </div>
      <div className="patient-ai-guidance-copy">
        <BookOpenText aria-hidden="true" />
        <div>
          <h4>{guidance?.title || "Chưa có nội dung giải thích từ tài liệu"}</h4>
          {guidance
            ? guidance.answer.split("\n\n").filter(Boolean).map((paragraph, index) => <p key={index}>{paragraph}</p>)
            : <p>Nguồn tham khảo chưa được trả về cho lần phân tích này. Kết quả hình ảnh vẫn được giữ nguyên.</p>}
        </div>
      </div>
    </section>
  );
}

function AiResultNextAction({ hasAppointment, onBook, onViewAppointment }: { hasAppointment: boolean; onBook: () => void; onViewAppointment: () => void }) {
  return (
    <section className="patient-ai-next-action" aria-labelledby="patient-ai-next-action-title">
      <div>
        <h3 id="patient-ai-next-action-title">Bước tiếp theo</h3>
        <p>{hasAppointment
          ? "Kết quả đã được gắn với lịch hẹn. Bạn có thể kiểm tra lại thời gian khám và trạng thái tiếp nhận."
          : "Đặt lịch để bác sĩ xem ảnh, đối chiếu triệu chứng và đưa ra đánh giá chuyên môn."}</p>
      </div>
      <button type="button" onClick={hasAppointment ? onViewAppointment : onBook}>
        {hasAppointment ? <CalendarCheck2 aria-hidden="true" /> : <CalendarDays aria-hidden="true" />}
        {hasAppointment ? "Xem lịch hẹn" : "Đặt lịch với bác sĩ"}
      </button>
    </section>
  );
}

export default function PatientAiResult({ prediction, assessment, onBook, onViewAppointment }: PatientAiResultProps) {
  return (
    <section className="patient-ai-result" aria-labelledby="patient-ai-result-title">
      <header className="patient-ai-result-header">
        <div>
          <h2 id="patient-ai-result-title">Kết quả phân tích tham khảo</h2>
          <p>Phân tích lúc <time dateTime={assessment.createdAt}>{formatAnalysisDate(assessment.createdAt)}</time></p>
        </div>
        <DoctorReviewStatus assessment={assessment} />
      </header>

      <MedicalAiNotice />

      <div className="patient-ai-result-body" aria-label="Nội dung phân tích từ AI">
        <AiObservationSummary prediction={prediction} />
        <PatientGuidance guidance={prediction.guidance} />
        <AiResultNextAction
          hasAppointment={Boolean(assessment.appointmentId)}
          onBook={onBook}
          onViewAppointment={onViewAppointment}
        />
      </div>
    </section>
  );
}
