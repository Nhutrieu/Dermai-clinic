import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Image as ImageIcon, X } from "lucide-react";
import { request } from "../../core/api";
import type { AiAssessment } from "../../core/types";
import DoctorSharedAi from "./DoctorSharedAi";

export default function DoctorAiPreviewButton({ token, appointmentId }: { token: string; appointmentId: string }) {
  const [available, setAvailable] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Chỉ hiện nút khi lịch này thực sự có kết quả được bệnh nhân chia sẻ.
    request<AiAssessment | undefined>(`/patients/appointments/${appointmentId}/shared-ai-assessment`, token)
      .then(value => setAvailable(Boolean(value)))
      .catch(() => setAvailable(false));
  }, [appointmentId, token]);

  if (!available) return null;
  return <>
    <button type="button" className="doctor-ai-preview-button" onClick={() => setOpen(true)}><ImageIcon /> Ảnh AI</button>
    {/* Portal giúp modal không bị cắt bởi overflow của thẻ lịch, đặc biệt trên màn hình nhỏ. */}
    {open && createPortal(<div className="doctor-ai-preview-backdrop" role="presentation" onMouseDown={() => setOpen(false)}>
      <section className="doctor-ai-preview-modal" role="dialog" aria-modal="true" aria-label="Ảnh bệnh nhân chia sẻ" onMouseDown={event => event.stopPropagation()}>
        <button className="doctor-ai-preview-close" type="button" aria-label="Đóng" onClick={() => setOpen(false)}><X /></button>
        <DoctorSharedAi token={token} appointmentId={appointmentId} />
      </section>
    </div>, document.body)}
  </>;
}
