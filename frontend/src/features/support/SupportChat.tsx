import { FormEvent, useEffect, useRef, useState } from "react";
import { CalendarCheck, CircleCheck, Headphones, MessageCircle, MessagesSquare, ShieldCheck, UserCheck, UserMinus } from "lucide-react";
import { request } from "../../core/api";
import { EmptyState } from "../../components/Ui";
import { enableChimeNotifications, subscribeRealtime, playChimeNotification } from "../../core/realtime";
import type { Appointment, AvailabilityResponse, AvailabilitySlot, Doctor, Patient, StaffDirectoryEntry, SupportConversation, SupportMessage, Tokens } from "../../core/types";
import { newIncomingSupportMessages } from "./supportMessageModel";
import SupportAssistant, { type AssistantTurnResponse } from "./SupportAssistant";

function tokenSubject(token: string) {
    try {
        const encoded = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
        const padded = encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=");
        return (JSON.parse(atob(padded)) as { sub?: string }).sub || "";
    } catch {
        return "";
    }
}

export default function SupportChat({ session }: { session: Tokens }) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<SupportMessage[]>([]);
    const [conversationStates, setConversationStates] = useState<SupportConversation[]>([]);
    const [staffDirectory, setStaffDirectory] = useState<Record<string, StaffDirectoryEntry>>({});
    const [conversation, setConversation] = useState("");
    const [patients, setPatients] = useState<Record<string, Patient>>({});
    const [text, setText] = useState("");
    const [error, setError] = useState("");
    const [assignmentBusy, setAssignmentBusy] = useState(false);
    const [bookingOpen, setBookingOpen] = useState(false);
    const [doctors, setDoctors] = useState<Doctor[]>([]);
    const [bookingDoctorId, setBookingDoctorId] = useState("");
    const [bookingDate, setBookingDate] = useState(() => new Date().toLocaleDateString("en-CA"));
    const [bookingSlots, setBookingSlots] = useState<AvailabilitySlot[]>([]);
    const [bookingClosureReason, setBookingClosureReason] = useState<string | null>(null);
    const [bookingSlot, setBookingSlot] = useState<AvailabilitySlot | null>(null);
    const [bookingReason, setBookingReason] = useState("");
    const [bookingBusy, setBookingBusy] = useState(false);
    const [notice, setNotice] = useState("");
    const [handoffNotice, setHandoffNotice] = useState(false);
    const [patientChannel, setPatientChannel] = useState<"assistant" | "receptionist">("assistant");

    const knownMessageIdsRef = useRef<Set<string>>(new Set());
    const messagesInitializedRef = useRef(false);
    const messageListRef = useRef<HTMLDivElement>(null);
    const requestedConversationRef = useRef("");
    const receptionist = session.role === "RECEPTIONIST";
    const admin = session.role === "ADMIN";
    const staffViewer = receptionist || admin;
    const currentIdentityId = tokenSubject(session.accessToken);
    const ids = [...new Set([...conversationStates.map(item => item.patientIdentityId), ...messages.map(item => item.patientIdentityId), ...(requestedConversationRef.current ? [requestedConversationRef.current] : [])])];
    const visible = staffViewer ? messages.filter(item => item.patientIdentityId === conversation) : messages;
    const activeConversation = conversationStates.find(item => item.patientIdentityId === conversation);
    const assignedToMe = receptionist && !!currentIdentityId && activeConversation?.assignedReceptionistIdentityId === currentIdentityId;
    const resolvedConversation = receptionist && activeConversation?.channelStatus === "AI_ACTIVE" && !!activeConversation.resolvedAt;
    const unread = admin ? [] : messages.filter(item => !item.readAt && (receptionist ? item.senderRole === "PATIENT" : item.senderRole !== "PATIENT"));
    const showAssistant = !staffViewer && patientChannel === "assistant";

    const staffName = (identityId?: string | null) => {
        if (!identityId) return "Chưa có người phụ trách";
        return staffDirectory[identityId]?.displayName?.trim() || "Lễ tân Derm";
    };

    async function load() {
        try {
            const [list, states, directory] = await Promise.all([
                request<SupportMessage[]>("/appointments/support", session.accessToken),
                request<SupportConversation[]>("/appointments/support/conversations", session.accessToken),
                request<StaffDirectoryEntry[]>("/auth/staff/directory", session.accessToken),
            ]);

            // Compare message IDs so the first message after an empty inbox is not missed.
            if (messagesInitializedRef.current && !admin) {
                const incoming = newIncomingSupportMessages(knownMessageIdsRef.current, list, receptionist);
                if (incoming.length) playChimeNotification();
            }
            knownMessageIdsRef.current = new Set(list.map(message => message.id));
            messagesInitializedRef.current = true;

            setMessages(list);
            setConversationStates(states);
            setStaffDirectory(Object.fromEntries(directory.map(item => [item.identityId, item])));
            const patientIds = [...new Set([...states.map(item => item.patientIdentityId), ...list.map(item => item.patientIdentityId), ...(requestedConversationRef.current ? [requestedConversationRef.current] : [])])];
            if (staffViewer) {
                const missing = patientIds.filter(id => !patients[id]);
                if (missing.length) {
                    const loaded = await Promise.all(missing.map(async id => {
                        try { return await request<Patient>(`/patients/identity/${id}`, session.accessToken); }
                        catch { return null; }
                    }));
                    setPatients(current => ({
                        ...current,
                        ...Object.fromEntries(loaded.filter((patient): patient is Patient => !!patient).map(patient => [patient.identityId, patient])),
                    }));
                }
                const preferredConversation = requestedConversationRef.current || conversation;
                if (preferredConversation && patientIds.includes(preferredConversation)) setConversation(preferredConversation);
                else if (!preferredConversation && patientIds[0]) setConversation(patientIds[0]);
            } else if (patientIds[0]) {
                if (!conversation) setConversation(patientIds[0]);
                if (!patients[patientIds[0]]) {
                    const me = await request<Patient>("/patients/me", session.accessToken);
                    setPatients({ [me.identityId]: me });
                }
            }
            if (!staffViewer) {
                const patientState = states[0];
                const handedToReception = !!patientState?.channelStatus && patientState.channelStatus !== "AI_ACTIVE";
                setPatientChannel(handedToReception ? "receptionist" : "assistant");
                setHandoffNotice(handedToReception);
            }
            setError("");
        } catch (reason) {
            setError((reason as Error).message);
        }
    }

    useEffect(() => {
        void load();
        const timer = window.setInterval(() => void load(), 4000);
        return () => window.clearInterval(timer);
    }, [open, conversation]);

    useEffect(() => {
        // Browsers require a user gesture before Web Audio may play in a background update.
        const unlockAudio = () => enableChimeNotifications();
        window.addEventListener("pointerdown", unlockAudio, { passive: true });
        window.addEventListener("keydown", unlockAudio);
        return () => {
            window.removeEventListener("pointerdown", unlockAudio);
            window.removeEventListener("keydown", unlockAudio);
        };
    }, []);

    useEffect(() => subscribeRealtime(event => {
        if (event.type === "CHAT_CHANGED") void load();
    }), [conversation]);

    useEffect(() => {
        const openChat = (event: Event) => {
            const detail = (event as CustomEvent<{ patientIdentityId?: string }>).detail;
            const patientIdentityId = detail?.patientIdentityId || sessionStorage.getItem("reception-support-patient");
            if (receptionist && patientIdentityId) {
                requestedConversationRef.current = patientIdentityId;
                setConversation(patientIdentityId);
            }
            setOpen(true);
        };
        window.addEventListener("open-support-chat", openChat);
        return () => window.removeEventListener("open-support-chat", openChat);
    }, [receptionist]);

    useEffect(() => {
        if (!open || admin || (receptionist && (!conversation || !assignedToMe))) return;
        const pending = messages.filter(item => !item.readAt && (receptionist ? item.patientIdentityId === conversation && item.senderRole === "PATIENT" : item.senderRole !== "PATIENT"));
        if (!pending.length) return;
        const readAt = new Date().toISOString();
        setMessages(current => current.map(item => pending.some(candidate => candidate.id === item.id) ? { ...item, readAt } : item));
        Promise.all(pending.map(item => request(`/appointments/support/${item.id}/read`, session.accessToken, { method: "PATCH" }))).catch(reason => setError((reason as Error).message));
    }, [open, conversation, messages, assignedToMe, admin, receptionist, session.accessToken]);

    useEffect(() => { setBookingOpen(false); setBookingSlot(null); setBookingSlots([]); setNotice(""); }, [conversation]);
    useEffect(() => { if (receptionist && !assignedToMe) setBookingOpen(false); }, [receptionist, assignedToMe]);
    useEffect(() => { if (!bookingOpen || !bookingDoctorId || !bookingDate) return; void loadBookingSlots(); }, [bookingOpen, bookingDoctorId, bookingDate]);

    useEffect(() => {
        if (!open || showAssistant || bookingOpen) return;
        // Scroll only the transcript viewport after React has painted the new
        // message; this keeps the page position and the composer unchanged.
        const frame = window.requestAnimationFrame(() => {
            const list = messageListRef.current;
            if (!list) return;
            const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            list.scrollTo({ top: list.scrollHeight, behavior: reducedMotion ? "auto" : "smooth" });
        });
        return () => window.cancelAnimationFrame(frame);
    }, [open, conversation, visible.length, showAssistant, bookingOpen]);

    async function claimConversation() {
        if (!conversation || assignmentBusy) return;
        setAssignmentBusy(true);
        setError("");
        try {
            await request(`/appointments/support/conversations/${conversation}/claim`, session.accessToken, { method: "POST" });
            setNotice("Bạn đang phụ trách cuộc trò chuyện này.");
            await load();
        } catch (reason) {
            setError((reason as Error).message);
            await load();
        } finally {
            setAssignmentBusy(false);
        }
    }

    async function releaseConversation() {
        if (!conversation || assignmentBusy) return;
        if (!window.confirm("Nhả cuộc trò chuyện này để lễ tân khác có thể nhận xử lý?")) return;
        setAssignmentBusy(true);
        setError("");
        try {
            await request(`/appointments/support/conversations/${conversation}/claim`, session.accessToken, { method: "DELETE" });
            setNotice("Đã nhả cuộc trò chuyện. Lễ tân khác có thể tiếp nhận.");
            await load();
        } catch (reason) {
            setError((reason as Error).message);
        } finally {
            setAssignmentBusy(false);
        }
    }

    async function resolveConversation() {
        if (!conversation || !assignedToMe || assignmentBusy) return;
        if (!window.confirm("Đánh dấu yêu cầu này đã được hỗ trợ xong? Yêu cầu tiếp theo của bệnh nhân sẽ quay lại Trợ lý Derm trước.")) return;
        setAssignmentBusy(true);
        setError("");
        try {
            await request(`/appointments/support/conversations/${conversation}/resolve`, session.accessToken, { method: "POST" });
            setNotice("Đã hoàn tất hỗ trợ. Yêu cầu mới của bệnh nhân sẽ được Trợ lý Derm tiếp nhận trước.");
            await load();
        } catch (reason) {
            setError((reason as Error).message);
            await load();
        } finally {
            setAssignmentBusy(false);
        }
    }

    async function send(event: FormEvent) {
        event.preventDefault();
        if (!text.trim() || (receptionist && (!conversation || !assignedToMe)) || admin) return;
        try {
            await request("/appointments/support", session.accessToken, {
                method: "POST",
                body: JSON.stringify({ patientIdentityId: receptionist ? conversation : null, body: text.trim() }),
            });
            setText("");
            await load();
        } catch (reason) {
            setError((reason as Error).message);
        }
    }

    async function assistantUpdated(result: AssistantTurnResponse) {
        await load();
        if (result.escalated) {
            setPatientChannel("receptionist");
            setHandoffNotice(true);
            setNotice("");
        }
    }

    async function openBooking() {
        if (!assignedToMe) {
            setError("Bạn cần nhận cuộc trò chuyện trước khi đặt lịch hộ.");
            return;
        }
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
        } catch (reason) {
            setError((reason as Error).message);
        }
    }

    async function loadBookingSlots() {
        setBookingBusy(true);
        setBookingSlot(null);
        try {
            const result = await request<AvailabilityResponse>(`/appointments/availability?doctorId=${encodeURIComponent(bookingDoctorId)}&date=${encodeURIComponent(bookingDate)}&durationMinutes=30`, session.accessToken);
            setBookingSlots(result.items.filter(item => item.status === "AVAILABLE"));
            setBookingClosureReason(result.status === "CLINIC_CLOSED"
                ? result.closureReason?.trim() || "Phòng khám tạm nghỉ."
                : null);
            setError("");
        } catch (reason) {
            setBookingSlots([]);
            setBookingClosureReason(null);
            setError((reason as Error).message);
        } finally {
            setBookingBusy(false);
        }
    }

    async function submitProposal(event: FormEvent) {
        event.preventDefault();
        const patient = patients[conversation];
        if (!assignedToMe || !patient || !bookingSlot || !bookingReason.trim()) return;
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
                    reason: bookingReason.trim(),
                }),
            });
            const time = new Date(bookingSlot.startAt).toLocaleString("vi-VN");
            await request("/appointments/support", session.accessToken, {
                method: "POST",
                body: JSON.stringify({ patientIdentityId: conversation, body: `Lễ tân đã gửi đề nghị lịch ${time} với BS. ${bookingSlot.doctorName}. Bạn vui lòng mở Thông báo và xác nhận trong 10 phút.` }),
            });
            setBookingOpen(false);
            setBookingSlot(null);
            setBookingReason("");
            setNotice("Đã gửi đề nghị. Đang chờ bệnh nhân xác nhận trong 10 phút.");
            await load();
        } catch (reason) {
            setError((reason as Error).message);
            await loadBookingSlots();
        } finally {
            setBookingBusy(false);
        }
    }

    const patientLabel = (id: string) => patients[id]?.fullName || `Bệnh nhân · ${id.slice(0, 8)}`;
    const messageSender = (message: SupportMessage) => message.senderRole === "PATIENT"
        ? patientLabel(message.patientIdentityId)
        : message.senderRole === "AI" ? "Trợ lý Derm"
        : message.senderRole === "SYSTEM" ? "Hệ thống"
        : message.senderRole === "ADMIN" ? "Quản trị viên" : staffName(message.senderIdentityId);

    const messageBody = (message: SupportMessage) => {
        if (staffViewer || !message.body.startsWith("[Yêu cầu chuyển từ Trợ lý AI]")) return message.body;
        const contentMarker = "\nNội dung: ";
        const noteMarker = "\nGhi chú: ";
        const start = message.body.indexOf(contentMarker);
        if (start < 0) return message.body;
        const contentStart = start + contentMarker.length;
        const end = message.body.indexOf(noteMarker, contentStart);
        return message.body.slice(contentStart, end < 0 ? undefined : end).trim();
    };

    return <div className={`support-chat ${staffViewer ? "receptionist-support-chat" : ""}`}>
        <button className="support-launch" aria-expanded={open} aria-controls="reception-support-panel" onClick={() => setOpen(!open)}>
            {open ? "Đóng" : admin ? "Giám sát hỗ trợ" : receptionist ? "Hộp thư hỗ trợ" : "Hỗ trợ"}
            {unread.length > 0 && <span className="support-badge">{unread.length > 99 ? "99+" : unread.length}</span>}
        </button>
        {open && <section id="reception-support-panel" className="support-panel" aria-label={staffViewer ? "Hộp thư hỗ trợ bệnh nhân" : "Hỗ trợ Derm Clinic"}>
            <header>
                <div>
                    <b>{admin ? "Giám sát hỗ trợ" : receptionist ? "Hỗ trợ bệnh nhân" : showAssistant ? "Trợ lý Derm" : "Lễ tân Derm"}</b>
                    <small>{admin ? "Chế độ chỉ xem" : receptionist ? "Hộp thư chung của đội ngũ lễ tân" : showAssistant ? "Hỗ trợ thông tin trước khi kết nối nhân viên" : activeConversation?.assignedReceptionistIdentityId ? `Đang hỗ trợ: ${staffName(activeConversation.assignedReceptionistIdentityId)}` : "Đã chuyển yêu cầu · đang chờ lễ tân tiếp nhận"}</small>
                </div>
                {receptionist && conversation && assignedToMe && <button className="support-book-for" onClick={() => bookingOpen ? setBookingOpen(false) : openBooking()}>{bookingOpen ? "Quay lại chat" : "Đặt lịch hộ"}</button>}
            </header>

            {staffViewer && <div className="support-conversations" onWheel={event => {
                const rail = event.currentTarget;
                if (rail.scrollWidth <= rail.clientWidth || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
                rail.scrollLeft += event.deltaY;
                event.preventDefault();
            }}>
                {ids.length === 0 ? <EmptyState compact className="support-conversation-empty" icon={MessagesSquare} title="Chưa có yêu cầu hỗ trợ" description="Các cuộc trò chuyện được chuyển tiếp sẽ xuất hiện tại đây." /> : ids.map(id => {
                    const state = conversationStates.find(item => item.patientIdentityId === id);
                    const mine = receptionist && state?.assignedReceptionistIdentityId === currentIdentityId;
                    const resolved = state?.channelStatus === "AI_ACTIVE" && !!state.resolvedAt;
                    return <button className={conversation === id ? "active" : ""} onClick={() => { requestedConversationRef.current = id; setConversation(id); }} key={id}>
                        <b>{patientLabel(id)}</b>
                        <span>{patients[id]?.phone || "Chưa có số điện thoại"} · {messages.filter(item => item.patientIdentityId === id).length} tin{messages.some(item => item.patientIdentityId === id && item.senderRole === "PATIENT" && !item.readAt) && <i className="conversation-unread" />}</span>
                        <em className={resolved ? "is-resolved" : !state?.assignedReceptionistIdentityId ? "is-unassigned" : mine ? "is-mine" : ""}>{resolved ? "Đã hoàn tất" : !state?.assignedReceptionistIdentityId ? "Chưa tiếp nhận" : mine ? "Bạn đang phụ trách" : staffName(state.assignedReceptionistIdentityId)}</em>
                    </button>;
                })}
            </div>}

            {staffViewer && conversation && <div className={`support-assignment ${resolvedConversation ? "is-resolved" : assignedToMe ? "is-mine" : activeConversation?.assignedReceptionistIdentityId ? "is-assigned" : "is-unassigned"}`}>
                <div>{resolvedConversation ? <CircleCheck aria-hidden="true" /> : activeConversation?.assignedReceptionistIdentityId ? <UserCheck aria-hidden="true" /> : <Headphones aria-hidden="true" />}<span><b>{resolvedConversation ? "Đã hoàn tất hỗ trợ" : activeConversation?.assignedReceptionistIdentityId ? staffName(activeConversation.assignedReceptionistIdentityId) : "Chưa có lễ tân tiếp nhận"}</b><small>{resolvedConversation ? "Lịch sử trò chuyện được giữ lại để bạn có thể xem khi cần." : admin ? "Quản trị viên đang xem và không thể gửi tin." : assignedToMe ? "Bạn đang phụ trách cuộc trò chuyện này." : activeConversation?.assignedReceptionistIdentityId ? "Bạn vẫn có thể xem nội dung cuộc trò chuyện." : "Nhận xử lý trước khi trả lời bệnh nhân."}</small></span></div>
                {receptionist && !resolvedConversation && !activeConversation?.assignedReceptionistIdentityId && <button type="button" disabled={assignmentBusy} onClick={claimConversation}><UserCheck aria-hidden="true" />{assignmentBusy ? "Đang nhận…" : "Nhận xử lý"}</button>}
                {receptionist && assignedToMe && <div className="support-assignment-actions">
                    <button type="button" className="support-resolve" aria-label="Hoàn tất hỗ trợ cuộc trò chuyện" title="Hoàn tất hỗ trợ" disabled={assignmentBusy} onClick={resolveConversation}><CircleCheck aria-hidden="true" />Hoàn tất</button>
                    <button type="button" className="support-release" aria-label="Nhả cuộc trò chuyện" title="Nhả cuộc trò chuyện" disabled={assignmentBusy} onClick={releaseConversation}><UserMinus aria-hidden="true" />Nhả</button>
                </div>}
            </div>}

            {showAssistant ? <SupportAssistant token={session.accessToken} messages={messages} onUpdated={assistantUpdated} /> : <>
            {handoffNotice && !staffViewer && <div className="support-handoff-confirmation" role="status" aria-live="polite">
                <MessageCircle aria-hidden="true" />
                <span><b>Đã chuyển yêu cầu của bạn đến lễ tân.</b><small>Lễ tân sẽ tiếp tục hỗ trợ trong cuộc trò chuyện này.</small></span>
            </div>}
            {notice && <p className="support-notice" aria-live="polite">{notice}</p>}
            {bookingOpen && receptionist && assignedToMe ? <form className="support-booking" onSubmit={submitProposal}>
                <div className="support-booking-title"><div><small>ĐẶT LỊCH HỘ</small><b>{patientLabel(conversation)}</b></div><CalendarCheck /></div>
                <label>Bác sĩ<select value={bookingDoctorId} onChange={event => setBookingDoctorId(event.target.value)}>{doctors.map(doctor => <option key={doctor.id} value={doctor.id}>BS. {doctor.fullName} · {doctor.specialtyCode}</option>)}</select></label>
                <label>Ngày khám<input type="date" min={new Date().toLocaleDateString("en-CA")} value={bookingDate} onChange={event => setBookingDate(event.target.value)} /></label>
                <div className="support-slot-list">{bookingBusy && !bookingSlots.length ? <small>Đang tải giờ trống…</small> : bookingClosureReason !== null ? <small>Phòng khám nghỉ trong ngày này. Lý do: {bookingClosureReason} Vui lòng chọn ngày khác.</small> : bookingSlots.length ? bookingSlots.map(slot => <button type="button" className={bookingSlot?.startAt === slot.startAt ? "selected" : ""} key={slot.startAt} onClick={() => setBookingSlot(slot)}>{new Date(slot.startAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</button>) : <small>Không có giờ trống trong ngày này.</small>}</div>
                <label>Lý do khám<textarea required maxLength={500} value={bookingReason} onChange={event => setBookingReason(event.target.value)} placeholder="Nhập triệu chứng hoặc nhu cầu bệnh nhân đã trao đổi…" /></label>
                {bookingSlot && <p className="support-proposal-summary"><b>{new Date(bookingSlot.startAt).toLocaleString("vi-VN")}</b><span>BS. {bookingSlot.doctorName} · bệnh nhân có 10 phút xác nhận</span></p>}
                <button className="support-proposal-submit" disabled={bookingBusy || !bookingSlot || !bookingReason.trim()}>{bookingBusy ? "Đang gửi…" : "Gửi bệnh nhân xác nhận"}</button>
            </form> : <>
                <div ref={messageListRef} className="support-messages" role="log" aria-live="polite" aria-label="Nội dung trao đổi hỗ trợ">{visible.length === 0 ? <p>{staffViewer ? "Cuộc trò chuyện chưa có tin nhắn." : "Lễ tân chưa gửi tin nhắn mới. Bạn có thể bổ sung nội dung bên dưới."}</p> : visible.map(message => {
                    const mine=staffViewer ? message.senderIdentityId === currentIdentityId && message.senderRole === "RECEPTIONIST" : message.senderRole === "PATIENT";
                    return <article className={message.senderRole === "SYSTEM" ? "system" : mine ? "mine" : "theirs"} key={message.id}><b>{messageSender(message)}</b><p>{messageBody(message)}</p><small>{new Date(message.sentAt).toLocaleString("vi-VN")}</small></article>;
                })}</div>
                {admin ? <div className="support-monitor-note"><ShieldCheck aria-hidden="true" /><span><b>Chế độ giám sát</b><small>Admin có thể xem người phụ trách và nội dung nhưng không gửi tin thay lễ tân.</small></span></div> : receptionist && !assignedToMe ? <div className="support-reply-locked"><Headphones aria-hidden="true" /><span>{resolvedConversation ? "Yêu cầu đã hoàn tất. Bạn vẫn có thể xem lại toàn bộ lịch sử phía trên." : activeConversation?.assignedReceptionistIdentityId ? `Cuộc trò chuyện đang do ${staffName(activeConversation.assignedReceptionistIdentityId)} phụ trách.` : "Nhận xử lý để trả lời bệnh nhân."}</span></div> : <form onSubmit={send}><textarea aria-label="Nội dung tin nhắn hỗ trợ" aria-keyshortcuts="Enter" title="Enter để gửi, Shift + Enter để xuống dòng" maxLength={2000} value={text} onChange={event => setText(event.target.value)} onKeyDown={event => {
                    // Enter submits like a messaging app; preserve Shift+Enter
                    // for multiline content and never interrupt an active IME.
                    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                    }
                }} placeholder="Nhập nội dung hỗ trợ về lịch khám…" /><button aria-label="Gửi tin nhắn" disabled={!text.trim()}>Gửi</button></form>}
            </>}
            </>}
            {error && <small className="support-error" role="alert">{error}</small>}
        </section>}
    </div>;
}
