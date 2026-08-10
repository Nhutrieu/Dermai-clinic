import { type FormEvent, useState } from "react";
import { Camera, Mail, ShieldCheck, UserRound } from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import { request } from "../../core/api";
import type { AccountProfile } from "../../core/types";

type ReceptionistAccountDialogProps = {
  token: string;
  profile: AccountProfile;
  avatarSrc: string;
  onChanged: (profile: AccountProfile, avatarChanged?: boolean) => void;
  onClose: () => void;
};

const accountStatus = (status: AccountProfile["status"]) => status === "ACTIVE" ? "Đang hoạt động" : "Đã khóa";

export default function ReceptionistAccountDialog({
  token,
  profile,
  avatarSrc,
  onChanged,
  onClose,
}: ReceptionistAccountDialogProps) {
  const [displayName, setDisplayName] = useState(profile.displayName || "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const updated = await request<AccountProfile>("/auth/me/profile", token, {
        method: "PATCH",
        body: JSON.stringify({ displayName: displayName.trim() }),
      });
      onChanged(updated);
      setMessage("Đã cập nhật tên hiển thị.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

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
      // The parent reloads the protected image with the current access token.
      onChanged(updated, true);
      setMessage("Đã cập nhật ảnh đại diện.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const initial = (profile.displayName || "Lễ tân").trim().charAt(0).toLocaleUpperCase("vi");
  const createdAt = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(profile.createdAt));

  return (
    <AccessibleDialog
      title="Tài khoản của tôi"
      titleId="receptionist-account-title"
      descriptionId="receptionist-account-content"
      className="receptionist-account-dialog"
      backdropClassName="receptionist-account-backdrop"
      closeDisabled={busy}
      closeOnBackdrop={!busy}
      onClose={onClose}
    >
      <p className="receptionist-account-intro">Thông tin dùng để nhận diện người phụ trách trong hộp thư và nhật ký lịch hẹn.</p>

      <div className="receptionist-account-identity">
        <label className="receptionist-avatar-picker" aria-label="Chọn ảnh đại diện">
          {avatarSrc ? <img src={avatarSrc} alt={`Ảnh đại diện ${profile.displayName || "lễ tân"}`} /> : <span aria-hidden="true">{initial}</span>}
          <b><Camera aria-hidden="true" /> Thay ảnh</b>
          <input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => void uploadAvatar(event.target.files?.[0])} />
        </label>
        <div>
          <strong>{profile.displayName || "Lễ tân"}</strong>
          <span>Lễ tân phòng khám</span>
          <small>JPG, PNG hoặc WebP · tối đa 2 MB</small>
        </div>
      </div>

      <form className="receptionist-account-form" onSubmit={saveProfile}>
        <label htmlFor="receptionist-own-name">Họ và tên</label>
        <div className="receptionist-account-name-row">
          <span><UserRound aria-hidden="true" /><input id="receptionist-own-name" data-dialog-initial-focus required maxLength={150} value={displayName} onChange={event => setDisplayName(event.target.value)} /></span>
          <button type="submit" disabled={busy || !displayName.trim() || displayName.trim() === (profile.displayName || "")}>{busy ? "Đang lưu…" : "Lưu thay đổi"}</button>
        </div>
      </form>

      <dl className="receptionist-account-details">
        <div><dt><Mail aria-hidden="true" />Email đăng nhập</dt><dd>{profile.email}</dd></div>
        <div><dt><ShieldCheck aria-hidden="true" />Trạng thái</dt><dd><span data-status={profile.status}>{accountStatus(profile.status)}</span></dd></div>
        <div><dt>Mã tài khoản</dt><dd>{profile.identityId.slice(0, 8).toUpperCase()}</dd></div>
        <div><dt>Ngày tạo</dt><dd>{createdAt}</dd></div>
      </dl>

      {error && <p className="receptionist-account-message is-error" role="alert">{error}</p>}
      {message && <p className="receptionist-account-message is-success" role="status" aria-live="polite">{message}</p>}
    </AccessibleDialog>
  );
}
