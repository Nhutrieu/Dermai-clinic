import { useEffect, useState, type FormEvent } from "react";
import { request } from "../../core/api";

type ClinicDay = { weekday: number; open: boolean; startTime: string; endTime: string };
const DAY_NAMES = ["", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"];

export default function AdminClinicSchedule({ token }: { token: string }) {
  const [days, setDays] = useState<ClinicDay[]>([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    setLoaded(false);setError(false);setMessage("");
    request<ClinicDay[]>("/appointments/clinic-schedule", token, { cache: "no-store" })
      .then(value => { if (active) { setDays(value);setLoaded(true); } })
      .catch(cause => { if (active) { setError(true); setMessage((cause as Error).message); } });
    return () => { active = false; };
  }, [token]);
  function update(weekday: number, patch: Partial<ClinicDay>) {
    setDays(current => current.map(day => day.weekday === weekday ? { ...day, ...patch } : day));
    setMessage("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();setMessage("");setError(false);
    const minutes = (time: string) => { const [hours, value] = time.split(":").map(Number); return hours * 60 + value; };
    if (days.some(day => minutes(day.endTime) - minutes(day.startTime) < 30)) {
      setError(true);setMessage("Giờ đóng cửa phải sau giờ mở cửa ít nhất 30 phút.");return;
    }
    setBusy(true);
    try {
      const saved = await request<ClinicDay[]>("/appointments/clinic-schedule", token, {
        method: "PUT", body: JSON.stringify(days),
      });
      setDays(saved);setMessage("Đã lưu và áp dụng lịch phòng khám cho tất cả bác sĩ.");
    } catch (cause) { setError(true);setMessage((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="panel management clinic-closure-panel clinic-schedule-panel" aria-labelledby="clinic-schedule-title">
    <h2 id="clinic-schedule-title">Lịch hoạt động phòng khám</h2>
    {!loaded && !error && <p role="status">Đang tải lịch hoạt động…</p>}
    <form onSubmit={save} className="clinic-week-form">
      <fieldset disabled={!loaded || busy}>
        <legend>Lịch hằng tuần</legend>
        {days.map(day => <div className="clinic-week-row" key={day.weekday}>
          <label className="clinic-week-toggle"><input type="checkbox" checked={day.open} onChange={event => update(day.weekday, { open: event.target.checked })} />{DAY_NAMES[day.weekday]}</label>
          <label>Mở cửa<input type="time" required disabled={!day.open} aria-label={`Giờ mở cửa ${DAY_NAMES[day.weekday]}`} value={day.startTime.slice(0, 5)} onChange={event => update(day.weekday, { startTime: event.target.value })} /></label>
          <label>Đóng cửa<input type="time" required disabled={!day.open} aria-label={`Giờ đóng cửa ${DAY_NAMES[day.weekday]}`} value={day.endTime.slice(0, 5)} onChange={event => update(day.weekday, { endTime: event.target.value })} /></label>
        </div>)}
        <button type="submit" className="primary">{busy ? "Đang lưu…" : "Lưu lịch phòng khám"}</button>
      </fieldset>
    </form>
    <small>Chỉ admin được thay đổi. Nếu giờ mới ảnh hưởng lịch khám đang hoạt động, hãy đổi hoặc hủy những lịch đó trước.</small>
    {message && <p className={`clinic-closure-message${error ? " is-error" : ""}`} role={error ? "alert" : "status"}>{message}</p>}
  </section>;
}
