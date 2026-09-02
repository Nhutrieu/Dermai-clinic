import { useEffect, useState } from "react";
import { CalendarClock, CheckCircle2, XCircle } from "lucide-react";
import { request } from "../../core/api";
import type { LeavePeriod } from "../../core/types";

type Props = { token: string };

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric", hour12: false,
  }).format(new Date(value));
}

export default function AdminLeaveRequests({ token }: Props) {
  const [items, setItems] = useState<LeavePeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setItems(await request<LeavePeriod[]>("/doctors/leave-requests", token));
      setError(false);
    } catch (cause) {
      setError(true);
      setMessage((cause as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [token]);

  async function decide(item: LeavePeriod, decision: "APPROVED" | "REJECTED") {
    if (!item.doctorId || busyId) return;
    setBusyId(item.id);
    setMessage("");
    setError(false);
    try {
      await request(`/doctors/${item.doctorId}/leave/${item.id}/approval`, token, {
        method: "PATCH",
        body: JSON.stringify({ decision }),
      });
      setItems(current => current.filter(candidate => candidate.id !== item.id));
      setMessage(decision === "APPROVED" ? "Đã duyệt yêu cầu nghỉ; lịch bệnh nhân sẽ được cập nhật." : "Đã từ chối yêu cầu nghỉ.");
    } catch (cause) {
      setError(true);
      setMessage((cause as Error).message);
    } finally {
      setBusyId("");
    }
  }

  return <section className="admin-leave-requests" aria-labelledby="admin-leave-requests-title">
    <header className="admin-leave-requests-heading">
      <div>
        <h3 id="admin-leave-requests-title"><CalendarClock aria-hidden="true" /> Yêu cầu nghỉ phép</h3>
        <p>Bác sĩ chỉ được nghỉ trên lịch bệnh nhân sau khi admin duyệt.</p>
      </div>
      <button type="button" className="admin-leave-refresh" onClick={() => void load()} disabled={loading || Boolean(busyId)}>Làm mới</button>
    </header>
    {message && <p className={`admin-leave-message ${error ? "is-error" : "is-success"}`} role={error ? "alert" : "status"}>{message}</p>}
    {loading ? <p className="admin-leave-empty">Đang tải yêu cầu...</p> : items.length === 0 ? <p className="admin-leave-empty">Không có yêu cầu đang chờ duyệt.</p> : (
      <div className="admin-leave-list">
        {items.map(item => (
          <article key={item.id}>
            <div className="admin-leave-copy">
              <strong>BS. {item.doctorName || "Chưa rõ bác sĩ"}</strong>
              <span>{formatDateTime(item.startAt)} – {formatDateTime(item.endAt)}</span>
              <p>{item.reason || "Không ghi lý do"}</p>
            </div>
            <div className="admin-leave-actions">
              <button type="button" className="admin-leave-approve" disabled={busyId !== ""} onClick={() => void decide(item, "APPROVED")}><CheckCircle2 aria-hidden="true" /> Duyệt</button>
              <button type="button" className="admin-leave-reject" disabled={busyId !== ""} onClick={() => void decide(item, "REJECTED")}><XCircle aria-hidden="true" /> Từ chối</button>
            </div>
          </article>
        ))}
      </div>
    )}
  </section>;
}