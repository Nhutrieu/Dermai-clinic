import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ClockAlert } from "lucide-react";
import { ApiError, request } from "../../core/api";
import { isStaleInProgressAppointment } from "../../core/appointmentPolicy";
import { subscribeRealtime } from "../../core/realtime";
import type { Appointment, Doctor, Patient } from "../../core/types";

type Props = {
  token: string;
  appointments: Appointment[];
  doctors: Doctor[];
  patients: Patient[];
  refresh: () => Promise<void>;
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
    hour12: false,
  }).format(new Date(value));
}

export default function AdminStaleConsultations({ token, appointments, doctors, patients, refresh }: Props) {
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const [now, setNow] = useState(Date.now());
  const stale = useMemo(
    () => appointments
      .filter(item => isStaleInProgressAppointment(item, now))
      .sort((left, right) => new Date(left.endAt).getTime() - new Date(right.endAt).getTime()),
    [appointments, now],
  );

  useEffect(() => {
    // Keep admin oversight aligned with doctor and reception updates.
    const unsubscribe = subscribeRealtime(event => {
      if (event.type === "SLOTS_CHANGED") void refresh();
    });
    return unsubscribe;
  }, [refresh]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  async function complete(appointmentId: string) {
    setBusyId(appointmentId);
    setMessage("");
    setError(false);
    try {
      await request(`/appointments/${appointmentId}/complete`, token, { method: "POST" });
      setMessage("Đã cập nhật lượt khám là hoàn tất.");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409 && cause.code === "INVALID_TRANSITION") {
        setMessage("Lịch này đã được người khác cập nhật. Danh sách vừa được làm mới.");
      } else {
        setMessage((cause as Error).message || "Không thể cập nhật lượt khám.");
        setError(true);
      }
    } finally {
      await refresh().catch(() => undefined);
      setBusyId("");
    }
  }

  if (!stale.length) return null;

  return (
    <section className="panel admin-stale-consultations" aria-labelledby="admin-stale-title">
      <header>
        <div>
          <ClockAlert aria-hidden="true" />
          <div><h2 id="admin-stale-title">Lượt khám cần cập nhật</h2><p>Ca đã quá giờ kết thúc trên 60 phút nhưng vẫn ở trạng thái đang khám.</p></div>
        </div>
        <span>{stale.length}</span>
      </header>
      {message && <p className={error ? "is-error" : "is-success"} role={error ? "alert" : "status"}>{message}</p>}
      <div className="admin-stale-list">
        {stale.map(appointment => {
          const patient = patients.find(item => item.id === appointment.patientId);
          const doctor = doctors.find(item => item.id === appointment.doctorId);
          return (
            <article key={appointment.id}>
              <div>
                <strong>{patient?.fullName || "Bệnh nhân chưa tải thông tin"}</strong>
                <span>BS. {doctor?.fullName || appointment.doctorName || "Chưa xác định"}</span>
              </div>
              <time dateTime={appointment.endAt}>Kết thúc dự kiến {formatDateTime(appointment.endAt)}</time>
              <button type="button" disabled={busyId === appointment.id} onClick={() => void complete(appointment.id)}>
                <CheckCircle2 aria-hidden="true" /> {busyId === appointment.id ? "Đang cập nhật..." : "Hoàn tất lượt khám"}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
