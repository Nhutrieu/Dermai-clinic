import { useState } from "react";
import { AlertCircle, CalendarDays, Camera, Cake, Check, FileHeart, Link2, Mail, Pencil, Phone, Save, ShieldCheck, UserRound, X } from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import { request } from "../../core/api";
import type { AccountProfile, Patient } from "../../core/types";

type PatientAccountDialogProps = {
  token: string;
  account: AccountProfile;
  patient: Patient;
  avatarSrc: string;
  onChanged: (profile: AccountProfile, avatarChanged?: boolean) => void;
  onPatientChanged: (patient: Patient) => void;
  onClose: () => void;
};

const statusLabel: Record<AccountProfile["status"], string> = {
  PENDING: "Chờ xác minh",
  ACTIVE: "Đang hoạt động",
  LOCKED: "Đã khóa",
  DISABLED: "Đã vô hiệu hóa",
};

function formatDate(value?: string) {
  if (!value) return "Chưa khai báo";
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

export default function PatientAccountDialog({ token, account, patient, avatarSrc, onChanged, onPatientChanged, onClose }: PatientAccountDialogProps) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    fullName: patient.fullName,
    dob: patient.dob || "",
    phone: patient.phone || "",
    allergies: patient.allergies || "",
    medicalHistory: patient.medicalHistory || "",
  });

  async function uploadAvatar(file?: File) {
    if (!file) return;
    setMessage(""); setError("");
    if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) { setError("Chỉ nhận ảnh JPG, PNG hoặc WebP."); return; }
    if (file.size > 2 * 1024 * 1024) { setError("Ảnh đại diện tối đa 2 MB."); return; }
    const body = new FormData(); body.append("image", file); setBusy(true);
    try {
      const updated = await request<AccountProfile>("/auth/me/avatar", token, { method: "POST", body });
      onChanged(updated, true); setMessage("Đã cập nhật ảnh đại diện.");
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage(""); setError("");
    try {
      const updated = await request<Patient>("/patients/me", token, {
        method: "PATCH",
        body: JSON.stringify({ ...form, dob: form.dob || null }),
      });
      onPatientChanged(updated); setEditing(false); setMessage("Hồ sơ bệnh nhân đã được cập nhật.");
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }

  function resetForm() {
    setForm({ fullName: patient.fullName, dob: patient.dob || "", phone: patient.phone || "", allergies: patient.allergies || "", medicalHistory: patient.medicalHistory || "" });
    setEditing(false); setError("");
  }

  const initial = patient.fullName.trim().charAt(0).toLocaleUpperCase("vi");
  return <AccessibleDialog title="Tài khoản của tôi" titleId="patient-account-title" descriptionId="patient-account-content" className="receptionist-account-dialog patient-account-dialog" backdropClassName="receptionist-account-backdrop" closeDisabled={busy} closeOnBackdrop={!busy} onClose={onClose}>
    <div className="patient-account-heading"><p className="receptionist-account-intro">Quản lý thông tin cá nhân và dữ liệu y khoa được sử dụng trong quá trình đặt lịch, thăm khám.</p>{!editing && <button type="button" onClick={() => setEditing(true)}><Pencil /> Chỉnh sửa hồ sơ</button>}</div>

    <div className="receptionist-account-identity patient-account-identity">
      <label className="receptionist-avatar-picker" aria-label="Chọn ảnh đại diện">{avatarSrc ? <img src={avatarSrc} alt={`Ảnh đại diện ${patient.fullName}`} /> : <span aria-hidden="true">{initial}</span>}<b><Camera aria-hidden="true" /> Thay ảnh</b><input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => void uploadAvatar(event.target.files?.[0])} /></label>
      <div><small>HỒ SƠ BỆNH NHÂN</small><strong>{patient.fullName}</strong><span>Mã bệnh nhân · {patient.id.slice(0, 8).toUpperCase()}</span><em><ShieldCheck /> Thông tin được bảo vệ trong hệ thống phòng khám</em></div>
    </div>

    {editing ? <form className="patient-account-edit" onSubmit={saveProfile}>
      <div className="patient-account-section-title"><UserRound /><div><b>Chỉnh sửa thông tin</b><small>Các trường có dấu * là bắt buộc.</small></div></div>
      <div className="patient-account-fields"><label>Họ và tên *<input required maxLength={160} value={form.fullName} onChange={event => setForm({ ...form, fullName: event.target.value })} /></label><label>Ngày sinh<input type="date" max={new Date().toISOString().slice(0, 10)} value={form.dob} onChange={event => setForm({ ...form, dob: event.target.value })} /></label><label>Số điện thoại *<input required inputMode="tel" value={form.phone} onChange={event => setForm({ ...form, phone: event.target.value })} /></label><label>Dị ứng<textarea maxLength={2000} placeholder="Ví dụ: Penicillin, hải sản…" value={form.allergies} onChange={event => setForm({ ...form, allergies: event.target.value })} /></label><label className="wide">Tiền sử bệnh và điều trị<textarea maxLength={4000} placeholder="Các bệnh lý, thủ thuật hoặc liệu trình đã thực hiện…" value={form.medicalHistory} onChange={event => setForm({ ...form, medicalHistory: event.target.value })} /></label></div>
      <div className="patient-account-edit-actions"><button type="button" onClick={resetForm} disabled={busy}><X /> Hủy chỉnh sửa</button><button type="submit" className="save" disabled={busy}><Save /> {busy ? "Đang lưu…" : "Lưu thay đổi"}</button></div>
    </form> : <>
      <section className="patient-account-section"><div className="patient-account-section-title"><UserRound /><div><b>Thông tin cá nhân</b><small>Thông tin nhận diện và liên hệ của tài khoản.</small></div></div><dl className="receptionist-account-details patient-account-details">
        <div><dt><Mail /> Email đăng nhập</dt><dd>{account.email}</dd></div><div><dt><Phone /> Số điện thoại</dt><dd>{patient.phone || "Chưa khai báo"}</dd></div><div><dt><Cake /> Ngày sinh</dt><dd>{formatDate(patient.dob)}</dd></div><div><dt><CalendarDays /> Ngày tạo tài khoản</dt><dd>{formatDate(account.createdAt)}</dd></div><div><dt><ShieldCheck /> Trạng thái</dt><dd><span data-status={account.status}>{statusLabel[account.status]}</span></dd></div><div><dt><Link2 /> Liên kết hồ sơ</dt><dd><span data-status={patient.accountLinked === false ? "PENDING" : "ACTIVE"}>{patient.accountLinked === false ? "Chưa liên kết" : "Đã liên kết"}</span></dd></div><div><dt>Mã tài khoản</dt><dd>{account.identityId.slice(0, 8).toUpperCase()}</dd></div><div><dt>Mã bệnh nhân</dt><dd>{patient.id.slice(0, 8).toUpperCase()}</dd></div>
      </dl></section>
      <section className="patient-account-section patient-medical-summary"><div className="patient-account-section-title"><FileHeart /><div><b>Thông tin y khoa</b><small>Giúp bác sĩ nắm bắt các lưu ý trước khi thăm khám.</small></div></div><div className="patient-account-medical-grid"><article><span><AlertCircle /> Dị ứng đã khai báo</span><p>{patient.allergies?.trim() || "Chưa ghi nhận dị ứng."}</p></article><article><span><FileHeart /> Tiền sử bệnh và điều trị</span><p>{patient.medicalHistory?.trim() || "Chưa có thông tin tiền sử y khoa."}</p></article></div><p className="patient-account-medical-note"><Check /> Hãy cập nhật khi thông tin sức khỏe thay đổi để bác sĩ tham khảo trước buổi khám.</p></section>
    </>}
    {error && <p className="receptionist-account-message is-error" role="alert">{error}</p>}{message && <p className="receptionist-account-message is-success" role="status" aria-live="polite">{message}</p>}
  </AccessibleDialog>;
}