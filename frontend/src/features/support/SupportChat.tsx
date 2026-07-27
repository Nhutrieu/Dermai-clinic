import { FormEvent, useEffect, useRef, useState } from "react";
import { CalendarCheck } from "lucide-react";
import { request } from "../../core/api";
import { subscribeRealtime, playChimeNotification } from "../../core/realtime";
import type { Appointment, AvailabilitySlot, Doctor, Patient, SupportMessage, Tokens } from "../../core/types";

export default function SupportChat({ session }: { session: Tokens }) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<SupportMessage[]>([]);
    const [conversation, setConversation] = useState("");
    const [patients, setPatients] = useState<Record<string, Patient>>({});
    const [text, setText] = useState("");
    const [error, setError] = useState("");
    const [bookingOpen, setBookingOpen] = useState(false);
    const [doctors, setDoctors] = useState<Doctor[]>([]);
    const [bookingDoctorId, setBookingDoctorId] = useState("");
    const [bookingDate, setBookingDate] = useState(() => new Date().toLocaleDateString("en-CA"));
    const [bookingSlots, setBookingSlots] = useState<AvailabilitySlot[]>([]);
    const [bookingSlot, setBookingSlot] = useState<AvailabilitySlot | null>(null);
    const [bookingReason, setBookingReason] = useState("");
    const [bookingBusy, setBookingBusy] = useState(false);
    const [notice, setNotice] = useState("");

    const prevCountRef = useRef<number>(0);
    const receptionist = session.role === "RECEPTIONIST";
    const ids = [...new Set(messages.map(x => x.patientIdentityId))];
    const visible = receptionist ? messages.filter(x => x.patientIdentityId === conversation) : messages;
    const unread = messages.filter(x => !x.readAt && (receptionist ? x.senderRole === "PATIENT" : x.senderRole !== "PATIENT"));

    async function load() {
        try {
            const list = await request<SupportMessage[]>("/appointments/support", session.accessToken);
            
            // ONLY play audio chime when a NEW message from the OTHER person arrives
            if (prevCountRef.current > 0 && list.length > prevCountRef.current) {
                const latestMsg = list[list.length - 1];
                const isFromOther = receptionist ? latestMsg.senderRole === "PATIENT" : latestMsg.senderRole !== "PATIENT";
                if (isFromOther) {
                    playChimeNotification();
                }
            }
            prevCountRef.current = list.length;

            setMessages(list);
            const patientIds = [...new Set(list.map(x => x.patientIdentityId))];
            if (receptionist) {
                const missing = patientIds.filter(id => !patients[id]);
                if (missing.length) {
                    const loaded = await Promise.all(
                        missing.map(async id => {
                            try { return await request<Patient>(`/patients/identity/${id}`, session.accessToken); }
                            catch { return null; }
                        })
                    );
                    setPatients(current => ({
                        ...current,
                        ...Object.fromEntries(loaded.filter((p): p is Patient => !!p).map(p => [p.identityId, p]))
                    }));
                }
                if (!conversation && list[0]) setConversation(list[0].patientIdentityId);
            } else if (patientIds[0] && !patients[patientIds[0]]) {
                const me = await request<Patient>("/patients/me", session.accessToken);
                setPatients({ [me.identityId]: me });
            }
            setError("");
        } catch (x) {
            setError((x as Error).message);
        }
    }

    useEffect(() => {
        load();
        const timer = window.setInterval(load, 4000);
        return () => window.clearInterval(timer);
    }, [open, conversation]);

    useEffect(() => subscribeRealtime(event => {
        if (event.type === "CHAT_CHANGED") void load();
    }), [conversation]);

    useEffect(() => {
        const openChat = () => {
            const patientIdentityId = sessionStorage.getItem("reception-support-patient");
            if (receptionist && patientIdentityId) setConversation(patientIdentityId);
            setOpen(true);
        };
        window.addEventListener("open-support-chat", openChat);
        return () => window.removeEventListener("open-support-chat", openChat);
    }, [receptionist]);

    useEffect(() => {
        if (!open || (receptionist && !conversation)) return;
        const pending = messages.filter(x => !x.readAt && (receptionist ? x.patientIdentityId === conversation && x.senderRole === "PATIENT" : x.senderRole !== "PATIENT"));
        if (!pending.length) return;
        const readAt = new Date().toISOString();
        setMessages(current => current.map(x => pending.some(p => p.id === x.id) ? { ...x, readAt } : x));
        Promise.all(pending.map(x => request(`/appointments/support/${x.id}/read`, session.accessToken, { method: "PATCH" }))).catch(x => setError((x as Error).message));
    }, [open, conversation, messages]);

    useEffect(() => { setBookingOpen(false); setBookingSlot(null); setBookingSlots([]); setNotice(""); }, [conversation]);
    useEffect(() => { if (!bookingOpen || !bookingDoctorId || !bookingDate) return; void loadBookingSlots(); }, [bookingOpen, bookingDoctorId, bookingDate]);

    async function send(e: FormEvent) {
        e.preventDefault();
        if (!text.trim() || (receptionist && !conversation)) return;
        try {
            await request("/appointments/support", session.accessToken, {
                method: "POST",
                body: JSON.stringify({ patientIdentityId: receptionist ? conversation : null, body: text.trim() })
            });
            setText("");
            await load();
        } catch (x) {
            setError((x as Error).message);
        }
    }

    async function openBooking() {
        if (!conversation || !patients[conversation]) {
            setError("Chưa đọc được hồ sơ bệnh nhân trong cuộc trò chuyện.");
            return;
        }
        setError("");
        setNotice("");
        try {
            let list = doctors;
            if (!list.length) {
                list = await request<Doctor[]>("/doctors", session.accessToken);
                setDoctors(list);
            }
            if (!list.length) {
                setError("Chưa có bác sĩ để đặt lịch.");
                return;
            }
            if (!bookingDoctorId) setBookingDoctorId(list[0].id);
            setBookingOpen(true);
        } catch (x) {
            setError((x as Error).message);
        }
    }

    async function loadBookingSlots() {
        setBookingBusy(true);
        setBookingSlot(null);
        try {
            const result = await request<{ items: AvailabilitySlot[] }>(`/appointments/availability?doctorId=${encodeURIComponent(bookingDoctorId)}&date=${encodeURIComponent(bookingDate)}&durationMinutes=30`, session.accessToken);
            setBookingSlots(result.items.filter(x => x.status === "AVAILABLE"));
            setError("");
        } catch (x) {
            setBookingSlots([]);
            setError((x as Error).message);
        } finally {
            setBookingBusy(false);
        }
    }

    async function submitProposal(e: FormEvent) {
        e.preventDefault();
        const patient = patients[conversation];
        if (!patient || !bookingSlot || !bookingReason.trim()) return;
        setBookingBusy(true);
        try {
            await request<Appointment>("/appointments/proposals", session.accessToken, {
                method: "POST",
                body: JSON.stringify({
                    patientId: patient.id,
                    patientIdentityId: patient.identityId,
                    doctorId: bookingSlot.doctorId,
                    doctorIdentityId: bookingSlot.doctorIdentityId,
                    startAt: bookingSlot.startAt,
                    endAt: bookingSlot.endAt,
                    reason: bookingReason.trim()
                })
            });
            const time = new Date(bookingSlot.startAt).toLocaleString("vi-VN");
            await request("/appointments/support", session.accessToken, {
                method: "POST",
                body: JSON.stringify({
                    patientIdentityId: conversation,
                    body: `Lễ tân đã gửi đề nghị lịch ${time} với BS. ${bookingSlot.doctorName}. Bạn vui lòng mở Thông báo và xác nhận trong 10 phút.`
                })
            });
            setBookingOpen(false);
            setBookingSlot(null);
            setBookingReason("");
            setNotice("Đã gửi đề nghị. Đang chờ bệnh nhân xác nhận trong 10 phút.");
            await load();
        } catch (x) {
            setError((x as Error).message);
            await loadBookingSlots();
        } finally {
            setBookingBusy(false);
        }
    }

    const patientLabel = (id: string) => patients[id]?.fullName || `Bệnh nhân · ${id.slice(0, 8)}`;

    return (
        <div className="support-chat">
            <button
                className="support-launch"
                onClick={() => setOpen(!open)}
            >
                {open ? "Đóng" : receptionist ? "Hộp thư hỗ trợ" : "Chat với lễ tân"}
                {unread.length > 0 && <span className="support-badge">{unread.length > 99 ? "99+" : unread.length}</span>}
            </button>
            {open && (
                <section className="support-panel">
                    <header>
                        <div>
                            <b>{receptionist ? "Hỗ trợ bệnh nhân" : "Lễ tân DermAI"}</b>
                            <small>Hỗ trợ lịch khám và thủ tục</small>
                        </div>
                        {receptionist && conversation && (
                            <button className="support-book-for" onClick={() => bookingOpen ? setBookingOpen(false) : openBooking()}>
                                {bookingOpen ? "Quay lại chat" : "Đặt lịch hộ"}
                            </button>
                        )}
                    </header>
                    {receptionist && (
                        <div className="support-conversations">
                            {ids.length === 0 ? (
                                <small>Chưa có hội thoại</small>
                            ) : (
                                ids.map(id => (
                                    <button className={conversation === id ? "active" : ""} onClick={() => setConversation(id)} key={id}>
                                        <b>{patientLabel(id)}</b>
                                        <span>
                                            {patients[id]?.phone || "Chưa có số điện thoại"} · {messages.filter(x => x.patientIdentityId === id).length} tin
                                            {messages.some(x => x.patientIdentityId === id && x.senderRole === "PATIENT" && !x.readAt) && <i className="conversation-unread" />}
                                        </span>
                                    </button>
                                ))
                            )}
                        </div>
                    )}
                    {notice && <p className="support-notice">{notice}</p>}
                    {bookingOpen && receptionist ? (
                        <form className="support-booking" onSubmit={submitProposal}>
                            <div className="support-booking-title">
                                <div>
                                    <small>ĐẶT LỊCH HỘ</small>
                                    <b>{patientLabel(conversation)}</b>
                                </div>
                                <CalendarCheck />
                            </div>
                            <label>
                                Bác sĩ
                                <select value={bookingDoctorId} onChange={e => setBookingDoctorId(e.target.value)}>
                                    {doctors.map(d => (
                                        <option key={d.id} value={d.id}>BS. {d.fullName} · {d.specialtyCode}</option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Ngày khám
                                <input type="date" min={new Date().toLocaleDateString("en-CA")} value={bookingDate} onChange={e => setBookingDate(e.target.value)} />
                            </label>
                            <div className="support-slot-list">
                                {bookingBusy && !bookingSlots.length ? (
                                    <small>Đang tải giờ trống…</small>
                                ) : bookingSlots.length ? (
                                    bookingSlots.map(slot => (
                                        <button type="button" className={bookingSlot?.startAt === slot.startAt ? "selected" : ""} key={slot.startAt} onClick={() => setBookingSlot(slot)}>
                                            {new Date(slot.startAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}
                                        </button>
                                    ))
                                ) : (
                                    <small>Không có giờ trống trong ngày này.</small>
                                )}
                            </div>
                            <label>
                                Lý do khám
                                <textarea required maxLength={500} value={bookingReason} onChange={e => setBookingReason(e.target.value)} placeholder="Nhập triệu chứng hoặc nhu cầu bệnh nhân đã trao đổi…" />
                            </label>
                            {bookingSlot && (
                                <p className="support-proposal-summary">
                                    <b>{new Date(bookingSlot.startAt).toLocaleString("vi-VN")}</b>
                                    <span>BS. {bookingSlot.doctorName} · bệnh nhân có 10 phút xác nhận</span>
                                </p>
                            )}
                            <button className="support-proposal-submit" disabled={bookingBusy || !bookingSlot || !bookingReason.trim()}>
                                {bookingBusy ? "Đang gửi…" : "Gửi bệnh nhân xác nhận"}
                            </button>
                        </form>
                    ) : (
                        <>
                            <div className="support-messages">
                                {visible.length === 0 ? (
                                    <p>Chưa có tin nhắn. Hãy gửi nội dung bạn cần hỗ trợ.</p>
                                ) : (
                                    visible.map(m => (
                                        <article className={m.senderRole === session.role ? "mine" : "theirs"} key={m.id}>
                                            <b>{m.senderRole === "PATIENT" ? patientLabel(m.patientIdentityId) : "Lễ tân DermAI"}</b>
                                            <p>{m.body}</p>
                                            <small>{new Date(m.sentAt).toLocaleString("vi-VN")}</small>
                                        </article>
                                    ))
                                )}
                            </div>
                            <form onSubmit={send}>
                                <textarea maxLength={2000} value={text} onChange={e => setText(e.target.value)} placeholder="Nhập nội dung hỗ trợ về lịch khám…" />
                                <button disabled={!text.trim()}>Gửi</button>
                            </form>
                        </>
                    )}
                    {error && <small className="support-error">{error}</small>}
                </section>
            )}
        </div>
    );
}
