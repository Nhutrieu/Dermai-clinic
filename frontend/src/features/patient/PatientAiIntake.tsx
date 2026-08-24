import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  ArrowRight,
  Camera,
  Check,
  CircleCheck,
  ImagePlus,
  Info,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
  Stethoscope,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import "../../styles/patient-ai-scope-notice.css";

export type AiAnalysisStage = "idle" | "analyzing" | "saving";
export type AiAnalysisOutcome = "success" | "uncertain" | null;

type PatientAiIntakeProps = {
  file: File | null;
  preview: string;
  share: boolean;
  stage: AiAnalysisStage;
  outcome: AiAnalysisOutcome;
  fileError: string;
  rejectionKind: "out-of-scope" | "quality" | null;
  analysisError: string;
  onSelectFile: (file: File) => void;
  onRemoveFile: () => void;
  onShareChange: (shared: boolean) => void;
  onAnalyze: () => void;
};

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function MedicalAiNotice() {
  return (
    <div className="ai-intake-medical-notice" role="note" aria-label="Lưu ý y tế">
      <Stethoscope aria-hidden="true" />
      <div>
        <strong>Kết quả chỉ hỗ trợ tham khảo</strong>
        <p>AI phân tích đặc điểm hình ảnh. Bác sĩ da liễu là người đưa ra kết luận chuyên môn.</p>
      </div>
    </div>
  );
}

function SkinPhotoGuidelines() {
  return (
    <section className="ai-intake-guidelines" aria-labelledby="skin-photo-guidelines-title">
      <div className="ai-intake-guidelines-heading">
        <Camera aria-hidden="true" />
        <div>
          <h3 id="skin-photo-guidelines-title">Chuẩn bị ảnh rõ ràng</h3>
          <p>Chụp trực tiếp vùng da cần kiểm tra để hệ thống có đủ thông tin hình ảnh.</p>
        </div>
      </div>

      <div className="ai-intake-guideline-groups">
        <section>
          <h4>Nên</h4>
          <ul>
            <li><Check aria-hidden="true" />Dùng ánh sáng tự nhiên hoặc nơi đủ sáng.</li>
            <li><Check aria-hidden="true" />Giữ camera ổn định và lấy nét vào vùng da.</li>
            <li><Check aria-hidden="true" />Chụp đủ gần để nhìn rõ đặc điểm cần kiểm tra.</li>
          </ul>
        </section>
        <section>
          <h4>Không nên</h4>
          <ul>
            <li><X aria-hidden="true" />Dùng bộ lọc hoặc chỉnh màu ảnh.</li>
            <li><X aria-hidden="true" />Tải ảnh quá mờ, quá xa hoặc không liên quan.</li>
            <li><X aria-hidden="true" />Để khuôn mặt hay thông tin nhận dạng nếu không cần thiết.</li>
          </ul>
        </section>
      </div>

      <div className="ai-intake-privacy-note">
        <LockKeyhole aria-hidden="true" />
        <div>
          <h4>Quyền riêng tư của hình ảnh</h4>
          <p>Ảnh được gửi vào hệ thống để phân tích và lưu cùng kết quả trong tài khoản của bạn. Chỉ chia sẻ với bác sĩ khi bạn chủ động chọn chia sẻ và đặt lịch.</p>
          <p>Chỉ tải ảnh bạn có quyền sử dụng.</p>
        </div>
      </div>
    </section>
  );
}

function SkinPhotoUploader({
  file,
  preview,
  share,
  stage,
  outcome,
  fileError,
  rejectionKind,
  analysisError,
  onSelectFile,
  onRemoveFile,
  onShareChange,
  onAnalyze,
}: PatientAiIntakeProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const chooseButtonRef = useRef<HTMLButtonElement>(null);
  const restoreChooserFocus = useRef(false);
  const [dragActive, setDragActive] = useState(false);
  const [scopeChoice, setScopeChoice] = useState<"supported" | "wound" | null>(null);
  const busy = stage !== "idle";

  // Sau khi xóa preview, trả focus về nút chọn ảnh mới để luồng bàn phím không bị đứt.
  useEffect(() => {
    if (!file && restoreChooserFocus.current) {
      chooseButtonRef.current?.focus();
      restoreChooserFocus.current = false;
    }
  }, [file]);

  useEffect(() => {
    setScopeChoice(null);
  }, [file]);

  function openFilePicker() {
    if (!busy) inputRef.current?.click();
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (selected) onSelectFile(selected);
    // Cho phép người dùng chọn lại đúng file vừa chọn sau một lỗi kỹ thuật.
    event.currentTarget.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    if (busy) return;
    const selected = event.dataTransfer.files?.[0];
    if (selected) onSelectFile(selected);
  }

  function removeFile() {
    restoreChooserFocus.current = true;
    if (inputRef.current) inputRef.current.value = "";
    onRemoveFile();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (scopeChoice !== "supported") return;
    onAnalyze();
  }

  const ctaLabel = stage === "analyzing"
    ? "Đang gửi và phân tích ảnh"
    : stage === "saving"
      ? "Đang hoàn tất kết quả"
      : analysisError
        ? "Thử lại phân tích"
        : outcome
          ? "Phân tích lại ảnh này"
          : "Bắt đầu phân tích";

  return (
    <form className="ai-intake-upload" onSubmit={submit} aria-busy={busy}>
      <div className="ai-intake-upload-heading">
        <div>
          <h3>Ảnh cần kiểm tra</h3>
          <p>Chọn một ảnh chụp rõ vùng da. Bạn có thể thay ảnh trước khi gửi.</p>
        </div>
        <ImagePlus aria-hidden="true" />
      </div>

      <div className="ai-intake-scope-notice" role="status">
        <ShieldAlert aria-hidden="true" />
        <div>
          <strong>Kiểm tra chất lượng và phạm vi đang bật</strong>
          <p>Trước khi phân tích, hệ thống kiểm tra ảnh mờ, thiếu sáng và ảnh nằm ngoài 8 nhóm bệnh được hỗ trợ.</p>
        </div>
        <span>
          <i aria-hidden="true" />
          Đang hoạt động
        </span>
      </div>

      <input
        ref={inputRef}
        className="ai-intake-file-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        tabIndex={-1}
        aria-label="Chọn ảnh vùng da để phân tích"
        onChange={handleFileInput}
      />

      {!preview ? (
        <div
          className={`ai-intake-dropzone${dragActive ? " is-dragging" : ""}${fileError ? " has-error" : ""}`}
          onDragEnter={event => {
            event.preventDefault();
            if (!busy) setDragActive(true);
          }}
          onDragOver={event => event.preventDefault()}
          onDragLeave={event => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragActive(false);
          }}
          onDrop={handleDrop}
        >
          <Upload aria-hidden="true" />
          <strong>Chọn hoặc kéo ảnh vào đây</strong>
          <p>Trên điện thoại, bạn có thể chụp ảnh mới bằng camera.</p>
          <button ref={chooseButtonRef} type="button" onClick={openFilePicker} disabled={busy}>
            Chọn ảnh
          </button>
          <small>JPEG, PNG hoặc WebP. Tối đa 10 MB.</small>
        </div>
      ) : (
        <div className="ai-intake-preview">
          <div className="ai-intake-preview-media">
            <img src={preview} alt="Ảnh vùng da đã chọn, đang chờ phân tích" />
          </div>
          <div className="ai-intake-preview-details">
            <span className="ai-intake-file-ready"><Info aria-hidden="true" />Ảnh đã chọn · chưa kiểm tra</span>
            <strong title={file?.name}>{file?.name}</strong>
            {file && <small>{formatFileSize(file.size)} · {file.type.replace("image/", "").toUpperCase()}</small>}
            <div className="ai-intake-preview-actions">
              <button type="button" onClick={openFilePicker} disabled={busy}>
                <RefreshCw aria-hidden="true" />Thay ảnh
              </button>
              <button type="button" className="ai-intake-remove-photo" onClick={removeFile} disabled={busy}>
                <Trash2 aria-hidden="true" />Xóa ảnh
              </button>
            </div>
          </div>
        </div>
      )}

      {preview && !fileError && (
        <fieldset className="ai-intake-scope-question">
          <legend>Ảnh này có phải vết xước, bỏng, vết thương hở hoặc đang chảy máu không?</legend>
          <p>Những tình trạng này nằm ngoài phạm vi của mô hình phân loại 8 nhóm bệnh da.</p>
          <div>
            <button type="button" className={scopeChoice === "wound" ? "is-selected" : ""} onClick={() => setScopeChoice("wound")}>Có, đây là vết thương</button>
            <button type="button" className={scopeChoice === "supported" ? "is-selected" : ""} onClick={() => setScopeChoice("supported")}>Không, gửi ảnh để hệ thống xác minh</button>
          </div>
          <small>Lựa chọn này không bỏ qua kiểm tra tự động. Ảnh ngoài phạm vi vẫn bị từ chối và không tạo kết quả 8 nhóm bệnh.</small>
        </fieldset>
      )}

      {scopeChoice === "wound" && (
        <div className="ai-intake-wound-warning" role="alert">
          <ShieldAlert aria-hidden="true" />
          <div><strong>Không sử dụng AI cho ảnh này</strong><p>Vết xước, bỏng và vết thương hở chưa nằm trong dữ liệu được hỗ trợ. Hãy vệ sinh phù hợp và liên hệ cơ sở y tế nếu chảy máu khó cầm, đau tăng, sưng đỏ lan rộng, có mủ hoặc sốt.</p></div>
        </div>
      )}

      {fileError && (
        <div className={`ai-intake-alert is-error${rejectionKind ? ` is-${rejectionKind}` : ""}`} role="alert">
          {rejectionKind === "out-of-scope" ? <ShieldAlert aria-hidden="true" /> : <AlertCircle aria-hidden="true" />}
          <div>
            <strong>{rejectionKind === "out-of-scope"
              ? "Ảnh nằm ngoài phạm vi kiểm tra"
              : rejectionKind === "quality"
                ? "Ảnh chưa đủ chất lượng"
                : "Ảnh chưa hợp lệ"}</strong>
            <p>{fileError}</p>
            {rejectionKind === "out-of-scope" && (
              <small>Công cụ chỉ hỗ trợ 8 nhóm hình ảnh da đã công bố. Nếu vùng da bị xước, bỏng, chảy máu, đau nhiều hoặc có dấu hiệu nhiễm trùng, hãy liên hệ phòng khám để được kiểm tra trực tiếp.</small>
            )}
            {preview && <button type="button" onClick={openFilePicker}>Chọn ảnh khác</button>}
          </div>
        </div>
      )}

      {analysisError && (
        <div className="ai-intake-alert is-error" role="alert">
          <AlertCircle aria-hidden="true" />
          <div>
            <strong>Chưa thể hoàn tất phân tích</strong>
            <p>{analysisError}</p>
            <button type="button" onClick={openFilePicker}>Chọn ảnh khác</button>
          </div>
        </div>
      )}

      <label className="ai-intake-share">
        <input
          type="checkbox"
          checked={share}
          disabled={busy}
          onChange={event => onShareChange(event.target.checked)}
        />
        <span>
          <strong>Chia sẻ ảnh và kết quả khi đặt lịch</strong>
          <small>Bác sĩ phụ trách chỉ nhận nội dung này sau khi bạn chủ động đặt lịch.</small>
        </span>
      </label>

      <div className="ai-intake-analysis-state" aria-live="polite" aria-atomic="true">
        {busy && (
          <div className="is-processing">
            <LoaderCircle aria-hidden="true" />
            <span>
              <strong>{stage === "analyzing" ? "Hệ thống đang phân tích đặc điểm hình ảnh" : "Đang lưu ảnh và hoàn tất kết quả"}</strong>
              <small>Quá trình này có thể mất một chút thời gian. Bạn không cần tải lại trang.</small>
            </span>
          </div>
        )}
        {!busy && outcome === "success" && (
          <div className="is-complete">
            <CircleCheck aria-hidden="true" />
            <span><strong>Phân tích đã hoàn tất</strong><small>Xem kết quả tham khảo ở phần bên dưới.</small></span>
          </div>
        )}
        {!busy && outcome === "uncertain" && (
          <div className="is-uncertain">
            <Info aria-hidden="true" />
            <span><strong>Kết quả chưa có đủ độ tin cậy</strong><small>Bạn có thể chụp lại ảnh rõ hơn hoặc đặt lịch để bác sĩ kiểm tra trực tiếp.</small></span>
          </div>
        )}
      </div>

      <div className="ai-intake-actions">
        <button className="ai-intake-submit" disabled={!file || Boolean(fileError) || busy || scopeChoice !== "supported"}>
          {busy && <LoaderCircle className="ai-intake-button-spinner" aria-hidden="true" />}
          <span>{ctaLabel}</span>
          {!busy && <ArrowRight aria-hidden="true" />}
        </button>
        <p><Info aria-hidden="true" />Không dùng công cụ này cho tình huống cấp cứu hoặc để tự kê thuốc.</p>
      </div>
    </form>
  );
}

export default function PatientAiIntake(props: PatientAiIntakeProps) {
  return (
    <>
      <section className="patient-ai-intro" aria-labelledby="patient-ai-title">
        <div>
          <h2 id="patient-ai-title">Kiểm tra hình ảnh da với sự hỗ trợ của AI</h2>
          <p>Tải một ảnh rõ vùng da cần kiểm tra để nhận thông tin tham khảo trước khi trao đổi với bác sĩ.</p>
        </div>
        <MedicalAiNotice />
      </section>

      <section className="ai-intake-shell panel" aria-label="Chuẩn bị và gửi ảnh phân tích">
        <SkinPhotoGuidelines />
        <SkinPhotoUploader {...props} />
      </section>
    </>
  );
}
