import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, BookOpenText, BrainCircuit, CalendarDays, Check, ImagePlus, ShieldCheck, Sparkles, Trash2, Upload } from "lucide-react";
import { request } from "../../core/api";
import type { AiAssessment, AiPrediction, Patient } from "../../core/types";

const LABELS: Record<string, string> = {
  Acne: "Mụn trứng cá",
  Candidiasis: "Nhiễm nấm Candida",
  Eczema: "Chàm / eczema",
  Lupus: "Biểu hiện da liên quan lupus",
  Psoriasis: "Vảy nến",
  SkinCancer: "Nhóm tổn thương nguy cơ ung thư da",
  Tinea: "Nấm da",
  Warts: "Mụn cóc",
};

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function label(value: string) {
  return LABELS[value] || value;
}

function percentage(value: number) {
  return `${(value * 100).toFixed(1).replace(".", ",")}%`;
}

function bookingSummary(assessment: AiAssessment) {
  const top = assessment.top3.map(item => `${label(item.label)} ${percentage(item.probability)}`).join("; ");
  return `Kết quả kiểm tra da bằng AI (tham khảo): ${top}. Model ${assessment.modelVersion}.${assessment.uncertain ? " AI đánh dấu kết quả chưa chắc chắn." : ""}`;
}

export default function PatientAiScreen({ token, patient, openBooking }: { token: string; patient: Patient; openBooking: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [prediction, setPrediction] = useState<AiPrediction | null>(null);
  const [current, setCurrent] = useState<AiAssessment | null>(null);
  const [history, setHistory] = useState<AiAssessment[]>([]);
  const [share, setShare] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState("");

  useEffect(() => {
    request<AiAssessment[]>("/patients/me/ai-assessments", token)
      .then(setHistory)
      .catch(value => setError((value as Error).message));
  }, [token]);

  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const latestShared = useMemo(() => history.find(item => item.sharedWithDoctor), [history]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    setError("");
    setMessage("");
    setPrediction(null);
    setCurrent(null);
    if (selected && (!ACCEPTED_TYPES.has(selected.type) || selected.size > MAX_FILE_BYTES)) {
      setFile(null);
      setError(selected.size > MAX_FILE_BYTES ? "Ảnh vượt quá giới hạn 10 MB." : "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP.");
      return;
    }
    setFile(selected);
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("image", file);
      const result = await request<AiPrediction>("/ai/predict", token, { method: "POST", body: form });
      const saved = await request<AiAssessment>("/patients/me/ai-assessments", token, {
        method: "POST",
        body: JSON.stringify({
          predictedLabel: result.disease,
          confidence: result.confidence,
          top3: result.top3,
          uncertain: result.uncertain,
          modelVersion: result.model_version,
          sharedWithDoctor: share,
        }),
      });
      // AI service chỉ phân tích; ảnh gốc được gửi tiếp về patient-service để quản lý quyền chia sẻ.
      const imageForm = new FormData();
      imageForm.append("image", file);
      await request(`/patients/me/ai-assessments/${saved.id}/image`, token, { method: "PUT", body: imageForm });
      saved.imageAvailable = true;
      setPrediction(result);
      setCurrent(saved);
      setHistory(items => [saved, ...items]);
      setMessage("Đã phân tích và lưu ảnh cùng kết quả vào tài khoản của bạn.");
    } catch (value) {
      setError((value as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function changeSharing(assessment: AiAssessment, sharedWithDoctor: boolean) {
    setError("");
    try {
      const updated = await request<AiAssessment>(`/patients/me/ai-assessments/${assessment.id}/sharing`, token, {
        method: "PATCH",
        body: JSON.stringify({ sharedWithDoctor }),
      });
      setHistory(items => items.map(item => item.id === updated.id ? updated : item));
      if (current?.id === updated.id) setCurrent(updated);
      setMessage(sharedWithDoctor ? "Kết quả sẽ được đính kèm khi bạn đặt lịch." : "Đã tắt chia sẻ kết quả này.");
    } catch (value) {
      setError((value as Error).message);
    }
  }

  async function book(assessment: AiAssessment) {
    let selected = assessment;
    if (!selected.sharedWithDoctor) {
      selected = await request<AiAssessment>(`/patients/me/ai-assessments/${assessment.id}/sharing`, token, {
        method: "PATCH",
        body: JSON.stringify({ sharedWithDoctor: true }),
      });
      setHistory(items => items.map(item => item.id === selected.id ? selected : item));
      if (current?.id === selected.id) setCurrent(selected);
    }
    sessionStorage.setItem("dermai-ai-booking", JSON.stringify({ assessmentId: selected.id, summary: bookingSummary(selected) }));
    openBooking();
  }

  async function remove(assessment: AiAssessment) {
    if (confirmDelete !== assessment.id) {
      setConfirmDelete(assessment.id);
      return;
    }
    setError("");
    try {
      await request(`/patients/me/ai-assessments/${assessment.id}`, token, { method: "DELETE" });
      setHistory(items => items.filter(item => item.id !== assessment.id));
      if (current?.id === assessment.id) {
        setCurrent(null);
        setPrediction(null);
      }
      setConfirmDelete("");
      setMessage("Đã xóa kết quả AI khỏi tài khoản.");
    } catch (value) {
      setError((value as Error).message);
    }
  }

  return <div className="patient-ai-page">
    <section className="ai-intro panel" style={{ gridTemplateColumns: "1fr" }}>
      <div className="ai-intro-copy"><span className="ai-kicker"><Sparkles /> KIỂM TRA DA BẰNG AI</span><h2>Tham khảo ban đầu trước khi đặt lịch.</h2><p>Tải ảnh vùng da cần kiểm tra. DermAI sẽ gợi ý ba nhóm có hình ảnh tương đồng để bạn mô tả tình trạng rõ hơn khi gặp bác sĩ.</p><div className="ai-safety"><ShieldCheck /><span><b>Quyền riêng tư</b><small>Ảnh được bảo vệ và chỉ bác sĩ của lịch khám được chia sẻ mới có thể xem.</small></span></div></div>
    </section>

    <div className="ai-workspace">
      <form className="ai-upload panel" onSubmit={analyze}>
        <div className="ai-section-heading"><div><small>BƯỚC 01</small><h3>Chọn ảnh tổn thương da</h3></div><ImagePlus /></div>
        <label className={`ai-dropzone ${preview ? "has-image" : ""}`}>
          {preview ? <img src={preview} alt="Ảnh da chuẩn bị phân tích" /> : <div><Upload /><b>Chọn hoặc chụp ảnh</b><span>JPEG, PNG, WebP · tối đa 10 MB</span></div>}
          <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={chooseFile} />
        </label>
        <div className="ai-photo-tips"><b>Ảnh tốt nên:</b><span><Check /> Đủ sáng, rõ nét</span><span><Check /> Chụp gần vùng da</span><span><Check /> Không dùng bộ lọc màu</span></div>
        <label className="ai-share-choice"><input type="checkbox" checked={share} onChange={event => setShare(event.target.checked)} /><span><b>Chia sẻ ảnh và kết quả khi đặt lịch</b><small>Bác sĩ phụ trách chỉ nhận ảnh cùng phần tóm tắt AI sau khi bạn chủ động đặt lịch.</small></span></label>
        <button className="ai-analyze" disabled={!file || busy}>{busy ? "AI đang phân tích…" : "Phân tích ảnh"}<BrainCircuit /></button>
        <p className="ai-disclaimer"><AlertTriangle /> Không dùng cho cấp cứu, tự kê thuốc hoặc thay thế khám trực tiếp.</p>
      </form>

      <section className="ai-result panel">
        <div className="ai-section-heading"><div><small>BƯỚC 02</small><h3>Kết quả tham khảo</h3></div><BrainCircuit /></div>
        {!prediction && <div className="ai-result-empty"><span><BrainCircuit /></span><b>Chưa có kết quả</b><p>Chọn một ảnh rõ nét rồi nhấn “Phân tích ảnh”.</p></div>}
        {prediction && current && <div className="ai-result-content">
          <div className={`ai-confidence ${prediction.uncertain ? "uncertain" : ""}`}><span><small>GỢI Ý CAO NHẤT</small><b>{label(prediction.disease)}</b><em>{percentage(prediction.confidence)}</em></span>{prediction.uncertain ? <AlertTriangle /> : <Check />}</div>
          {prediction.uncertain && <p className="ai-uncertain-note">AI chưa đủ chắc chắn với ảnh này. Bạn nên đặt lịch để được bác sĩ kiểm tra trực tiếp.</p>}
          <div className="ai-ranking"><b>Ba khả năng tham khảo</b>{prediction.top3.map((item, index) => <div key={item.label}><span><i>{index + 1}</i>{label(item.label)}</span><strong>{percentage(item.probability)}</strong><progress max={1} value={item.probability} /></div>)}</div>
          <div className="ai-gradcam"><div><b>Vùng AI tập trung</b><small>Màu nóng thể hiện vùng ảnh ảnh hưởng nhiều đến kết quả.</small></div><img src={prediction.gradcam_image} alt="Bản đồ Grad-CAM của kết quả AI" /></div>
          {prediction.guidance && <section className={`ai-rag-guidance ${prediction.guidance.has_evidence ? "" : "no-evidence"}`}>
            <header><span><BookOpenText /></span><div><small>TRA CỨU TỪ TÀI LIỆU Y KHOA</small><h4>{prediction.guidance.title}</h4></div></header>
            <div className="ai-rag-answer">{prediction.guidance.answer.split("\n\n").map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
          </section>}
          <p className="ai-result-disclaimer">{prediction.disclaimer}</p>
          <button className="ai-book-result" onClick={() => book(current)}><CalendarDays /> Đặt lịch với kết quả này</button>
        </div>}
      </section>
    </div>

    {(message || error) && <p className={`ai-feedback ${error ? "error" : ""}`}>{error || message}</p>}

    <section className="ai-history panel">
      <div className="ai-history-head"><div><small>LỊCH SỬ CỦA {patient.fullName.toUpperCase()}</small><h3>Kết quả kiểm tra gần đây</h3></div>{latestShared && <span><Check /> Có kết quả đang chia sẻ</span>}</div>
      {history.length === 0 ? <div className="ai-history-empty">Chưa có kết quả AI nào được lưu.</div> : <div className="ai-history-list">{history.map(item => <article key={item.id}><div className={`ai-history-mark ${item.uncertain ? "uncertain" : ""}`}><BrainCircuit /></div><div><small>{new Date(item.createdAt).toLocaleString("vi-VN")}</small><b>{label(item.predictedLabel)}</b><p>Độ tin cậy {percentage(item.confidence)} · {item.modelVersion}</p></div><div className="ai-history-actions"><button className={item.sharedWithDoctor ? "shared" : ""} onClick={() => changeSharing(item, !item.sharedWithDoctor)}>{item.sharedWithDoctor ? "Đang chia sẻ" : "Chia sẻ khi đặt lịch"}</button><button className="ai-history-book" onClick={() => book(item)}><CalendarDays /> Đặt lịch</button><button className={`ai-delete ${confirmDelete === item.id ? "confirm" : ""}`} aria-label="Xóa kết quả AI" onClick={() => remove(item)}><Trash2 />{confirmDelete === item.id && <span>Xác nhận xóa</span>}</button></div></article>)}</div>}
    </section>
  </div>;
}
