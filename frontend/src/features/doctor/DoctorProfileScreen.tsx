import { FormEvent, useMemo, useState } from "react";
import { BadgeCheck, CalendarOff, Camera, Clock3, Pencil, Save, Trash2, X } from "lucide-react";
import { request } from "../../core/api";
import type { Doctor, LeavePeriod, WorkSchedule } from "../../core/types";

type Props = {
  token: string;
  doctor: Doctor;
  work: WorkSchedule[];
  leave: LeavePeriod[];
  saved: (doctor: Doctor) => void;
};

type FeedbackScope = "overview" | "professional" | "bio" | "leave";
type Feedback = { text: string; error: boolean };
const CLINIC_WORKDAYS = [1, 2, 3, 4, 5, 6];

function localDateValue(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(-2).map(part => part[0]).join("").toUpperCase();
}

function formatFee(value: number) {
  return value ? `${new Intl.NumberFormat("vi-VN").format(value)} đ` : "Chưa cấu hình";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour12: false,
  }).format(new Date(value));
}

function leaveStatusLabel(status: LeavePeriod["status"]) {
  if (status === "PENDING") return "Chờ admin duyệt";
  if (status === "REJECTED") return "Đã từ chối";
  return "Đã duyệt";
}

export default function DoctorProfileScreen({ token, doctor, work, leave, saved }: Props) {
  const [profile, setProfile] = useState(doctor);
  const schedules = work;
  const [leaves, setLeaves] = useState(leave);
  const [bio, setBio] = useState(doctor.bio || "");
  const [phone, setPhone] = useState(doctor.phone || "");
  const [editingProfessional, setEditingProfessional] = useState(false);
  const [editingPersonal, setEditingPersonal] = useState(false);
  const [pendingAvatar, setPendingAvatar] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState("");
  const [leaveStart, setLeaveStart] = useState("");
  const [leaveEnd, setLeaveEnd] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [feedbackScope, setFeedbackScope] = useState<FeedbackScope>("professional");

  const weekdaySchedule = useMemo(
    () => schedules.find(item => item.weekday === 1) || schedules[0],
    [schedules],
  );
  const configuredWorkdays = useMemo(
    () => CLINIC_WORKDAYS.filter(day => schedules.some(item => item.weekday === day)).length,
    [schedules],
  );
  const sortedLeaves = useMemo(
    () => [...leaves].sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime()),
    [leaves],
  );

  async function saveProfessional(event: FormEvent) {
    event.preventDefault();
    setFeedbackScope("professional");
    try {
      const updated = await request<Doctor>("/doctors/me", token, {
        method: "PATCH",
        body: JSON.stringify({
          fullName: profile.fullName,
          specialtyCode: profile.specialtyCode,
          experienceYears: profile.experienceYears,
          certificateNo: profile.certificateNo || null,
        }),
      });
      setProfile(updated);
      saved(updated);
      setEditingProfessional(false);
      setFeedback({ text: "Đã lưu thông tin chuyên môn.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  function cancelProfessionalEdit() {
    setProfile(current => ({
      ...current,
      fullName: doctor.fullName,
      specialtyCode: doctor.specialtyCode,
      experienceYears: doctor.experienceYears,
      certificateNo: doctor.certificateNo,
    }));
    setEditingProfessional(false);
    setFeedback(null);
  }

  async function savePersonal(event: FormEvent) {
    event.preventDefault();
    setFeedbackScope("bio");
    try {
      let updated = await request<Doctor>("/doctors/me/personal", token, {
        method: "PATCH",
        body: JSON.stringify({ phone: phone.trim(), bio }),
      });
      if (pendingAvatar) {
        const form = new FormData();
        form.append("image", pendingAvatar);
        updated = await request<Doctor>("/doctors/me/avatar", token, { method: "POST", body: form });
      }
      setProfile(updated);
      setPhone(updated.phone || "");
      setBio(updated.bio || "");
      saved(updated);
      setEditingPersonal(false);
      setPendingAvatar(null);
      setAvatarPreview("");
      setFeedback({ text: "Đã lưu thông tin cá nhân.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  function cancelPersonalEdit() {
    setPhone(profile.phone || "");
    setBio(profile.bio || "");
    setPendingAvatar(null);
    setAvatarPreview("");
    setEditingPersonal(false);
    setFeedback(null);
  }

  function chooseAvatar(file?: File) {
    if (!file) return;
    setFeedbackScope("overview");
    if (file.size > 2 * 1024 * 1024) {
      setFeedback({ text: "Ảnh đại diện tối đa 2 MB.", error: true });
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setAvatarPreview(String(reader.result || ""));
    reader.readAsDataURL(file);
    setPendingAvatar(file);
    setFeedback(null);
  }

  async function addLeave(event: FormEvent) {
    event.preventDefault();
    setFeedbackScope("leave");
    try {
      await request(`/doctors/${doctor.id}/leave`, token, {
        method: "POST",
        body: JSON.stringify({
          startAt: new Date(leaveStart).toISOString(),
          endAt: new Date(leaveEnd).toISOString(),
          reason: leaveReason || null,
        }),
      });
      const data = await request<{ leavePeriods: LeavePeriod[] }>("/doctors/me/schedule", token);
      setLeaves(data.leavePeriods);
      setLeaveStart("");
      setLeaveEnd("");
      setLeaveReason("");
      setFeedback({ text: "Đã gửi yêu cầu nghỉ. Lịch bệnh nhân chỉ đóng sau khi admin duyệt.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  async function removeLeave(id: string) {
    setFeedbackScope("leave");
    try {
      await request(`/doctors/${doctor.id}/leave/${id}`, token, { method: "DELETE" });
      setLeaves(current => current.filter(item => item.id !== id));
      setFeedback({ text: "Đã xóa ngày nghỉ.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  const displayName = /^bs\.?\s/i.test(profile.fullName) ? profile.fullName : `BS. ${profile.fullName}`;
  const renderFeedback = (scope: FeedbackScope) => feedback && feedbackScope === scope ? (
    <div className={`doctor-profile-feedback ${feedback.error ? "is-error" : "is-success"}`} role={feedback.error ? "alert" : "status"} aria-live={feedback.error ? "assertive" : "polite"}>
      {feedback.text}
    </div>
  ) : null;

  return (
    <main className="doctor-profile-page" aria-labelledby="doctor-profile-title">
      <section className="doctor-profile-overview" aria-label="Tóm tắt hồ sơ công khai">
        <div className="doctor-profile-identity">
          <label className={`doctor-profile-avatar-picker ${editingPersonal ? "is-editable" : "is-readonly"}`} aria-label={editingPersonal ? "Chọn ảnh đại diện mới" : "Ảnh đại diện bác sĩ"}>
            {avatarPreview || profile.avatarUrl
              ? <img src={avatarPreview || profile.avatarUrl} alt={`Ảnh đại diện của ${profile.fullName}`} />
              : <span aria-hidden="true">{initials(profile.fullName)}</span>}
            {editingPersonal && <b aria-hidden="true"><Camera /></b>}
            <input disabled={!editingPersonal} type="file" accept="image/jpeg,image/png,image/webp" onChange={event => chooseAvatar(event.target.files?.[0])} />
          </label>
          <div>
            <span className="doctor-profile-visibility"><BadgeCheck aria-hidden="true" /> Hồ sơ hiển thị với bệnh nhân</span>
            <h2 id="doctor-profile-title">{displayName}</h2>
            <p>{profile.specialtyCode || "Chưa cập nhật chuyên môn"}</p>
            <small>{editingPersonal ? "Chọn ảnh để thay đổi. JPG, PNG hoặc WebP, tối đa 2 MB." : "Thông tin hồ sơ bác sĩ tại DermAI Clinic."}</small>
          </div>
        </div>
        <dl className="doctor-profile-facts">
          <div><dt>Kinh nghiệm</dt><dd>{profile.experienceYears} năm</dd></div>
          <div><dt>Số chứng chỉ</dt><dd>{profile.certificateNo || "Chưa cập nhật"}</dd></div>
          <div><dt>Giá khám cơ bản</dt><dd>{formatFee(profile.consultationFee)}</dd><small>Do quản trị viên cấu hình</small></div>
        </dl>
        {renderFeedback("overview")}
      </section>

      <div className="doctor-profile-layout">
        <div className="doctor-profile-primary">
          <section className="doctor-profile-section" aria-labelledby="doctor-professional-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-professional-title">Thông tin chuyên môn và tài khoản</h2><p>Bác sĩ có thể cập nhật thông tin chuyên môn. Thông tin tài khoản vẫn được hệ thống quản lý.</p></div>
              {!editingProfessional && <button type="button" className="doctor-profile-secondary-button" onClick={() => { setFeedback(null); setEditingProfessional(true); }}><Pencil aria-hidden="true" /> Chỉnh sửa</button>}
            </header>
            {renderFeedback("professional")}
            {editingProfessional ? <form className="doctor-profile-form" onSubmit={saveProfessional}>
              <label>Họ và tên<input required maxLength={160} autoComplete="name" value={profile.fullName} onChange={event => setProfile({ ...profile, fullName: event.target.value })} /></label>
              <label>Chuyên khoa<input required maxLength={80} value={profile.specialtyCode} onChange={event => setProfile({ ...profile, specialtyCode: event.target.value })} /></label>
              <label>Số năm kinh nghiệm<input type="number" min="0" max="80" required value={profile.experienceYears} onChange={event => setProfile({ ...profile, experienceYears: Number(event.target.value) })} /></label>
              <label>Số chứng chỉ hành nghề<input maxLength={120} value={profile.certificateNo || ""} onChange={event => setProfile({ ...profile, certificateNo: event.target.value })} /></label>
              <div className="doctor-profile-form-actions doctor-profile-professional-actions">
                <small>Nhấn Lưu để cập nhật thông tin hiển thị với bệnh nhân.</small>
                <div className="doctor-profile-edit-actions"><button type="button" className="doctor-profile-secondary-button" onClick={cancelProfessionalEdit}><X aria-hidden="true" /> Hủy</button><button type="submit" className="doctor-profile-primary-button"><Save aria-hidden="true" /> Lưu</button></div>
              </div>
            </form> : <dl className="doctor-profile-readonly-grid">
              <div><dt>Họ và tên</dt><dd>{profile.fullName}</dd></div>
              <div><dt>Chuyên khoa</dt><dd>{profile.specialtyCode}</dd></div>
              <div><dt>Chức danh</dt><dd>Bác sĩ</dd></div>
              <div><dt>Kinh nghiệm</dt><dd>{profile.experienceYears} năm</dd></div>
              <div><dt>Số chứng chỉ hành nghề</dt><dd>{profile.certificateNo || "Chưa cập nhật"}</dd></div>
            </dl>}
          </section>

          <section className="doctor-profile-section" aria-labelledby="doctor-bio-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-bio-title">Thông tin cá nhân</h2><p>Bác sĩ có thể cập nhật ảnh đại diện, số điện thoại và phần giới thiệu ngắn.</p></div>
              {!editingPersonal && <button type="button" className="doctor-profile-secondary-button" onClick={() => { setFeedback(null); setEditingPersonal(true); }}><Pencil aria-hidden="true" /> Chỉnh sửa thông tin cá nhân</button>}
            </header>
            {renderFeedback("bio")}
            {editingPersonal ? <form className="doctor-profile-bio-form" onSubmit={savePersonal}>
              <label>Số điện thoại<input type="tel" minLength={8} maxLength={20} value={phone} onChange={event => setPhone(event.target.value)} placeholder="Ví dụ: 0352 790 904" /></label>
              <label htmlFor="doctor-profile-bio">Phần giới thiệu ngắn</label>
              <textarea id="doctor-profile-bio" maxLength={1200} value={bio} onChange={event => setBio(event.target.value)} placeholder="Ví dụ: Bác sĩ chuyên điều trị mụn, viêm da và các bệnh lý da liễu thường gặp." />
              <div className="doctor-profile-form-actions">
                <small>{bio.length}/1200 ký tự</small>
                <div className="doctor-profile-edit-actions"><button type="button" className="doctor-profile-secondary-button" onClick={cancelPersonalEdit}><X aria-hidden="true" /> Hủy</button><button type="submit" className="doctor-profile-primary-button"><Save aria-hidden="true" /> Lưu</button></div>
              </div>
            </form> : <dl className="doctor-profile-personal-view"><div><dt>Số điện thoại</dt><dd>{profile.phone || "Chưa cập nhật"}</dd></div><div><dt>Giới thiệu ngắn</dt><dd>{profile.bio || "Chưa có phần giới thiệu."}</dd></div></dl>}
          </section>
        </div>

        <aside className="doctor-profile-secondary" aria-label="Lịch làm việc và nghỉ phép">
          <section className="doctor-profile-section doctor-profile-schedule" aria-labelledby="doctor-schedule-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-schedule-title"><Clock3 aria-hidden="true" /> Lịch làm việc</h2></div>
            </header>
            <div className="doctor-profile-schedule-summary" role="status">
              <div><span>Ngày làm việc</span><strong>{configuredWorkdays === 6 ? "Thứ Hai - Thứ Bảy" : `${configuredWorkdays}/6 ngày đã cấu hình`}</strong></div>
              <div><span>Khung giờ hiện tại</span><strong>{weekdaySchedule ? `${weekdaySchedule.startTime.slice(0, 5)} - ${weekdaySchedule.endTime.slice(0, 5)}` : "Chưa thiết lập"}</strong></div>
            </div>
          </section>

          <section className="doctor-profile-section doctor-profile-leave" aria-labelledby="doctor-leave-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-leave-title"><CalendarOff aria-hidden="true" /> Nghỉ phép</h2><p>Yêu cầu nghỉ sẽ chờ admin duyệt trước khi khóa các khung giờ trên lịch bệnh nhân.</p></div>
            </header>
            {renderFeedback("leave")}
            {sortedLeaves.length > 0 ? (
              <div className="doctor-profile-leave-list" aria-label="Danh sách ngày nghỉ">
                {sortedLeaves.map(item => (
                  <article key={item.id}>
                    <div><strong>{formatDateTime(item.startAt)}</strong><span>Đến {formatDateTime(item.endAt)}</span><span className={`doctor-profile-leave-status is-${(item.status || "APPROVED").toLowerCase()}`}>{leaveStatusLabel(item.status)}</span><p>{item.reason || "Không ghi lý do"}</p>{item.reviewNote && <p>Ghi chú admin: {item.reviewNote}</p>}</div>
                    <button type="button" aria-label={`Xóa ngày nghỉ bắt đầu ${formatDateTime(item.startAt)}`} onClick={() => void removeLeave(item.id)}><Trash2 aria-hidden="true" /> Xóa</button>
                  </article>
                ))}
              </div>
            ) : (
              <div className="doctor-profile-empty" role="status"><CalendarOff aria-hidden="true" /><div><strong>Chưa có ngày nghỉ</strong><span>Thêm ngày nghỉ khi bạn không thể nhận lịch khám.</span></div></div>
            )}
            <form className="doctor-profile-leave-form" onSubmit={addLeave}>
              <label>Bắt đầu nghỉ<input type="datetime-local" required value={leaveStart} onChange={event => setLeaveStart(event.target.value)} /></label>
              <label>Kết thúc nghỉ<input type="datetime-local" required min={leaveStart || undefined} value={leaveEnd} onChange={event => setLeaveEnd(event.target.value)} /></label>
              <label>Lý do nghỉ<input maxLength={300} value={leaveReason} placeholder="Ví dụ: Nghỉ phép cá nhân" onChange={event => setLeaveReason(event.target.value)} /></label>
              <button type="submit" className="doctor-profile-secondary-button">Thêm ngày nghỉ</button>
            </form>
          </section>
        </aside>
      </div>
    </main>
  );
}
