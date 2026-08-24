import { useEffect, useState } from "react";
import { BrainCircuit, Image as ImageIcon } from "lucide-react";
import { request, requestBlob } from "../../core/api";
import type { AiAssessment } from "../../core/types";
import { patientAiLabel } from "../patient/patientAiPresentation";

export default function DoctorSharedAi({ token, appointmentId }: { token: string; appointmentId: string }) {
  const [assessment, setAssessment] = useState<AiAssessment | null>(null);
  const [imageUrl, setImageUrl] = useState("");

  useEffect(() => {
    // Ảnh là dữ liệu riêng tư nên tải bằng request có Bearer token, không gắn URL công khai vào thẻ img.
    let active = true;
    let objectUrl = "";
    setAssessment(null);
    setImageUrl("");
    request<AiAssessment | undefined>(`/patients/appointments/${appointmentId}/shared-ai-assessment`, token)
      .then(async value => {
        if (!active || !value) return;
        setAssessment(value);
        if (!value.imageAvailable) return;
        const image = await requestBlob(`/patients/appointments/${appointmentId}/shared-ai-assessment/image`, token);
        objectUrl = URL.createObjectURL(image);
        if (active) setImageUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      active = false;
      // Giải phóng blob URL khi đóng modal/chuyển lịch để tránh tăng bộ nhớ trên điện thoại.
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [appointmentId, token]);

  if (!assessment) return null;

  return <section className="doctor-ai-share">
    <header><span><BrainCircuit /></span><div><small>ẢNH BỆNH NHÂN CHIA SẺ</small><h3>Kết quả kiểm tra da trước buổi khám</h3></div></header>
    <div className="doctor-ai-share-body">
      <div className="doctor-ai-image">
        {imageUrl ? <img src={imageUrl} alt="Ảnh vùng da bệnh nhân chia sẻ" /> : <span><ImageIcon /><small>Kết quả cũ không có ảnh đính kèm</small></span>}
      </div>
      <div className="doctor-ai-summary">
        <small>GỢI Ý CAO NHẤT</small>
        <div><h4>{patientAiLabel(assessment.predictedLabel)}</h4><strong>{(assessment.confidence * 100).toFixed(1)}%</strong></div>
        <ul>{assessment.top3.map(item => <li key={item.label}><span>{patientAiLabel(item.label)}</span><b>{(item.probability * 100).toFixed(1)}%</b></li>)}</ul>
        {assessment.uncertain && <p>AI đánh dấu kết quả này chưa chắc chắn.</p>}
        <em>Phân tích lúc {new Date(assessment.createdAt).toLocaleString("vi-VN")} · {assessment.modelVersion}</em>
      </div>
    </div>
    <footer>Bác sĩ đối chiếu ảnh và khám trực tiếp trước khi đưa ra chẩn đoán.</footer>
  </section>;
}
