import { FormEvent, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { request } from "../../core/api";
import { subscribeRealtime, type RealtimeConnectionState } from "../../core/realtime";
import type { Appointment, Doctor, Patient, Recommendation, RecommendationResult, ReminderAction, ReminderItem } from "../../core/types";
import { State } from "../../components/Ui";
import ReceptionAppointmentRequests from "./ReceptionAppointmentRequests";
import ReceptionAcceptedAppointments from "./ReceptionAcceptedAppointments";
import {
    APPOINTMENT_ALREADY_HANDLED_MESSAGE,
    isAppointmentAlreadyHandledError,
} from "./receptionBookingModel";
type PatientPage = { content: Patient[]; totalElements: number };
function formatAppointmentTime(iso: string) {
    if (!iso) return "";
    const d = new Date(iso);
    const time = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
    const date = d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
    return `${time} · ${date}`;
}

function getStatusBadge(status: string) {
    switch (status) {
        case "PENDING": return { label: "Chờ tiếp nhận", badgeClass: "badge-pending" };
        case "ASSIGNED": return { label: "Đã xếp bác sĩ", badgeClass: "badge-assigned" };
        case "CONFIRMED": return { label: "Đã xác nhận", badgeClass: "badge-confirmed" };
        case "CHECKED_IN": return { label: "Đã đến phòng khám", badgeClass: "badge-confirmed" };
        case "IN_PROGRESS": return { label: "Đang khám", badgeClass: "badge-in-progress" };
        case "COMPLETED": return { label: "Đã hoàn thành", badgeClass: "badge-completed" };
        case "CANCELLED": return { label: "Đã hủy", badgeClass: "badge-cancelled" };
        case "FOLLOW_UP_REQUIRED": return { label: "Yêu cầu tái khám", badgeClass: "badge-followup" };
        default: return { label: status, badgeClass: "badge-default" };
    }
}

export default function ReceptionPanel({ token, tab }: { token: string; tab: string }) {
    const [query, setQuery] = useState(""); const [patients, setPatients] = useState<Patient[]>([]); const [doctors, setDoctors] = useState<Doctor[]>([]); const [queue, setQueue] = useState<Appointment[]>([]); const [reminders, setReminders] = useState<ReminderItem[]>([]); const [recommendations, setRecommendations] = useState<Recommendation[]>([]); const [recommendFor, setRecommendFor] = useState(""); const [patientId, setPatientId] = useState(""); const [message, setMessage] = useState("");
    const [messageError, setMessageError] = useState(false);
    const [queueLoading, setQueueLoading] = useState(true);
    const [queueRefreshing, setQueueRefreshing] = useState(false);
    const [queueError, setQueueError] = useState("");
    const [reminderLoading, setReminderLoading] = useState(true);
    const [reminderError, setReminderError] = useState("");
    const [patientLoadWarning, setPatientLoadWarning] = useState("");
    const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
    const [realtimeState, setRealtimeState] = useState<RealtimeConnectionState>("connecting");
    const [busyAppointmentId, setBusyAppointmentId] = useState("");
    const realtimeRefreshTimer = useRef<number | null>(null);
    const rescheduleIdempotencyKeys = useRef(new Map<string, string>());
    async function loadQueue(showLoading = false, showRefreshing = false) {
        if (showLoading) setQueueLoading(true);
        if (showRefreshing) setQueueRefreshing(true);
        try {
            setQueueError("");
            const from = new Date();
            // Keep enough accepted-history data for reception to review completed,
            // cancelled and no-show visits instead of hiding them after one day.
            from.setDate(from.getDate() - 90);
            const to = new Date();
            to.setDate(to.getDate() + 60);
            const items = await request<Appointment[]>(`/appointments/queue?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token);
            setQueue(items);
            setLastUpdatedAt(new Date());

            // A missing patient profile must not hide the booking request itself.
            const ids = [...new Set(items.map(item => item.patientId))];
            const loaded = await Promise.allSettled(ids.map(id => request<Patient>(`/patients/${id}`, token)));
            const available = loaded
                .filter((result): result is PromiseFulfilledResult<Patient> => result.status === "fulfilled")
                .map(result => result.value);
            const missingCount = loaded.length - available.length;
            setPatients(current => [...new Map([...current, ...available].map(item => [item.id, item])).values()]);
            setPatientLoadWarning(missingCount ? `Chưa tải được ${missingCount} hồ sơ bệnh nhân. Yêu cầu vẫn được giữ trong danh sách.` : "");
        } catch (cause) {
            setQueueError((cause as Error).message);
        } finally {
            setQueueLoading(false);
            setQueueRefreshing(false);
        }
    }
    async function search(q?: string) {
        const searchTerm = (q !== undefined ? q : query).trim();
        try {
            setMessage("");
            setMessageError(false);
            const page = await request<PatientPage>(`/patients?query=${encodeURIComponent(searchTerm)}`, token);
            setPatients(page.content || []);
        } catch (x) {
            setMessage((x as Error).message);
            setMessageError(true);
        }
    }
    async function loadReminders(showLoading = false) {
        if (showLoading) setReminderLoading(true);
        try {
            setReminderError("");
            setReminders(await request<ReminderItem[]>("/appointments/reminders", token));
        } catch (cause) {
            setReminderError((cause as Error).message);
        } finally {
            setReminderLoading(false);
        }
    }
    async function loadDoctors() { setDoctors(await request<Doctor[]>("/doctors", token)) }
    useEffect(() => {
        void loadDoctors().catch(() => undefined);
        void loadQueue(true);
        void loadReminders(true);
    }, []);
    useEffect(() => { const refresh = () => { void loadDoctors().catch(() => undefined) }; window.addEventListener("doctor-profiles-changed", refresh); return () => window.removeEventListener("doctor-profiles-changed", refresh) }, [token]);
    useEffect(() => { const refresh = () => { void loadQueue(); void loadReminders(); }; window.addEventListener("reception-appointments-changed", refresh); return () => window.removeEventListener("reception-appointments-changed", refresh) }, []);
    useEffect(() => {
        // A patient hold and confirmation can emit close events; debounce them into one queue refresh.
        const refreshQueue = () => {
            void loadQueue();
            void loadReminders();
        };
        const scheduleRefresh = () => {
            if (realtimeRefreshTimer.current !== null) window.clearTimeout(realtimeRefreshTimer.current);
            realtimeRefreshTimer.current = window.setTimeout(() => {
                realtimeRefreshTimer.current = null;
                refreshQueue();
            }, 150);
        };
        const unsubscribe = subscribeRealtime(event => {
            if (event.type !== "SLOTS_CHANGED") return;
            scheduleRefresh();
        }, { onConnectionChange: setRealtimeState });
        // Recover a missed WebSocket frame after sleep, network changes or a background browser tab.
        const fallback = window.setInterval(refreshQueue, 5_000);
        window.addEventListener("focus", scheduleRefresh);
        return () => {
            unsubscribe();
            window.clearInterval(fallback);
            window.removeEventListener("focus", scheduleRefresh);
            if (realtimeRefreshTimer.current !== null) window.clearTimeout(realtimeRefreshTimer.current);
        };
    }, [token]);
    useEffect(() => { if(patientId)sessionStorage.setItem("reception-support-patient",patients.find(p=>p.id===patientId)?.identityId||"") }, [patientId,patients]);
    async function confirm(id: string) {
        setBusyAppointmentId(id);
        setMessage("");
        setMessageError(false);
        try {
            await request(`/appointments/${id}/confirm`, token, { method: "POST" });
            setMessage("Đã xác nhận lịch và chuyển sang danh sách lịch đã nhận.");
            await Promise.all([loadQueue(), loadReminders()]);
        } catch (x) {
            if (isAppointmentAlreadyHandledError(x)) {
                setMessage(APPOINTMENT_ALREADY_HANDLED_MESSAGE);
                setMessageError(false);
                await Promise.all([loadQueue(), loadReminders()]);
            } else {
                setMessage((x as Error).message);
                setMessageError(true);
            }
        } finally {
            setBusyAppointmentId("");
        }
    }
    async function cancel(id: string, cancelReason: string) {
        try {
            const updated = await request<Appointment>(`/appointments/${id}/cancel`, token, {
                method: "POST",
                body: JSON.stringify({ reason: cancelReason.trim() })
            });
            setMessage("Đã hủy lịch và cập nhật danh sách vận hành.");
            setMessageError(false);
            await Promise.all([loadQueue(), loadReminders()]);
            window.dispatchEvent(new Event("reception-appointments-changed"));
            return updated;
        } catch (x) {
            setMessage((x as Error).message);
            setMessageError(true);
            throw x;
        }
    }
    async function noShow(id: string) {
        setBusyAppointmentId(id);
        setMessageError(false);
        try {
            await request(`/appointments/${id}/no-show`, token, { method: "POST" });
            setMessage("Đã ghi nhận bệnh nhân không đến khám.");
            await Promise.all([loadQueue(), loadReminders()]);
        } catch (x) {
            setMessage((x as Error).message);
            setMessageError(true);
        } finally {
            setBusyAppointmentId("");
        }
    }
    async function checkIn(id: string) {
        setBusyAppointmentId(id);
        setMessageError(false);
        try {
            await request(`/appointments/${id}/check-in`, token, { method: "POST" });
            setMessage("Đã xác nhận bệnh nhân có mặt và chuyển sang chờ khám.");
            await Promise.all([loadQueue(), loadReminders()]);
        } catch (x) {
            setMessage((x as Error).message);
            setMessageError(true);
            throw x;
        } finally {
            setBusyAppointmentId("");
        }
    }
    async function remind(id: string, action: ReminderAction["actionType"]) {
        setBusyAppointmentId(id);
        setMessageError(false);
        try {
            await request(`/appointments/${id}/reminder-actions`, token, { method: "POST", body: JSON.stringify({ action }) });
            setMessage(action === "CALLED" ? "Đã lưu trạng thái gọi xác nhận." : action === "RESENT" ? "Đã gửi thông báo nhắc lại cho bệnh nhân." : "Đã lưu trạng thái không liên hệ được.");
            await loadReminders();
        } catch (x) {
            setMessage((x as Error).message);
            setMessageError(true);
        } finally {
            setBusyAppointmentId("");
        }
    }
    async function recommend(x: Appointment) {
        setBusyAppointmentId(x.id);
        setMessage("");
        setMessageError(false);
        try {
            const result = await request<RecommendationResult>("/appointments/recommendations", token, { method: "POST", body: JSON.stringify({ patientId: x.patientId, preferredStart: x.startAt, durationMinutes: Math.round((new Date(x.endAt).getTime() - new Date(x.startAt).getTime()) / 60000), limit: 5 }) });
            setRecommendFor(x.id);
            setRecommendations(result.items);
            setMessage(result.items.length ? "Đã tìm thấy các lịch có thể phân công." : "Không có khung giờ phù hợp trong 7 ngày.");
        } catch (e) {
            setMessage((e as Error).message);
            setMessageError(true);
        } finally {
            setBusyAppointmentId("");
        }
    }
    async function assign(id: string, slot: Recommendation) {
        setBusyAppointmentId(id);
        setMessage("");
        setMessageError(false);
        try {
            await request(`/appointments/${id}/assign`, token, { method: "POST", body: JSON.stringify({ doctorId: slot.doctorId, doctorIdentityId: slot.doctorIdentityId, startAt: slot.startAt, endAt: slot.endAt }) });
            setRecommendations([]);
            setRecommendFor("");
            setMessage("Đã phân công bác sĩ và khung giờ cho yêu cầu.");
            await loadQueue();
        } catch (x) {
            setMessage((x as Error).message);
            setMessageError(true);
        } finally {
            setBusyAppointmentId("");
        }
    }
    async function reschedule(id: string, value: string, idempotencyKey?: string) {
        // Keep one key stable for retries of the same appointment and target slot.
        const attempt = `${id}:${value}`;
        const stableKey = idempotencyKey ?? rescheduleIdempotencyKeys.current.get(attempt) ?? crypto.randomUUID();
        rescheduleIdempotencyKeys.current.set(attempt, stableKey);
        const from = new Date(value);
        try {
            const updated = await request<Appointment>(`/appointments/${id}/reschedule`, token, {
                method: "POST",
                headers: { "Idempotency-Key": stableKey },
                body: JSON.stringify({
                    startAt: from.toISOString(),
                    endAt: new Date(from.getTime() + 30 * 60000).toISOString()
                })
            });
            setMessage("Đã đổi lịch và giữ nguyên lý do khám ban đầu.");
            await Promise.all([loadQueue(), loadReminders()]);
            window.dispatchEvent(new Event("reception-appointments-changed"));
            return updated;
        } catch (x) {
            setMessage((x as Error).message);
            throw x;
        }
    }
    const patientName = (x: Appointment) => patients.find(p => p.id === x.patientId)?.fullName || x.patientId;
    const doctorName = (x: Appointment) => x.doctorId ? doctors.find(d => d.id === x.doctorId)?.fullName || "Bác sĩ đã chọn" : "Chưa chọn bác sĩ";

    function openSupport(patient: Patient) {
        sessionStorage.setItem("reception-support-patient", patient.identityId);
        window.dispatchEvent(new Event("open-support-chat"));
    }

    if (tab === "profile") { const selectedPatient=patients.find(p=>p.id===patientId);const patientAppointments=queue.filter(x=>x.patientId===patientId).sort((a,b)=>new Date(b.startAt).getTime()-new Date(a.startAt).getTime());return <section className="panel management"><h2>Tra cứu bệnh nhân</h2><p>Chọn bệnh nhân để xem thông tin xác minh và hỗ trợ lịch khám.</p>{message && <p className="booking-message">{message}</p>}<div className="inline"><input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();search();}}} placeholder="Nhập họ tên hoặc số điện thoại" /><button type="button" onClick={() => search()}>Tìm</button></div><div className="patient-search-layout"><div className="patient-search-results">{patients.length===0?<State text="Không tìm thấy bệnh nhân."/>:patients.map(p => <button className={`result ${patientId===p.id?"selected":""}`} key={p.id} onClick={() => setPatientId(p.id)}><b>{p.fullName}</b><small>{p.phone||"Chưa có số điện thoại"}</small></button>)}</div>{selectedPatient&&<article className="reception-patient-detail"><header><div><small>THÔNG TIN BỆNH NHÂN</small><h3>{selectedPatient.fullName}</h3></div><button onClick={()=>setPatientId("")}><X/></button></header><dl><dt>Số điện thoại</dt><dd>{selectedPatient.phone||"Chưa khai báo"}</dd><dt>Ngày sinh</dt><dd>{selectedPatient.dob?new Date(selectedPatient.dob).toLocaleDateString("vi-VN"):"Chưa khai báo"}</dd></dl><div className="patient-recent"><b>Lịch khám gần đây</b>{patientAppointments.length===0?<p>Chưa có lịch trong phạm vi tra cứu.</p>:patientAppointments.slice(0,3).map(x=><p key={x.id}>{formatAppointmentTime(x.startAt)} · {doctorName(x)} · {getStatusBadge(x.status).label}</p>)}</div><button className="primary" onClick={()=>window.dispatchEvent(new Event("open-support-chat"))}>Mở chat hỗ trợ</button></article>}</div></section>}
    if (tab === "appointments") return <ReceptionAppointmentRequests
        requests={queue}
        patients={patients}
        doctors={doctors}
        recommendations={recommendations}
        recommendFor={recommendFor}
        loading={queueLoading}
        refreshing={queueRefreshing}
        error={queueError}
        profileWarning={patientLoadWarning}
        actionMessage={message}
        actionMessageError={messageError}
        busyAppointmentId={busyAppointmentId}
        lastUpdatedAt={lastUpdatedAt}
        onRefresh={async () => { await Promise.all([loadQueue(false, true), loadDoctors().catch(() => undefined)]); }}
        onRecommend={recommend}
        onAssign={assign}
        onConfirm={confirm}
        onCancel={cancel}
        onOpenSupport={openSupport}
        onOpenAccepted={() => window.dispatchEvent(new CustomEvent("reception-navigate", { detail: "records" }))}
    />;
    return <ReceptionAcceptedAppointments
        token={token}
        appointments={queue}
        reminders={reminders}
        patients={patients}
        doctors={doctors}
        queueLoading={queueLoading}
        queueRefreshing={queueRefreshing}
        queueError={queueError}
        reminderLoading={reminderLoading}
        reminderError={reminderError}
        patientLoadWarning={patientLoadWarning}
        actionMessage={message}
        actionMessageError={messageError}
        busyAppointmentId={busyAppointmentId}
        realtimeState={realtimeState}
        lastUpdatedAt={lastUpdatedAt}
        onRetryQueue={async () => { await loadQueue(true); }}
        onRetryReminders={async () => { await loadReminders(true); }}
        onRemind={async (id, action) => { await remind(id, action); }}
        onReschedule={reschedule}
        onCancel={cancel}
        onCheckIn={checkIn}
        onNoShow={async id => { await noShow(id); }}
        onOpenSupport={openSupport}
        onOpenRequests={() => window.dispatchEvent(new CustomEvent("reception-navigate", { detail: "appointments" }))}
    />
}
