import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, Trash2 } from "lucide-react";
import { request } from "../core/api";
import type { Appointment, ClinicReview, Recommendation, RecommendationResult } from "../core/types";
import { State } from "./Ui";

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
        case "IN_PROGRESS": return { label: "Đang khám", badgeClass: "badge-in-progress" };
        case "COMPLETED": return { label: "Đã hoàn thành", badgeClass: "badge-completed" };
        case "CANCELLED": return { label: "Đã hủy", badgeClass: "badge-cancelled" };
        case "FOLLOW_UP_REQUIRED": return { label: "Yêu cầu tái khám", badgeClass: "badge-followup" };
        default: return { label: status, badgeClass: "badge-default" };
    }
}

export function RescheduleControl({ token, appointment, submit }: { token: string; appointment: Appointment; submit: (value: string) => Promise<void> }) { const [open, setOpen] = useState(false); const [value, setValue] = useState(""); const [slots, setSlots] = useState<Recommendation[]>([]); const [message, setMessage] = useState(""); async function find() { if (!appointment.doctorId) { await submit(value); setOpen(false); return } try { const result = await request<RecommendationResult>("/appointments/recommendations", token, { method: "POST", body: JSON.stringify({ patientId: appointment.patientId, preferredDoctorId: appointment.doctorId, preferredStart: new Date(value).toISOString(), durationMinutes: Math.round((new Date(appointment.endAt).getTime() - new Date(appointment.startAt).getTime()) / 60000), limit: 5 }) }); setSlots(result.items); setMessage(result.items.length ? "Chọn một slot đã được kiểm tra:" : "Không có slot hợp lệ trong 7 ngày.") } catch (x) { setMessage((x as Error).message) } } return open ? <div className="smart-action"><div className="action-form"><input type="datetime-local" required value={value} onChange={e => { setValue(e.target.value); setSlots([]) }} /><button disabled={!value} onClick={find}>{appointment.doctorId ? "Tìm slot" : "Lưu"}</button><button onClick={() => setOpen(false)}>Đóng</button></div>{message && <small>{message}</small>}{slots.map(slot => <button className="slot-choice" key={slot.startAt} onClick={async () => { await submit(slot.startAt); setOpen(false) }}>{formatAppointmentTime(slot.startAt)} · {Math.round(slot.score * 100)}/100</button>)}</div> : <button onClick={() => setOpen(true)}>Đổi lịch</button> }
export function CancelControl({ submit }: { submit: (reason: string) => Promise<void> }) { const [open, setOpen] = useState(false); const [reason, setReason] = useState(""); return open ? <div className="action-form"><input required placeholder="Lý do hủy" value={reason} onChange={e => setReason(e.target.value)} /><button disabled={!reason.trim()} onClick={async () => { await submit(reason); setOpen(false); setReason("") }}>Xác nhận hủy</button><button onClick={() => setOpen(false)}>Đóng</button></div> : <button onClick={() => setOpen(true)}>Hủy</button> }
function PatientFollowUpControl({ token, appointment, submit }: { token: string; appointment: Appointment; submit: (slot: Recommendation) => Promise<void> }) { const [open, setOpen] = useState(false); const [value, setValue] = useState(""); const [slots, setSlots] = useState<Recommendation[]>([]); const [message, setMessage] = useState(""); const minimum = appointment.followUpNotBefore ? new Date(appointment.followUpNotBefore).toISOString().slice(0, 16) : undefined; async function find() { try { const result = await request<RecommendationResult>("/appointments/recommendations", token, { method: "POST", body: JSON.stringify({ patientId: appointment.patientId, preferredDoctorId: appointment.doctorId, preferredStart: new Date(value).toISOString(), durationMinutes: 30, limit: 5 }) }); setSlots(result.items); setMessage(result.items.length ? "Chọn giờ tái khám phù hợp với bạn:" : "Không có giờ trống trong 7 ngày.") } catch (x) { setMessage((x as Error).message) } } return open ? <div className="smart-action"><b>Lý do: {appointment.followUpReason || "Bác sĩ yêu cầu tái khám"}</b>{appointment.followUpNotBefore && <small>Khám lại từ: {new Date(appointment.followUpNotBefore).toLocaleDateString("vi-VN")}</small>}<div className="action-form"><input type="datetime-local" required min={minimum} value={value} onChange={e => { setValue(e.target.value); setSlots([]) }} /><button disabled={!value} onClick={find}>Tìm giờ trống</button><button onClick={() => setOpen(false)}>Đóng</button></div>{message && <small>{message}</small>}{slots.map(slot => <button className="slot-choice" key={slot.startAt} onClick={async () => { await submit(slot); setOpen(false) }}>{formatAppointmentTime(slot.startAt)} · {Math.round(slot.score * 100)}/100</button>)}</div> : <button onClick={() => setOpen(true)}>Chọn giờ tái khám</button> }
export function HideCancelledButton({token,id}:{token:string;id:string}){const [busy,setBusy]=useState(false);async function hide(e:React.MouseEvent<HTMLButtonElement>){if(!confirm("Ẩn lịch đã hủy này khỏi danh sách của bạn?"))return;const row=e.currentTarget.closest("article");setBusy(true);try{await request(`/appointments/${id}/hide`,token,{method:"PATCH"});row?.remove()}catch(x){alert((x as Error).message);setBusy(false)}}return <button className="hide-cancelled" title="Xóa khỏi danh sách" aria-label="Xóa lịch đã hủy khỏi danh sách" disabled={busy} onClick={hide}><Trash2/></button>}
export function ReviewControl({token,appointmentId,patientName="Bệnh nhân"}:{token:string;appointmentId:string;patientName?:string}){const [open,setOpen]=useState(false);const [rating,setRating]=useState(5);const [comment,setComment]=useState("");const [submitted,setSubmitted]=useState(false);const [message,setMessage]=useState("");useEffect(()=>{request<ClinicReview[]>("/appointments/reviews/mine",token).then(items=>setSubmitted(items.some(x=>x.appointmentId===appointmentId))).catch(()=>{})},[appointmentId,token]);async function submit(e:FormEvent){e.preventDefault();try{await request(`/appointments/reviews/${appointmentId}`,token,{method:"PUT",body:JSON.stringify({rating,comment,displayName:patientName})});setSubmitted(true);setMessage("Đã gửi đánh giá, đang chờ quản trị viên duyệt.");setOpen(false)}catch(x){setMessage((x as Error).message)}}return <div className="review-control">{submitted?<button disabled>Đã đánh giá</button>:open?<form onSubmit={submit}><label>Số sao<select value={rating} onChange={e=>setRating(Number(e.target.value))}>{[5,4,3,2,1].map(x=><option key={x} value={x}>{x} sao</option>)}</select></label><textarea required minLength={5} maxLength={1000} value={comment} onChange={e=>setComment(e.target.value)} placeholder="Chia sẻ trải nghiệm của bạn..."/><button>Gửi đánh giá</button><button type="button" onClick={()=>setOpen(false)}>Đóng</button></form>:<button onClick={()=>setOpen(true)}>Đánh giá phòng khám</button>}{message&&<small>{message}</small>}</div>}

export default function AppointmentList({ appointments, token, cancel, reschedule, bookFollowUp, patientName = "Bệnh nhân" }: { appointments: Appointment[]; token?: string; cancel?: (id: string, reason: string) => Promise<void>; reschedule?: (id: string, value: string) => Promise<void>; bookFollowUp?: (id: string, slot: Recommendation) => Promise<void>; patientName?:string }) {
    const [searchKw, setSearchKw] = useState("");
    const [statusFilter, setStatusFilter] = useState("ALL");
    const [dateFilter, setDateFilter] = useState("ALL");

    const filtered = appointments.filter(x => {
        const kw = searchKw.trim().toLowerCase();
        const rText = (x.reason || "").toLowerCase();
        const fText = (x.followUpReason || "").toLowerCase();
        if (kw && !rText.includes(kw) && !fText.includes(kw)) return false;
        if (statusFilter !== "ALL" && x.status !== statusFilter) return false;
        if (dateFilter === "TODAY" && new Date(x.startAt).toDateString() !== new Date().toDateString()) return false;
        if (dateFilter === "UPCOMING" && new Date(x.startAt).getTime() < Date.now()) return false;
        if (dateFilter === "PAST" && new Date(x.startAt).getTime() >= Date.now()) return false;
        return true;
    });

    return <section className="panel schedule real-list">
        <h2>Lịch khám của tôi</h2>
        {appointments.length > 0 && (
            <div className="list-filter-bar">
                <div className="filter-group keyword-search">
                    <input 
                        type="text" 
                        value={searchKw} 
                        onChange={e => setSearchKw(e.target.value)} 
                        placeholder="Tìm triệu chứng, lý do..." 
                    />
                    {searchKw && <button type="button" className="clear-filter" onClick={() => setSearchKw("")}>×</button>}
                </div>
                <div className="filter-group">
                    <label>Trạng thái:</label>
                    <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
                        <option value="ALL">Tất cả ({appointments.length})</option>
                        <option value="PENDING">Chờ tiếp nhận</option>
                        <option value="CONFIRMED">Đã xác nhận</option>
                        <option value="COMPLETED">Đã hoàn thành</option>
                        <option value="CANCELLED">Đã hủy</option>
                        <option value="FOLLOW_UP_REQUIRED">Yêu cầu tái khám</option>
                    </select>
                </div>
                <div className="filter-group">
                    <label>Thời gian:</label>
                    <select value={dateFilter} onChange={e => setDateFilter(e.target.value)}>
                        <option value="ALL">Tất cả ngày</option>
                        <option value="TODAY">Hôm nay</option>
                        <option value="UPCOMING">Sắp tới</option>
                        <option value="PAST">Đã qua</option>
                    </select>
                </div>
                {(searchKw || statusFilter !== "ALL" || dateFilter !== "ALL") && (
                    <button 
                        type="button" 
                        className="reset-filters-btn" 
                        onClick={() => { setSearchKw(""); setStatusFilter("ALL"); setDateFilter("ALL"); }}
                    >
                        Xóa lọc
                    </button>
                )}
                <span className="filter-result-count">Hiển thị {filtered.length}/{appointments.length} lịch</span>
            </div>
        )}
        {filtered.length === 0 ? <State text={appointments.length === 0 ? "Chưa có lịch khám trong database." : "Không có lịch khám phù hợp với bộ lọc."} /> : filtered.map(x => {
            const { label, badgeClass } = getStatusBadge(x.status);
            return <article key={x.id} className="appointment-card">
                <div className="appointment-icon-wrapper">
                    <CalendarDays />
                </div>
                <div className="appointment-details">
                    <b className="appointment-time">{formatAppointmentTime(x.startAt)}</b>
                    <p className="appointment-reason">{x.status === "FOLLOW_UP_REQUIRED" ? x.followUpReason || "Bác sĩ yêu cầu tái khám" : x.reason || "Không có ghi chú"}</p>
                </div>
                <div className="actions">
                    <span className={`status-badge ${badgeClass}`}>{label}</span>
                    {["PENDING", "ASSIGNED", "CONFIRMED"].includes(x.status) && reschedule && token && <RescheduleControl token={token} appointment={x} submit={value => reschedule(x.id, value)} />}
                    {["PENDING", "ASSIGNED", "CONFIRMED"].includes(x.status) && cancel && (Date.now() - new Date(x.createdAt).getTime() <= 30 * 60_000 ? <CancelControl submit={reason => cancel(x.id, reason)} /> : <button className="contact-reception" onClick={() => window.dispatchEvent(new Event("open-support-chat"))}>Liên hệ lễ tân để hủy</button>)}
                    {x.status === "FOLLOW_UP_REQUIRED" && token && bookFollowUp && <PatientFollowUpControl token={token} appointment={x} submit={slot => bookFollowUp(x.id, slot)} />}
                    {x.status === "COMPLETED" && token && patientName && <ReviewControl token={token} appointmentId={x.id} patientName={patientName} />}
                </div>
            </article>;
        })}
    </section>;
}
AppointmentList.defaultProps={patientName:"Bệnh nhân"};

