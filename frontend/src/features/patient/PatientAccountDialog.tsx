import { useState } from "react";
import { CalendarDays, Camera, Mail, Phone, ShieldCheck } from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import { request } from "../../core/api";
import type { AccountProfile, Patient } from "../../core/types";

type PatientAccountDialogProps = {
  token: string;
  account: AccountProfile;
  patient: Patient;
  avatarSrc: string;
  onChanged: (profile: AccountProfile, avatarChanged?: boolean) => void;
  onClose: () => void;
};

const statusLabel: Record<AccountProfile["status"], string> = {
  PENDING: "Chờ xác minh",
  ACTIVE: "Đang hoạt động",
  LOCKED: "Đã khóa",
  DISABLED: "Đã vô hiệu hóa",
};

export default function PatientAccountDialog({ token, account, patient, avatarSrc, onChanged, onClose }: PatientAccountDialogProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function uploadAvatar(file?: File) {
    if (!file) return;
    setMessage("");
    setError("");
    if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) {
      setError("Chỉ nhận ảnh JPG, PNG hoặc WebP.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("Ảnh đại diện tối đa 2 MB.");
      return;
    }

    const body = new FormData();
    body.append("image", file);
    setBusy(true);
    try {
      const updated = await request<AccountProfile>("/auth/me/avatar", token, { method: "POST", body });
      // Reload through the authenticated blob endpoint; no patient image is made public.
      onChanged(updated, true);
      setMessage("Đã cập nhật ảnh đại diện.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const initial = patient.fullName.trim().charAt(0).toLocaleUpperCase("vi");
  const createdAt = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(account.createdAt));

  return (
    <AccessibleDialog
      title="Tài khoản của tôi"
      titleId="patient-account-title"
      descriptionId="patient-account-content"
      className="receptionist-account-dialog patient-account-dialog"
      backdropClassName="receptionist-account-backdrop"
      closeDisabled={busy}
      closeOnBackdrop={!busy}
      onClose={onClose}
    >
      <p className="receptionist-account-intro">Thông tin đăng nhập và liên hệ đang được sử dụng cho lịch khám của bạn.</p>

      <div className="receptionist-account-identity">
        <label className="receptionist-avatar-picker" aria-label="Chọn ảnh đại diện">
          {avatarSrc ? <img src={avatarSrc} alt={`Ảnh đại diện ${patient.fullName}`} /> : <span aria-hidden="true">{initial}</span>}
          <b><Camera aria-hidden="true" /> Thay ảnh</b>
          <input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => void uploadAvatar(event.target.files?.[0])} />
        </label>
        <div>
          <strong>{patient.fullName}</strong>
          <span>Bệnh nhân</span>
          <small>JPG, PNG hoặc WebP · tối đa 2 MB</small>
        </div>
      </div>

      <dl className="receptionist-account-details patient-account-details">
        <div><dt><Mail aria-hidden="true" />Email đăng nhập</dt><dd>{account.email}</dd></div>
        <div><dt><Phone aria-hidden="true" />Số điện thoại</dt><dd>{patient.phone || "Chưa khai báo"}</dd></div>
        <div><dt><ShieldCheck aria-hidden="true" />Trạng thái</dt><dd><span data-status={account.status}>{statusLabel[account.status]}</span></dd></div>
        <div><dt><CalendarDays aria-hidden="true" />Ngày tạo</dt><dd>{createdAt}</dd></div>
        <div><dt>Mã tài khoản</dt><dd>{account.identityId.slice(0, 8).toUpperCase()}</dd></div>
      </dl>

      {error && <p className="receptionist-account-message is-error" role="alert">{error}</p>}
      {message && <p className="receptionist-account-message is-success" role="status" aria-live="polite">{message}</p>}
    </AccessibleDialog>
  );
}
