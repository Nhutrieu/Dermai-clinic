import { FormEvent, useEffect, useState } from "react";
import { Clock3 } from "lucide-react";
import { request } from "../../core/api";
import type { WorkSchedule } from "../../core/types";

type SchedulingDoctor = {
  id: string;
  workSchedules: WorkSchedule[];
};

type Props = {
  doctorId: string;
  doctorName: string;
  token: string;
};

const WORKDAYS = [1, 2, 3, 4, 5, 6];

export default function AdminDoctorScheduleEditor({ doctorId, doctorName, token }: Props) {
  const [startTime, setStartTime] = useState("08:00");
  const [endTime, setEndTime] = useState("17:00");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setMessage("");
    setError("");
    request<SchedulingDoctor[]>("/doctors/scheduling-data", token)
      .then(items => {
        if (!active) return;
        const schedules = items.find(item => item.id === doctorId)?.workSchedules || [];
        const weekday = schedules.find(item => item.weekday === 1) || schedules[0];
        setStartTime(weekday?.startTime.slice(0, 5) || "08:00");
        setEndTime(weekday?.endTime.slice(0, 5) || "17:00");
      })
      .catch(reason => {
        if (active) setError((reason as Error).message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [doctorId, token]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await request<WorkSchedule[]>(`/doctors/${doctorId}/schedule`, token, {
        method: "PUT",
        body: JSON.stringify(WORKDAYS.map(weekday => ({
          weekday,
          startTime,
          endTime,
          slotMinutes: 30,
        }))),
      });
      setMessage(`Đã cập nhật giờ làm việc của BS. ${doctorName}.`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="admin-doctor-schedule" aria-labelledby={`doctor-schedule-${doctorId}`}>
      <header>
        <span><Clock3 aria-hidden="true" /></span>
        <div>
          <h4 id={`doctor-schedule-${doctorId}`}>Lịch làm việc</h4>
          <p>Áp dụng từ Thứ Hai đến Thứ Bảy. Hệ thống tự chia thành các lượt 30 phút.</p>
        </div>
      </header>
      {loading ? <p className="admin-doctor-schedule-loading" role="status">Đang tải lịch làm việc…</p> : (
        <form onSubmit={save}>
          <label>
            Bắt đầu
            <input type="time" required value={startTime} onChange={event => setStartTime(event.target.value)} />
          </label>
          <label>
            Kết thúc
            <input type="time" required value={endTime} onChange={event => setEndTime(event.target.value)} />
          </label>
          <button type="submit" className="primary" disabled={busy || startTime >= endTime}>
            {busy ? "Đang lưu…" : "Lưu giờ làm việc"}
          </button>
        </form>
      )}
      <small>Chỉ quản trị viên có thể thay đổi. Các lịch đang hoạt động luôn được kiểm tra trước khi lưu.</small>
      {error && <p className="admin-doctor-schedule-feedback is-error" role="alert">{error}</p>}
      {message && <p className="admin-doctor-schedule-feedback is-success" role="status" aria-live="polite">{message}</p>}
    </section>
  );
}
