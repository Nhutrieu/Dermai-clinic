import { useEffect, useState } from "react";
import { Clock3 } from "lucide-react";
import { request } from "../../core/api";
import type { ClinicSchedule } from "../../core/clinicSchedule";

const DAY_NAMES = ["", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"];

type Props = { doctorId: string; doctorName: string; token: string };

export default function AdminDoctorScheduleEditor({ doctorId, doctorName, token }: Props) {
  const [schedule, setSchedule] = useState<ClinicSchedule | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setSchedule(null);setError("");
    request<ClinicSchedule>("/appointments/clinic-schedule/overview", token, { cache: "no-store" })
      .then(value => { if (active) setSchedule(value); })
      .catch(cause => { if (active) setError((cause as Error).message); });
    return () => { active = false; };
  }, [doctorId, token]);
  return <section className="admin-doctor-schedule" aria-labelledby={`doctor-schedule-${doctorId}`}>
    <header>
      <span><Clock3 aria-hidden="true" /></span>
      <div><h4 id={`doctor-schedule-${doctorId}`}>Lịch làm việc</h4><p>BS. {doctorName} dùng lịch chung được thiết lập tại mục Lịch phòng khám. Không cần lưu lại lịch riêng cho bác sĩ.</p></div>
    </header>
    {error ? <p role="alert" className="admin-doctor-schedule-feedback is-error">{error}</p>
      : !schedule ? <p role="status">Đang tải lịch phòng khám…</p>
      : schedule.configured ? <dl className="admin-clinic-workday-list">{schedule.days.map(day => <div key={day.weekday}><dt>{DAY_NAMES[day.weekday]}</dt><dd>{day.open ? `${day.startTime.slice(0, 5)}–${day.endTime.slice(0, 5)}` : "Nghỉ"}</dd></div>)}</dl>
      : <p>Admin hãy lưu lịch tại mục Lịch phòng khám để tự áp dụng cho tất cả bác sĩ. Trong lúc chưa thiết lập, hệ thống vẫn dùng lịch bác sĩ hiện có.</p>}
    <small>Nghỉ phép được duyệt và các lịch đã đặt sẽ tự chặn khung giờ tương ứng.</small>
  </section>;
}
