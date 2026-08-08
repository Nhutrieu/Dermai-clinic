import { FormEvent, useEffect, useMemo, useState } from "react";
import { BadgeCheck, CalendarOff, Camera, Clock3, Save, Trash2 } from "lucide-react";
import { request } from "../../core/api";
import type { Doctor, LeavePeriod, WorkSchedule } from "../../core/types";

type Props = {
  token: string;
  doctor: Doctor;
  work: WorkSchedule[];
  leave: LeavePeriod[];
  saved: (doctor: Doctor) => void;
};

type Feedback = { text: string; error: boolean };
const CLINIC_WORKDAYS = [1, 2, 3, 4, 5];

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

export default function DoctorProfileScreen({ token, doctor, work, leave, saved }: Props) {
  const savedWeekday = work.find(item => item.weekday === 1) || work[0];
  const [profile, setProfile] = useState(doctor);
  const [schedules, setSchedules] = useState(work);
  const [leaves, setLeaves] = useState(leave);
  const [bio, setBio] = useState(doctor.bio || "");
  const [startTime, setStartTime] = useState(savedWeekday?.startTime.slice(0, 5) || "08:00");
  const [endTime, setEndTime] = useState(savedWeekday?.endTime.slice(0, 5) || "17:00");
  const [slotMinutes, setSlotMinutes] = useState(savedWeekday?.slotMinutes || 30);
  const [leaveStart, setLeaveStart] = useState("");
  const [leaveEnd, setLeaveEnd] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  // Preserve the existing delayed save so profile data remains synced across patient views.
  useEffect(() => {
    if (
      profile.fullName === doctor.fullName
      && profile.specialtyCode === doctor.specialtyCode
      && profile.experienceYears === doctor.experienceYears
      && profile.certificateNo === doctor.certificateNo
    ) return;

    const timer = window.setTimeout(async () => {
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
        setFeedback({ text: "Đã tự động lưu thông tin chuyên môn.", error: false });
      } catch (cause) {
        setFeedback({ text: (cause as Error).message, error: true });
      }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [
    doctor.certificateNo,
    doctor.experienceYears,
    doctor.fullName,
    doctor.specialtyCode,
    profile.certificateNo,
    profile.experienceYears,
    profile.fullName,
    profile.specialtyCode,
    saved,
    token,
  ]);

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

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
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
      setFeedback({ text: "Đã lưu thông tin chuyên môn.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  async function chooseAvatar(file?: File) {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setFeedback({ text: "Ảnh đại diện tối đa 2 MB.", error: true });
      return;
    }
    const form = new FormData();
    form.append("image", file);
    try {
      const updated = await request<Doctor>("/doctors/me/avatar", token, { method: "POST", body: form });
      setProfile(updated);
      saved(updated);
      setFeedback({ text: "Đã cập nhật ảnh đại diện.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  async function saveBio(event: FormEvent) {
    event.preventDefault();
    try {
      const updated = await request<Doctor>("/doctors/me/bio", token, {
        method: "PATCH",
        body: JSON.stringify({ bio }),
      });
      setProfile(updated);
      saved(updated);
      setFeedback({ text: "Đã lưu phần giới thiệu bác sĩ.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  async function saveWeeklySchedule(event: FormEvent) {
    event.preventDefault();
    try {
      const weekly = CLINIC_WORKDAYS.map(day => ({ id: "", weekday: day, startTime, endTime, slotMinutes }));
      const body = weekly.map(item => ({
        weekday: item.weekday,
        startTime: item.startTime,
        endTime: item.endTime,
        slotMinutes: item.slotMinutes,
      }));
      const updated = await request<WorkSchedule[]>(`/doctors/${doctor.id}/schedule`, token, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setSchedules(updated);
      setFeedback({
        text: `Đã lưu giờ làm việc ${startTime} - ${endTime}, mỗi lượt ${slotMinutes} phút, từ Thứ Hai đến Thứ Sáu.`,
        error: false,
      });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  async function addLeave(event: FormEvent) {
    event.preventDefault();
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
      setFeedback({ text: "Đã thêm ngày nghỉ và đóng các khung giờ liên quan.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  async function removeLeave(id: string) {
    try {
      await request(`/doctors/${doctor.id}/leave/${id}`, token, { method: "DELETE" });
      setLeaves(current => current.filter(item => item.id !== id));
      setFeedback({ text: "Đã xóa ngày nghỉ.", error: false });
    } catch (cause) {
      setFeedback({ text: (cause as Error).message, error: true });
    }
  }

  const displayName = /^bs\.?\s/i.test(profile.fullName) ? profile.fullName : `BS. ${profile.fullName}`;

  return (
    <main className="doctor-profile-page" aria-labelledby="doctor-profile-title">
      <section className="doctor-profile-overview" aria-label="Tóm tắt hồ sơ công khai">
        <div className="doctor-profile-identity">
          <label className="doctor-profile-avatar-picker" aria-label="Chọn ảnh đại diện mới">
            {profile.avatarUrl
              ? <img src={profile.avatarUrl} alt={`Ảnh đại diện của ${profile.fullName}`} />
              : <span aria-hidden="true">{initials(profile.fullName)}</span>}
            <b aria-hidden="true"><Camera /></b>
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => void chooseAvatar(event.target.files?.[0])} />
          </label>
          <div>
            <span className="doctor-profile-visibility"><BadgeCheck aria-hidden="true" /> Hồ sơ hiển thị với bệnh nhân</span>
            <h2 id="doctor-profile-title">{displayName}</h2>
            <p>{profile.specialtyCode || "Chưa cập nhật chuyên môn"}</p>
            <small>Chọn ảnh để thay đổi. JPG, PNG hoặc WebP, tối đa 2 MB.</small>
          </div>
        </div>
        <dl className="doctor-profile-facts">
          <div><dt>Kinh nghiệm</dt><dd>{profile.experienceYears} năm</dd></div>
          <div><dt>Số chứng chỉ</dt><dd>{profile.certificateNo || "Chưa cập nhật"}</dd></div>
          <div><dt>Giá khám cơ bản</dt><dd>{formatFee(profile.consultationFee)}</dd><small>Do quản trị viên cấu hình</small></div>
        </dl>
      </section>

      {feedback && (
        <div className={`doctor-profile-feedback ${feedback.error ? "is-error" : "is-success"}`} role={feedback.error ? "alert" : "status"} aria-live={feedback.error ? "assertive" : "polite"}>
          {feedback.text}
        </div>
      )}

      <div className="doctor-profile-layout">
        <div className="doctor-profile-primary">
          <section className="doctor-profile-section" aria-labelledby="doctor-professional-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-professional-title">Thông tin chuyên môn</h2><p>Nội dung này xuất hiện trong danh sách bác sĩ và khi bệnh nhân đặt lịch.</p></div>
              <span>Đang bật tự động lưu</span>
            </header>
            <form className="doctor-profile-form" onSubmit={saveProfile}>
              <label>Họ và tên<input required maxLength={160} autoComplete="name" value={profile.fullName} onChange={event => setProfile({ ...profile, fullName: event.target.value })} /></label>
              <label>Chuyên môn<input required maxLength={80} value={profile.specialtyCode} onChange={event => setProfile({ ...profile, specialtyCode: event.target.value })} /></label>
              <label>Số năm kinh nghiệm<input type="number" min="0" max="80" required value={profile.experienceYears} onChange={event => setProfile({ ...profile, experienceYears: Number(event.target.value) })} /></label>
              <label>Số chứng chỉ hành nghề<input maxLength={120} value={profile.certificateNo || ""} onChange={event => setProfile({ ...profile, certificateNo: event.target.value })} /></label>
              <div className="doctor-profile-form-actions">
                <small>Nhấn lưu để cập nhật ngay thay vì chờ tự động lưu.</small>
                <button type="submit" className="doctor-profile-primary-button"><Save aria-hidden="true" /> Lưu thay đổi</button>
              </div>
            </form>
          </section>

          <section className="doctor-profile-section" aria-labelledby="doctor-bio-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-bio-title">Giới thiệu với bệnh nhân</h2><p>Nêu kinh nghiệm, thế mạnh điều trị và cách tiếp cận chuyên môn.</p></div>
            </header>
            <form className="doctor-profile-bio-form" onSubmit={saveBio}>
              <label htmlFor="doctor-profile-bio">Mô tả bác sĩ</label>
              <textarea id="doctor-profile-bio" maxLength={1200} value={bio} onChange={event => setBio(event.target.value)} placeholder="Ví dụ: Bác sĩ chuyên điều trị mụn, viêm da và các bệnh lý da liễu thường gặp." />
              <div className="doctor-profile-form-actions">
                <small>{bio.length}/1200 ký tự</small>
                <button type="submit" className="doctor-profile-primary-button"><Save aria-hidden="true" /> Lưu giới thiệu</button>
              </div>
            </form>
          </section>
        </div>

        <aside className="doctor-profile-secondary" aria-label="Lịch làm việc và nghỉ phép">
          <section className="doctor-profile-section doctor-profile-schedule" aria-labelledby="doctor-schedule-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-schedule-title"><Clock3 aria-hidden="true" /> Lịch làm việc</h2><p>Thiết lập một khung giờ chung cho các ngày trong tuần.</p></div>
            </header>
            <div className="doctor-profile-schedule-summary" role="status">
              <div><span>Ngày làm việc</span><strong>{configuredWorkdays === 5 ? "Thứ Hai - Thứ Sáu" : `${configuredWorkdays}/5 ngày đã cấu hình`}</strong></div>
              <div><span>Khung giờ hiện tại</span><strong>{weekdaySchedule ? `${weekdaySchedule.startTime.slice(0, 5)} - ${weekdaySchedule.endTime.slice(0, 5)}` : "Chưa thiết lập"}</strong></div>
              <div><span>Thời lượng mỗi lượt</span><strong>{weekdaySchedule ? `${weekdaySchedule.slotMinutes} phút` : "Chưa thiết lập"}</strong></div>
            </div>
            <form className="doctor-profile-schedule-form" onSubmit={saveWeeklySchedule}>
              <label>Bắt đầu<input type="time" required value={startTime} onChange={event => setStartTime(event.target.value)} /></label>
              <label>Kết thúc<input type="time" required value={endTime} onChange={event => setEndTime(event.target.value)} /></label>
              <label className="doctor-profile-slot-field">Thời lượng mỗi lượt khám<div className="doctor-profile-number-control"><input type="number" min="10" max="120" required value={slotMinutes} onChange={event => setSlotMinutes(Number(event.target.value))} /><span>phút</span></div></label>
              <p className="doctor-profile-helper">Giờ nghỉ trưa 12:00 - 13:00 được hệ thống áp dụng tự động.</p>
              <button type="submit" className="doctor-profile-primary-button">Lưu giờ làm việc</button>
            </form>
          </section>

          <section className="doctor-profile-section doctor-profile-leave" aria-labelledby="doctor-leave-title">
            <header className="doctor-profile-section-heading">
              <div><h2 id="doctor-leave-title"><CalendarOff aria-hidden="true" /> Nghỉ phép</h2><p>Các khung giờ trùng ngày nghỉ sẽ không cho bệnh nhân đặt lịch.</p></div>
            </header>
            {sortedLeaves.length > 0 ? (
              <div className="doctor-profile-leave-list" aria-label="Danh sách ngày nghỉ">
                {sortedLeaves.map(item => (
                  <article key={item.id}>
                    <div><strong>{formatDateTime(item.startAt)}</strong><span>Đến {formatDateTime(item.endAt)}</span><p>{item.reason || "Không ghi lý do"}</p></div>
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
