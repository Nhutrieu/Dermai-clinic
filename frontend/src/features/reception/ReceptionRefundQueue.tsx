import { FormEvent, useCallback, useEffect, useState } from "react";
import { BadgeCheck, Banknote, CheckCircle2, ChevronDown, ChevronUp, Clock3, ImageIcon, ReceiptText, RefreshCw, Search, ShieldCheck, X } from "lucide-react";
import { request, requestBlob } from "../../core/api";

type RefundMethod = "BANK_TRANSFER" | "CASH";
type RefundPayment = {
  id: string;
  bookingId: string;
  amount: number;
  orderCode: number;
  status: "REFUND_REQUESTED" | "REFUNDED";
  refundReason?: string;
  refundRequestedByRole?: string;
  refundInitiator?: "PATIENT_REQUEST" | "CLINIC";
  refundRequestedAt?: string;
  refundAmount?: number;
  refundedAt?: string;
  refundReference?: string;
  refundMethod?: RefundMethod;
  refundReceiptNumber?: string;
  refundRecipientName?: string;
  refundEvidenceAvailable?: boolean;
  refundEvidenceOriginalName?: string;
  refundCompletedByIdentity?: string;
  refundCompletedByRole?: string;
};
type StaffDirectoryEntry = { identityId: string; displayName?: string | null };
type EvidencePreview = { url: string; name: string };

const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
const dateTime = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric" });
const allowedEvidenceTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxEvidenceBytes = 5 * 1024 * 1024;
const refundHistoryPageSize = 6;

function formatDateTime(value?: string) {
  if (!value) return "Chưa cập nhật";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Chưa cập nhật" : dateTime.format(parsed);
}

function RefundAction({ payment, token, completed }: { payment: RefundPayment; token: string; completed: () => void }) {
  const clinicCancelled = payment.refundInitiator === "CLINIC";
  const policyAmount = payment.refundAmount ?? payment.amount;
  const [method, setMethod] = useState<RefundMethod>("BANK_TRANSFER");
  const [reference, setReference] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [evidence, setEvidence] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const validProof = method === "CASH" ? Boolean(recipientName.trim()) : Boolean(reference.trim() || evidence);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!validProof) {
      setError(method === "CASH" ? "Vui lòng nhập tên người nhận tiền mặt." : "Vui lòng nhập mã giao dịch hoặc tải ảnh biên lai.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("amount", String(policyAmount));
      form.append("method", method);
      if (reference.trim()) form.append("reference", reference.trim());
      if (recipientName.trim()) form.append("recipientName", recipientName.trim());
      if (evidence) form.append("evidence", evidence);
      await request(`/payments/${payment.id}/refunds/complete`, token, { method: "POST", body: form });
      completed();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function chooseEvidence(file: File | null) {
    if (!file) { setEvidence(null); return; }
    if (file.size > maxEvidenceBytes) { setEvidence(null); setError("Ảnh biên lai tối đa 5 MB."); return; }
    if (!allowedEvidenceTypes.has(file.type)) { setEvidence(null); setError("Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP."); return; }
    setError("");
    setEvidence(file);
  }

  return <form className="refund-action" onSubmit={submit}>
    <div className="refund-policy-amount">
      <span>Số tiền cần hoàn</span>
      <strong>{money.format(policyAmount)}</strong>
      <small>{clinicCancelled ? "Hoàn đủ do phòng khám chủ động hủy" : "Đã tính tự động theo chính sách hoàn tiền"}</small>
    </div>
    <label>Phương thức hoàn
      <select value={method} onChange={event => { setMethod(event.target.value as RefundMethod); setError(""); }}>
        <option value="BANK_TRANSFER">Chuyển khoản</option>
        <option value="CASH">Tiền mặt</option>
      </select>
    </label>
    {method === "BANK_TRANSFER" ? <>
      <label>Mã giao dịch <small>Không bắt buộc nếu có ảnh biên lai</small>
        <input maxLength={200} value={reference} onChange={event => setReference(event.target.value)} placeholder="Ví dụ: FT2409..." />
      </label>
      <label className="refund-proof">Ảnh biên lai <small>JPG, PNG hoặc WebP · tối đa 5 MB</small>
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => chooseEvidence(event.target.files?.[0] || null)} />
      </label>
    </> : <>
      <label className="refund-recipient">Người nhận tiền
        <input required maxLength={200} value={recipientName} onChange={event => setRecipientName(event.target.value)} placeholder="Họ tên người nhận" />
      </label>
      <label className="refund-proof">Ảnh phiếu ký nhận <small>Không bắt buộc · JPG, PNG hoặc WebP · tối đa 5 MB</small>
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => chooseEvidence(event.target.files?.[0] || null)} />
      </label>
    </>}
    {evidence && <small className="refund-selected-proof"><ImageIcon aria-hidden="true" /> Đã chọn: {evidence.name}</small>}
    {method === "CASH" && <small className="refund-form-note">Hệ thống tự sinh số phiếu hoàn tiền, không cần nhập mã giao dịch.</small>}
    {error && <small className="refund-error refund-form-error" role="alert">{error}</small>}
    <button type="submit" disabled={busy || !validProof || policyAmount <= 0}>{busy ? "Đang lưu…" : "Xác nhận đã hoàn"}</button>
  </form>;
}

export default function ReceptionRefundQueue({ token, readOnly = false }: { token: string; readOnly?: boolean }) {
  const [items, setItems] = useState<RefundPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [staffNames, setStaffNames] = useState<Record<string, string>>({});
  const [evidenceLoading, setEvidenceLoading] = useState<string | null>(null);
  const [evidenceErrors, setEvidenceErrors] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<EvidencePreview | null>(null);
  const [historyQuery, setHistoryQuery] = useState("");
  const [visibleHistoryCount, setVisibleHistoryCount] = useState(refundHistoryPageSize);

  const load = useCallback(async () => {
    try {
      const [refunds, directory] = await Promise.all([
        request<RefundPayment[]>("/payments/refunds", token),
        readOnly ? request<StaffDirectoryEntry[]>("/auth/staff/directory", token) : Promise.resolve([]),
      ]);
      setItems(refunds);
      setStaffNames(Object.fromEntries(directory.map(member => [member.identityId, member.displayName || `Nhân viên ${member.identityId.slice(0, 8)}`])));
      setError("");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
    }
  }, [token, readOnly]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load, revision]);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview.url);
  }, [preview]);

  function closePreview() {
    if (preview) URL.revokeObjectURL(preview.url);
    setPreview(null);
  }

  async function viewEvidence(payment: RefundPayment) {
    setEvidenceLoading(payment.id);
    setEvidenceErrors(current => ({ ...current, [payment.id]: "" }));
    try {
      const blob = await requestBlob(`/payments/${payment.id}/refunds/evidence`, token);
      if (preview) URL.revokeObjectURL(preview.url);
      setPreview({ url: URL.createObjectURL(blob), name: payment.refundEvidenceOriginalName || "Chứng từ hoàn tiền" });
    } catch (cause) {
      setEvidenceErrors(current => ({ ...current, [payment.id]: (cause as Error).message }));
    } finally {
      setEvidenceLoading(null);
    }
  }

  function completedBy(payment: RefundPayment) {
    return payment.refundCompletedByIdentity
      ? staffNames[payment.refundCompletedByIdentity] || `${payment.refundCompletedByRole === "ADMIN" ? "Admin" : "Lễ tân"} ${payment.refundCompletedByIdentity.slice(0, 8)}`
      : "Chưa rõ người thực hiện";
  }

  const pending = items.filter(item => item.status === "REFUND_REQUESTED");
  const completed = items.filter(item => item.status === "REFUNDED");
  const normalizedHistoryQuery = historyQuery.trim().toLocaleLowerCase("vi-VN");
  const filteredCompleted = completed.filter(payment => {
    if (!normalizedHistoryQuery) return true;
    const searchable = [
      payment.orderCode,
      payment.bookingId,
      payment.refundReference,
      payment.refundReceiptNumber,
      payment.refundRecipientName,
      payment.refundMethod === "CASH" ? "tiền mặt" : "chuyển khoản",
      money.format(payment.refundAmount ?? 0),
      readOnly ? completedBy(payment) : "",
    ].filter(Boolean).join(" ").toLocaleLowerCase("vi-VN");
    return searchable.includes(normalizedHistoryQuery);
  });
  const visibleCompleted = filteredCompleted.slice(0, visibleHistoryCount);
  const pendingAmount = pending.reduce((sum, item) => sum + (item.refundAmount ?? item.amount), 0);
  const completedAmount = completed.reduce((sum, item) => sum + (item.refundAmount ?? 0), 0);

  return <section className="panel refund-queue" aria-labelledby="refund-queue-title">
    <header className="refund-header">
      <div><span className="section-kicker">{readOnly ? "GIÁM SÁT HOÀN TIỀN" : "HOÀN TIỀN CỌC"}</span><h2 id="refund-queue-title">{readOnly ? "Theo dõi hoàn tiền" : "Xử lý yêu cầu hoàn tiền"}</h2><p>{readOnly ? "Theo dõi số tiền, người xử lý và chứng từ đối soát. Thao tác hoàn tiền do lễ tân thực hiện." : "Kiểm tra mức hoàn do hệ thống tính, chuyển tiền và lưu chứng từ để đối soát."}</p></div>
      <button type="button" className="refund-refresh" onClick={() => void load()} disabled={loading}><RefreshCw aria-hidden="true" className={loading ? "is-spinning" : ""} /> {loading ? "Đang tải" : "Làm mới"}</button>
    </header>

    <div className="refund-stats" aria-label="Tổng quan hoàn tiền">
      <div><span className="refund-stat-icon is-pending"><Clock3 aria-hidden="true" /></span><span><small>Đang chờ xử lý</small><strong>{pending.length} yêu cầu</strong></span></div>
      <div><span className="refund-stat-icon is-money"><Banknote aria-hidden="true" /></span><span><small>Số tiền đang chờ</small><strong>{money.format(pendingAmount)}</strong></span></div>
      <div><span className="refund-stat-icon is-completed"><CheckCircle2 aria-hidden="true" /></span><span><small>Đã hoàn gần đây</small><strong>{money.format(completedAmount)}</strong></span></div>
    </div>

    {error && <div className="refund-load-error" role="alert"><span><b>Không tải được dữ liệu hoàn tiền</b><small>{error}</small></span><button type="button" onClick={() => void load()}>Thử lại</button></div>}
    {readOnly && pending.length > 0 && <div className="refund-admin-alert" role="status"><ShieldCheck aria-hidden="true" /><span><b>{pending.length} yêu cầu đang chờ lễ tân xử lý</b><small>Admin sẽ thấy người thực hiện và chứng từ ngay sau khi hoàn tất.</small></span></div>}

    {!loading && !error && pending.length === 0 && <div className="refund-empty"><BadgeCheck aria-hidden="true" /><span><b>Không có yêu cầu đang chờ</b><small>Tất cả yêu cầu hoàn cọc hiện đã được xử lý.</small></span></div>}

    <div className="refund-list">{pending.map(payment => <article key={payment.id}>
      <div className="refund-summary">
        <div className="refund-request-heading"><span className={`refund-origin ${payment.refundInitiator === "CLINIC" ? "is-clinic" : "is-patient"}`}>{payment.refundInitiator === "CLINIC" ? "Phòng khám hủy" : "Bệnh nhân yêu cầu"}</span><h3>{money.format(payment.refundAmount ?? payment.amount)}</h3><small>Yêu cầu lúc {formatDateTime(payment.refundRequestedAt)}</small></div>
        <div className="refund-request-meta"><span><small>Mã đơn</small><b>{payment.orderCode}</b></span><span><small>Mã lịch</small><b>#{payment.bookingId.slice(0, 8)}</b></span><span className="is-wide"><small>Lý do</small><b>{payment.refundReason || "Không có lý do"}</b></span></div>
        <p className="refund-policy-note"><ShieldCheck aria-hidden="true" /> Tiền cọc {money.format(payment.amount)} · mức hoàn đã khóa theo chính sách</p>
      </div>
      {readOnly ? <div className="refund-monitor-status"><Clock3 aria-hidden="true" /><span><b>Đang chờ lễ tân xử lý</b><small>Admin không cần thao tác tại đây.</small></span></div> : <RefundAction payment={payment} token={token} completed={() => setRevision(value => value + 1)} />}
    </article>)}</div>

    {completed.length > 0 && <section className="refund-history" aria-labelledby="refund-history-title">
      <div className="refund-history-heading"><div><span className="section-kicker">LỊCH SỬ GẦN ĐÂY</span><h3 id="refund-history-title">Đã hoàn tiền</h3></div><span>{completed.length} giao dịch</span></div>
      <div className="refund-history-toolbar">
        <label><Search aria-hidden="true" /><input type="search" value={historyQuery} onChange={event => { setHistoryQuery(event.target.value); setVisibleHistoryCount(refundHistoryPageSize); }} placeholder="Tìm mã đơn, mã giao dịch, người nhận…" aria-label="Tìm trong lịch sử hoàn tiền" />{historyQuery && <button type="button" onClick={() => { setHistoryQuery(""); setVisibleHistoryCount(refundHistoryPageSize); }} aria-label="Xóa nội dung tìm kiếm"><X aria-hidden="true" /></button>}</label>
        <span>{filteredCompleted.length === completed.length ? `${completed.length} kết quả` : `${filteredCompleted.length} / ${completed.length} kết quả`}</span>
      </div>
      {filteredCompleted.length === 0 ? <div className="refund-history-empty"><Search aria-hidden="true" /><b>Không tìm thấy giao dịch</b><small>Thử tìm bằng mã đơn, mã giao dịch hoặc tên người nhận.</small></div> : <>
      <div className="refund-history-grid">{visibleCompleted.map(payment => <article className="refund-history-card" key={payment.id}>
        <div className="refund-history-top"><span className="refund-completed-icon"><CheckCircle2 aria-hidden="true" /></span><div><small>Đã hoàn</small><strong>{money.format(payment.refundAmount ?? 0)}</strong></div><span className="refund-method-badge">{payment.refundMethod === "CASH" ? "Tiền mặt" : "Chuyển khoản"}</span></div>
        <dl><div><dt>Mã đơn</dt><dd>{payment.orderCode}</dd></div><div><dt>Hoàn lúc</dt><dd>{formatDateTime(payment.refundedAt)}</dd></div>{payment.refundMethod === "CASH" ? <><div><dt>Số phiếu</dt><dd>{payment.refundReceiptNumber || "—"}</dd></div><div><dt>Người nhận</dt><dd>{payment.refundRecipientName || "—"}</dd></div></> : <div className="is-wide"><dt>Mã giao dịch</dt><dd>{payment.refundReference || "Dùng biên lai chuyển khoản"}</dd></div>}{readOnly && <div className="is-wide"><dt>Người thực hiện</dt><dd>{completedBy(payment)}</dd></div>}</dl>
        {payment.refundEvidenceAvailable && <div className="refund-evidence-action"><button type="button" onClick={() => void viewEvidence(payment)} disabled={evidenceLoading === payment.id}><ImageIcon aria-hidden="true" /> {evidenceLoading === payment.id ? "Đang mở…" : "Xem chứng từ"}</button>{evidenceErrors[payment.id] && <small role="alert">{evidenceErrors[payment.id]}</small>}</div>}
      </article>)}</div>
      <div className="refund-history-controls"><span>Đang hiển thị {Math.min(visibleHistoryCount, filteredCompleted.length)} / {filteredCompleted.length} giao dịch</span><div>{visibleHistoryCount > refundHistoryPageSize && <button type="button" onClick={() => setVisibleHistoryCount(refundHistoryPageSize)}><ChevronUp aria-hidden="true" /> Thu gọn</button>}{visibleHistoryCount < filteredCompleted.length && <button type="button" className="is-primary" onClick={() => setVisibleHistoryCount(count => Math.min(count + refundHistoryPageSize, filteredCompleted.length))}>Xem thêm {Math.min(refundHistoryPageSize, filteredCompleted.length - visibleHistoryCount)} <ChevronDown aria-hidden="true" /></button>}</div></div>
      </>}
    </section>}

    {preview && <div className="refund-evidence-modal" role="dialog" aria-modal="true" aria-label="Chứng từ hoàn tiền" onClick={closePreview}><div onClick={event => event.stopPropagation()}><header><span><ReceiptText aria-hidden="true" /><b>{preview.name}</b></span><button type="button" onClick={closePreview} aria-label="Đóng chứng từ"><X aria-hidden="true" /></button></header><img src={preview.url} alt="Chứng từ hoàn tiền" /></div></div>}
  </section>;
}
