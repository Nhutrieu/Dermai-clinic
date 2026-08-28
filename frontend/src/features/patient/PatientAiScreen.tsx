import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BrainCircuit, CalendarDays, Check, ImagePlus, Trash2 } from "lucide-react";
import { ApiError, request } from "../../core/api";
import type { AiAssessment, AiPrediction, Patient } from "../../core/types";
import { EmptyState, ErrorState, StateSkeleton } from "../../components/Ui";
import PatientAiIntake, { type AiAnalysisStage } from "./PatientAiIntake";
import PatientAiResult from "./PatientAiResult";
import { formatAiPercentage, patientAiLabel } from "./patientAiPresentation";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function bookingSummary(assessment: AiAssessment) {
  const top = assessment.top3.map(item => `${patientAiLabel(item.label)} ${formatAiPercentage(item.probability)}`).join("; ");
  return `Kết quả kiểm tra da bằng AI (tham khảo): ${top}. Phiên bản mô hình ${assessment.modelVersion}.${assessment.uncertain ? " AI đánh dấu kết quả chưa chắc chắn." : ""}`;
}

export function validatePhoto(selected: File) {
  if (selected.size > MAX_FILE_BYTES) return "Ảnh vượt quá giới hạn 10 MB.";
  if (!ACCEPTED_TYPES.has(selected.type)) return "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP.";
  return "";
}

export function technicalAnalysisError(value: unknown, failedStage: AiAnalysisStage) {
  if (value instanceof ApiError) {
    if (value.status === 401 || value.status === 403) return "Phiên đăng nhập không còn quyền sử dụng tính năng này. Vui lòng đăng nhập lại.";
    if (value.status === 503) return "Dịch vụ phân tích đang tạm thời chưa sẵn sàng. Vui lòng thử lại sau.";
    if (value.status >= 500) return failedStage === "saving"
      ? "Hệ thống đã xử lý ảnh nhưng chưa thể hoàn tất việc lưu kết quả. Vui lòng thử lại."
      : "Hệ thống chưa thể phân tích ảnh lúc này. Vui lòng thử lại sau ít phút.";
  }
  return (value as Error).message || "Chưa thể hoàn tất phân tích. Vui lòng thử lại.";
}

export function photoRejectionKind(message: string): "out-of-scope" | "quality" | null {
  if (!message) return null;
  if (/ngoài (8 nhóm bệnh|phạm vi)|không thuộc.*nhóm bệnh/i.test(message)) return "out-of-scope";
  if (/quá nhỏ|quá tối|quá sáng|cháy sáng|bị mờ|thiếu chi tiết|độ tương phản/i.test(message)) return "quality";
  return null;
}

export default function PatientAiScreen({ token, patient, openBooking }: { token: string; patient: Patient; openBooking: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [prediction, setPrediction] = useState<AiPrediction | null>(null);
  const [current, setCurrent] = useState<AiAssessment | null>(null);
  const [history, setHistory] = useState<AiAssessment[]>([]);
  const [share, setShare] = useState(false);
  const [analysisStage, setAnalysisStage] = useState<AiAnalysisStage>("idle");
  const [message, setMessage] = useState("");
  const [fileError, setFileError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [actionError, setActionError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState("");
  const resultRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      setHistory(await request<AiAssessment[]>("/patients/me/ai-assessments", token));
    } catch (value) {
      setHistoryError((value as Error).message);
    } finally {
      setHistoryLoading(false);
    }
  }, [token]);

  useEffect(() => { void loadHistory(); }, [loadHistory]);

  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!prediction || !current) return;
    const result = resultRef.current;
    if (!result) return;

    let frame = 0;
    const delay = window.setTimeout(() => {
      const start = window.scrollY;
      const target = Math.max(0, window.scrollY + result.getBoundingClientRect().top - 24);
      const distance = target - start;
      const duration = 900;
      const startedAt = performance.now();
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (prefersReducedMotion) {
        window.scrollTo(0, target);
        return;
      }

      const animate = (now: number) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        window.scrollTo(0, start + distance * eased);
        if (progress < 1) frame = window.requestAnimationFrame(animate);
      };
      frame = window.requestAnimationFrame(animate);
    }, 140);

    return () => {
      window.clearTimeout(delay);
      window.cancelAnimationFrame(frame);
    };
  }, [prediction, current]);

  const latestShared = useMemo(() => history.find(item => item.sharedWithDoctor), [history]);

  function selectFile(selected: File) {
    const validationError = validatePhoto(selected);
    setFileError(validationError);
    setAnalysisError("");
    setActionError("");
    setMessage("");
    setPrediction(null);
    setCurrent(null);
    if (validationError) {
      setFile(null);
      return;
    }
    setFile(selected);
  }

  function removeFile() {
    setFile(null);
    setPrediction(null);
    setCurrent(null);
    setFileError("");
    setAnalysisError("");
    setActionError("");
    setMessage("");
  }

  async function analyze() {
    if (!file || fileError || analysisStage !== "idle") return;
    let failedStage: AiAnalysisStage = "analyzing";
    setAnalysisStage("analyzing");
    setAnalysisError("");
    setActionError("");
    setMessage("");
    setPrediction(null);
    setCurrent(null);
    try {
      const form = new FormData();
      form.append("image", file);
      const result = await request<AiPrediction>("/ai/predict", token, { method: "POST", body: form });
      failedStage = "saving";
      setAnalysisStage("saving");
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
      if (value instanceof ApiError && [413, 415, 422].includes(value.status)) {
        setFileError(value.message || "Tệp ảnh chưa hợp lệ.");
      } else {
        setAnalysisError(technicalAnalysisError(value, failedStage));
      }
    } finally {
      setAnalysisStage("idle");
    }
  }

  async function changeSharing(assessment: AiAssessment, sharedWithDoctor: boolean) {
    setActionError("");
    try {
      const updated = await request<AiAssessment>(`/patients/me/ai-assessments/${assessment.id}/sharing`, token, {
        method: "PATCH",
        body: JSON.stringify({ sharedWithDoctor }),
      });
      setHistory(items => items.map(item => item.id === updated.id ? updated : item));
      if (current?.id === updated.id) setCurrent(updated);
      setMessage(sharedWithDoctor ? "Kết quả sẽ được đính kèm khi bạn đặt lịch." : "Đã tắt chia sẻ kết quả này.");
    } catch (value) {
      setActionError((value as Error).message);
    }
  }

  async function book(assessment: AiAssessment) {
    setActionError("");
    try {
      let selected = assessment;
      if (!selected.sharedWithDoctor) {
        selected = await request<AiAssessment>(`/patients/me/ai-assessments/${assessment.id}/sharing`, token, {
          method: "PATCH",
          body: JSON.stringify({ sharedWithDoctor: true }),
        });
        setHistory(items => items.map(item => item.id === selected.id ? selected : item));
        if (current?.id === selected.id) setCurrent(selected);
      }
      // Keep the existing booking handoff so the selected AI result is attached after confirmation.
      sessionStorage.setItem("dermai-ai-booking", JSON.stringify({ assessmentId: selected.id, summary: bookingSummary(selected) }));
      openBooking();
    } catch (value) {
      setActionError((value as Error).message || "Chưa thể mở luồng đặt lịch với kết quả này.");
    }
  }

  async function remove(assessment: AiAssessment) {
    if (confirmDelete !== assessment.id) {
      setConfirmDelete(assessment.id);
      return;
    }
    setActionError("");
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
      setActionError((value as Error).message);
    }
  }

  return <div className="patient-ai-page">
    <PatientAiIntake
      file={file}
      preview={preview}
      share={share}
      stage={analysisStage}
      outcome={prediction && current ? (prediction.uncertain ? "uncertain" : "success") : null}
      fileError={fileError}
      rejectionKind={photoRejectionKind(fileError)}
      analysisError={analysisError}
      onSelectFile={selectFile}
      onRemoveFile={removeFile}
      onShareChange={setShare}
      onAnalyze={analyze}
    />

    {prediction && current && <div ref={resultRef} className="patient-ai-result-anchor">
      <PatientAiResult
        prediction={prediction}
        assessment={current}
        onBook={() => void book(current)}
        onViewAppointment={openBooking}
      />
    </div>}

    {(message || actionError) && <p className={`ai-feedback ${actionError ? "error" : ""}`} role={actionError ? "alert" : "status"} aria-live={actionError ? "assertive" : "polite"}>{actionError || message}</p>}

    <section className="ai-history panel">
      <div className="ai-history-head"><div><h3>Kết quả kiểm tra gần đây</h3><p>Lịch sử của {patient.fullName}</p></div>{latestShared && <span><Check /> Có kết quả đang chia sẻ</span>}</div>
      {historyLoading && <StateSkeleton rows={2} label="Đang tải kết quả kiểm tra da" />}
      {!historyLoading && historyError && <ErrorState title="Không thể tải kết quả đã lưu" description={historyError} retry={() => void loadHistory()} />}
      {!historyLoading && !historyError && history.length === 0 && <EmptyState
        icon={ImagePlus}
        title="Chưa có kết quả kiểm tra da"
        description="Chọn một ảnh rõ nét để bắt đầu. Kết quả chỉ mang tính tham khảo và không thay thế kết luận của bác sĩ."
        action={{
          label: "Chọn ảnh để kiểm tra",
          onClick: () => document.querySelector<HTMLInputElement>(".ai-intake-file-input")?.click(),
        }}
        note="Ảnh JPEG, PNG hoặc WebP, tối đa 10 MB."
      />}
      {!historyLoading && !historyError && history.length > 0 && <>
        <div className="ai-history-list">{(historyExpanded ? history : history.slice(0, 5)).map(item => <article key={item.id}>
          <div className={`ai-history-mark ${item.uncertain ? "uncertain" : ""}`}><BrainCircuit /></div>
          <div className="ai-history-summary">
            <small>{new Date(item.createdAt).toLocaleString("vi-VN")}</small>
            <b>{patientAiLabel(item.predictedLabel)}</b>
            <p>{item.imageAvailable ? "Ảnh đã lưu" : "Không có ảnh đính kèm"}</p>
          </div>
          <div className="ai-history-actions">
            <button type="button" className={item.sharedWithDoctor ? "shared" : ""} onClick={() => changeSharing(item, !item.sharedWithDoctor)}>{item.sharedWithDoctor ? "Đang chia sẻ" : "Chia sẻ khi đặt lịch"}</button>
            <button type="button" className="ai-history-book" onClick={() => book(item)}><CalendarDays /> Đặt lịch</button>
            <button type="button" className={`ai-delete ${confirmDelete === item.id ? "confirm" : ""}`} aria-label={confirmDelete === item.id ? "Xác nhận xóa kết quả AI" : "Xóa kết quả AI"} aria-pressed={confirmDelete === item.id} onClick={() => remove(item)}><Trash2 />{confirmDelete === item.id && <span>Xác nhận xóa</span>}</button>
          </div>
        </article>)}</div>
        {history.length > 5 && <button type="button" className="ai-history-toggle" onClick={() => setHistoryExpanded(expanded => !expanded)}>
          {historyExpanded ? "Thu gọn" : `Xem thêm ${history.length - 5} kết quả`}
        </button>}
      </>}
    </section>
  </div>;
}
