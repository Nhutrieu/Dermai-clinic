import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, BrainCircuit, CalendarDays, CheckCircle2, Clock3, Stethoscope } from "lucide-react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import { subscribeRealtime } from "../../core/realtime";
import type { AiAssessment, Appointment, AvailabilityResponse, AvailabilitySlot, Doctor, Patient } from "../../core/types";
import AppointmentList from "../../components/AppointmentList";
import AccessibleDialog from "../../components/AccessibleDialog";
import { formatAiPercentage, patientAiLabel } from "./patientAiPresentation";

const ACTIVE_UPCOMING_STATUSES = new Set(["PROPOSED", "PENDING", "ASSIGNED", "CONFIRMED", "CHECKED_IN", "IN_PROGRESS"]);
const HOLD_DURATION_SECONDS = 5 * 60;
type Feedback = { tone: "info" | "success" | "error"; text: string };
type BookingDialogProps = {
    title: string;
    descriptionId: string;
    titleId: string;
    tone?: "warning" | "danger";
    children: ReactNode;
    primaryLabel: string;
    secondaryLabel: string;
    onPrimary: () => void;
    onClose: () => void;
    note?: string;
};

function activeUpcoming(list: Appointment[]) {
    const now = Date.now();
    return list.filter(item => ACTIVE_UPCOMING_STATUSES.has(item.status) && (["CHECKED_IN", "IN_PROGRESS"].includes(item.status) || new Date(item.endAt).getTime() > now));
}

function clinicDate(value: string) {
    return new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit"
    }).format(new Date(value));
}

function clinicDateInput(addDays = 0) {
    const value = new Date();
    value.setDate(value.getDate() + addDays);
    return new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit"
    }).format(value);
}

function formatTime(value: string) {
    return new Date(value).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

function formatDateTime(value: string) {
    return new Date(value).toLocaleString("vi-VN", {
        hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric"
    });
}

function formatDateInput(value: string) {
    const [year, month, day] = value.split("-");
    return year && month && day ? day + "/" + month + "/" + year : value;
}

function slotLabel(status: AvailabilitySlot["status"], holdCountdown: string) {
    switch (status) {
        case "BOOKED": return "Đã có người đặt";
        case "ON_LEAVE": return "Bác sĩ nghỉ";
        case "HELD_BY_YOU": return "Bạn đang giữ " + holdCountdown;
        case "HELD_BY_OTHER": return "Người khác đang giữ";
        default: return "Còn trống";
    }
}

function BookingDialog({
    title, descriptionId, titleId, tone = "warning", children, primaryLabel,
    secondaryLabel, onPrimary, onClose, note
}: BookingDialogProps) {
    return (
        <AccessibleDialog
            title={title}
            titleId={titleId}
            descriptionId={descriptionId}
            tone={tone}
            icon={<AlertTriangle />}
            onClose={onClose}
            footer={(
                <>
                    <button type="button" onClick={onClose}>{secondaryLabel}</button>
                    <button type="button" className="booking-dialog-primary" onClick={onPrimary}>{primaryLabel}</button>
                </>
            )}
        >
            {children}
            {note && <p className="booking-dialog-note">{note}</p>}
        </AccessibleDialog>
    );
}

export default function PatientAppointmentsView({
    token, patient, appointments, changed
}: {
    token: string;
    patient: Patient;
    appointments: Appointment[];
    changed: (appointments: Appointment[]) => void;
}) {
    const [doctors, setDoctors] = useState<Doctor[]>([]);
    const [doctorId, setDoctorId] = useState("");
    const [date, setDate] = useState(() => clinicDateInput());
    const [clinicClosureReason, setClinicClosureReason] = useState<string | null>(null);
    const [clinicClosureNotice, setClinicClosureNotice] = useState<string | null>(null);
    const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
    const [selected, setSelected] = useState<AvailabilitySlot | null>(null);
    const [pendingSlot, setPendingSlot] = useState<AvailabilitySlot | null>(null);
    const [duplicateBooking, setDuplicateBooking] = useState<{ slot: AvailabilitySlot; existing: Appointment } | null>(null);
    const [timeConflict, setTimeConflict] = useState<{ slot: AvailabilitySlot; existing: Appointment; doctorName: string } | null>(null);
    const [holdId, setHoldId] = useState("");
    const [holdUntil, setHoldUntil] = useState("");
    const [heldFee, setHeldFee] = useState<number | null>(null);
    const [holdClock, setHoldClock] = useState(Date.now());
    const [reason, setReason] = useState("");
    const [sharedAi, setSharedAi] = useState<AiAssessment | null>(null);
    const [items, setItems] = useState(appointments);
    const [feedback, setFeedback] = useState<Feedback | null>(null);
    const [busy, setBusy] = useState(false);
    const slotRequestInFlight = useRef(false);
    const clinicClosureNoticeKeyRef = useRef("");

    const doctor = doctors.find(item => item.id === doctorId);
    const upcomingCount = activeUpcoming(items).length;
    // A hold always lasts five minutes. Clamp the display so a stale render
    // clock or a small client/server clock skew can never show more than 5:00.
    const holdSeconds = holdUntil
        ? Math.min(HOLD_DURATION_SECONDS, Math.max(0, Math.ceil((new Date(holdUntil).getTime() - holdClock) / 1000)))
        : 0;
    const holdCountdown = Math.floor(holdSeconds / 60) + ":" + String(holdSeconds % 60).padStart(2, "0");

    async function loadDoctors() {
        const list = await request<Doctor[]>("/doctors", token);
        setDoctors(list);
        setDoctorId(current => current && list.some(item => item.id === current) ? current : list[0]?.id || "");
    }

    useEffect(() => {
        loadDoctors().catch(error => setFeedback({ tone: "error", text: (error as Error).message }));
    }, [token]);

    useEffect(() => {
        const refresh = () => { void loadDoctors().catch(() => undefined) };
        window.addEventListener("doctor-profiles-changed", refresh);
        return () => window.removeEventListener("doctor-profiles-changed", refresh);
    }, [token]);

    useEffect(() => {
        request<AiAssessment[]>("/patients/me/ai-assessments", token).then(list => {
            const draft = sessionStorage.getItem("dermai-ai-booking");
            let draftId = "";
            let draftSummary = "";
            try {
                const parsed = JSON.parse(draft || "{}");
                draftId = parsed.assessmentId || "";
                draftSummary = parsed.summary || "";
            } catch {
                /* Bỏ qua draft lỗi để luồng đặt lịch vẫn hoạt động. */
            }
            const assessment = list.find(item => item.id === draftId && item.sharedWithDoctor)
                || list.find(item => item.sharedWithDoctor);
            if (!assessment) return;
            setSharedAi(assessment);
            const top = assessment.top3
                .map(item => patientAiLabel(item.label) + " " + formatAiPercentage(item.probability))
                .join("; ");
            const summary = draftSummary
                || "Kết quả kiểm tra da bằng AI (tham khảo): " + top + ". Phiên bản mô hình "
                + assessment.modelVersion + "."
                + (assessment.uncertain ? " AI đánh dấu kết quả chưa chắc chắn." : "");
            setReason(value => value.trim() ? value : summary);
            sessionStorage.removeItem("dermai-ai-booking");
        }).catch(() => undefined);
    }, [token]);

    useEffect(() => {
        const raw = sessionStorage.getItem("derm-home-booking");
        if (!raw || !doctors.length) return;
        try {
            const draft = JSON.parse(raw) as { doctorId?: string; date?: string; reason?: string };
            if (draft.doctorId && doctors.some(item => item.id === draft.doctorId)) setDoctorId(draft.doctorId);
            if (draft.date) setDate(draft.date);
            if (draft.reason) setReason(value => value.trim() ? value : draft.reason || "");
            setFeedback({ tone: "success", text: "Đã khôi phục lựa chọn từ trang chủ. Hãy chọn khung giờ còn trống để tiếp tục." });
            sessionStorage.removeItem("derm-home-booking");
        } catch {
            sessionStorage.removeItem("derm-home-booking");
        }
    }, [doctors]);
    useEffect(() => { setItems(appointments) }, [appointments]);

    async function findSlots(realtime = false) {
        if (!doctorId || !date || slotRequestInFlight.current) return;
        slotRequestInFlight.current = true;
        // Background refreshes must not toggle the whole booking form into a
        // loading state; that was causing a visible pulse every few seconds.
        if (!realtime) setBusy(true);
        if (!realtime) {
            setFeedback(null);
            setClinicClosureReason(null);
            setSlots([]);
        }
        try {
            const result = await request<AvailabilityResponse>(
                "/appointments/availability?doctorId=" + encodeURIComponent(doctorId)
                + "&date=" + encodeURIComponent(date),
                token
            );
            const clinicClosed = result.status === "CLINIC_CLOSED";
            const closureReason = result.closureReason?.trim() || "Phòng khám tạm nghỉ.";
            setClinicClosureReason(clinicClosed ? closureReason : null);
            if (clinicClosed) {
                const closureKey = doctorId + ":" + date + ":" + closureReason;
                if (clinicClosureNoticeKeyRef.current !== closureKey) {
                    clinicClosureNoticeKeyRef.current = closureKey;
                    setClinicClosureNotice(closureReason);
                }
                if (holdId) await releaseHold();
                else {
                    setSelected(null);
                    setHoldUntil("");
                    setHeldFee(null);
                }
            } else {
                clinicClosureNoticeKeyRef.current = "";
                setClinicClosureNotice(null);
            }
            setSlots(result.items);
            const own = result.items.find(item => item.status === "HELD_BY_YOU");
            if (own) {
                setSelected(own);
                setHoldId(own.holdId || "");
                setHoldClock(Date.now());
                setHoldUntil(own.holdExpiresAt || "");
            } else if (selected && !result.items.some(item => item.startAt === selected.startAt && item.status === "AVAILABLE")) {
                setSelected(null);
                setHoldId("");
                setHoldUntil("");
                setHeldFee(null);
            }
            const available = result.items.filter(item => item.status === "AVAILABLE").length;
            const doctorOnLeave = result.items.length > 0
                && result.items.every(item => item.status === "ON_LEAVE");
            const text = clinicClosed
                ? "Phòng khám nghỉ trong ngày này. Lý do: " + closureReason + " Vui lòng chọn ngày khác."
                : doctorOnLeave
                ? "Bác sĩ nghỉ trong ngày này. Vui lòng chọn ngày hoặc bác sĩ khác."
                : result.items.length
                ? realtime ? "Lịch khám vừa được cập nhật tự động."
                    : available ? "Chọn một khung giờ còn trống." : "Các khung giờ trong ngày này đã kín."
                : "Bác sĩ chưa có lịch làm việc trong ngày đã chọn.";
            // Keep the user-facing feedback stable during a background sync.
            // The slot grid itself still reflects any real availability change.
            if (!realtime) setFeedback({ tone: "info", text });
            return own;
        } catch (error) {
            clinicClosureNoticeKeyRef.current = "";
            setClinicClosureReason(null);
            setClinicClosureNotice(null);
            setFeedback({ tone: "error", text: (error as Error).message });
            return undefined;
        } finally {
            slotRequestInFlight.current = false;
            if (!realtime) setBusy(false);
        }
    }

    useEffect(() => {
        if (doctorId && date) void findSlots();
    }, [doctorId, date]);

    useEffect(() => {
        if (!doctorId || !date) return;
        let live = true;
        const refresh = () => { if (live && !document.hidden) void findSlots(true); };
        const unsubscribe = subscribeRealtime(event => {
            if (event.type === "SLOTS_CHANGED") refresh();
        });
        const doctorUpdated = (event: Event) => {
            const doctorIdFromEvent = (event as CustomEvent<{ doctorId?: string }>).detail?.doctorId;
            if (!doctorIdFromEvent || doctorIdFromEvent === doctorId) refresh();
        };
        window.addEventListener("doctor-profiles-changed", doctorUpdated);
        // WebSocket is the primary update source. This sparse fallback only
        // recovers after a missed frame, sleep, or a network change.
        const fallback = window.setInterval(refresh, 30_000);
        window.addEventListener("focus", refresh);
        document.addEventListener("visibilitychange", refresh);
        return () => {
            live = false;
            unsubscribe();
            window.clearInterval(fallback);
            window.removeEventListener("focus", refresh);
            document.removeEventListener("visibilitychange", refresh);
            window.removeEventListener("doctor-profiles-changed", doctorUpdated);
        };
    }, [doctorId, date]);

    useEffect(() => {
        if (!holdUntil) return;
        const timer = window.setInterval(() => setHoldClock(Date.now()), 1000);
        const expiry = window.setTimeout(() => {
            void releaseHold()
                .then(() => findSlots(true))
                .finally(() => setFeedback({
                    tone: "error",
                    text: "Thời gian giữ chỗ đã hết. Vui lòng chọn lại khung giờ."
                }));
        }, Math.max(0, new Date(holdUntil).getTime() - Date.now()) + 250);
        return () => {
            window.clearInterval(timer);
            window.clearTimeout(expiry);
        };
    }, [holdUntil]);

    async function releaseHold() {
        if (!holdId) return;
        const id = holdId;
        setHoldId("");
        setHoldUntil("");
        setHeldFee(null);
        setSelected(null);
        await request("/appointments/holds/" + id, token, { method: "DELETE" }).catch(() => undefined);
    }

    async function holdSlot(slot: AvailabilitySlot) {
        if (busy) return;
        if (slot.status === "HELD_BY_YOU") {
            setBusy(true);
            try {
                await releaseHold();
                await findSlots(true);
                setFeedback({ tone: "info", text: "Đã nhả khung giờ. Người khác có thể đặt giờ này." });
            } finally {
                setBusy(false);
            }
            return;
        }
        if (slot.status !== "AVAILABLE") return;
        setBusy(true);
        try {
            await releaseHold();
            const held = await request<Appointment>("/appointments/holds", token, {
                method: "POST",
                body: JSON.stringify({
                    patientId: patient.id,
                    doctorId: slot.doctorId,
                    doctorIdentityId: slot.doctorIdentityId,
                    startAt: slot.startAt,
                    endAt: slot.endAt
                })
            });
            setSelected({ ...slot, status: "HELD_BY_YOU", holdId: held.id, holdExpiresAt: held.holdExpiresAt });
            setHoldId(held.id);
            // Reset the UI clock at the moment the server creates this hold.
            setHoldClock(Date.now());
            setHoldUntil(held.holdExpiresAt || "");
            // Show the exact server-side quote retained by this hold, even if Admin changes the doctor's price meanwhile.
            setHeldFee(held.consultationFeeSnapshot ?? null);
            setFeedback({ tone: "success", text: "Khung giờ được giữ riêng cho bạn trong 5 phút." });
        } catch (error) {
            const own = await findSlots(true);
            if (own && own.startAt === slot.startAt) {
                setFeedback({ tone: "success", text: "Khung giờ đã được giữ cho bạn. Hãy nhập lý do khám và xác nhận đặt lịch." });
            } else {
                setFeedback({ tone: "error", text: (error as Error).message });
            }
        } finally {
            setBusy(false);
        }
    }

    async function chooseSlot(slot: AvailabilitySlot) {
        if (busy) return;
        if (slot.status === "HELD_BY_YOU") {
            await holdSlot(slot);
            return;
        }
        if (slot.status !== "AVAILABLE") return;
        setBusy(true);
        try {
            const latest = await request<Appointment[]>("/appointments/mine", token);
            setItems(latest);
            changed(latest);
            const upcoming = activeUpcoming(latest);
            const overlapping = upcoming.find(item =>
                item.doctorId !== slot.doctorId
                && new Date(item.startAt).getTime() < new Date(slot.endAt).getTime()
                && new Date(item.endAt).getTime() > new Date(slot.startAt).getTime()
            );
            if (overlapping) {
                const bookedDoctor = doctors.find(item => item.id === overlapping.doctorId);
                setTimeConflict({
                    slot,
                    existing: overlapping,
                    doctorName: bookedDoctor?.fullName || overlapping.doctorName || "bác sĩ khác"
                });
                return;
            }
            const sameDoctorDay = upcoming.find(item =>
                item.doctorId === slot.doctorId && clinicDate(item.startAt) === clinicDate(slot.startAt)
            );
            if (sameDoctorDay) {
                setDuplicateBooking({ slot, existing: sameDoctorDay });
                return;
            }
            if (upcoming.length >= 3) {
                setFeedback({
                    tone: "error",
                    text: "Bạn đã có tối đa 3 lịch khám sắp tới. Vui lòng hoàn thành hoặc hủy một lịch trước khi đặt thêm."
                });
                return;
            }
            if (upcoming.length > 0) {
                setPendingSlot(slot);
                return;
            }
        } catch (error) {
            setFeedback({ tone: "error", text: (error as Error).message });
            return;
        } finally {
            setBusy(false);
        }
        await holdSlot(slot);
    }

    async function confirmAdditionalBooking() {
        const slot = pendingSlot;
        setPendingSlot(null);
        if (slot) await holdSlot(slot);
    }

    function chooseAnotherDate() {
        setDuplicateBooking(null);
        window.setTimeout(() => document.querySelector<HTMLInputElement>("#booking-date")?.focus(), 0);
    }

    function chooseAnotherDateFromClosure() {
        setClinicClosureNotice(null);
        window.setTimeout(() => document.querySelector<HTMLInputElement>("#booking-date")?.focus(), 0);
    }

    function chooseAnotherTime() {
        setTimeConflict(null);
        window.setTimeout(() => {
            document.querySelector<HTMLButtonElement>(".booking-slot-grid button:not(:disabled)")?.focus();
        }, 0);
    }

    async function book() {
        if (!selected || !holdId || !reason.trim()) return;
        setBusy(true);
        try {
            const booked = await request<Appointment>("/appointments/holds/" + holdId + "/confirm", token, {
                method: "POST",
                headers: { "Idempotency-Key": crypto.randomUUID() },
                body: JSON.stringify({ reason: reason.trim() })
            });
            if (sharedAi) {
                await request("/patients/me/ai-assessments/" + sharedAi.id + "/sharing", token, {
                    method: "PATCH",
                    body: JSON.stringify({ sharedWithDoctor: true, appointmentId: booked.id })
                });
            }
            const latest = await request<Appointment[]>("/appointments/mine", token);
            setItems(latest);
            changed(latest);
            setReason("");
            setSharedAi(null);
            setSelected(null);
            setHoldId("");
            setHoldUntil("");
            await findSlots(true);
            setFeedback({
                tone: "success",
                text: sharedAi
                    ? "Đã gửi yêu cầu đặt lịch và chia sẻ riêng kết quả AI với bác sĩ phụ trách."
                    : "Đã gửi yêu cầu đặt lịch. Bạn có thể theo dõi trạng thái ở danh sách bên dưới."
            });
        } catch (error) {
            await findSlots(true);
            setFeedback({ tone: "error", text: (error as Error).message });
        } finally {
            setBusy(false);
        }
    }

    async function clearSharedAi() {
        if (!sharedAi) return;
        await request("/patients/me/ai-assessments/" + sharedAi.id + "/sharing", token, {
            method: "PATCH", body: JSON.stringify({ sharedWithDoctor: false })
        }).catch(() => undefined);
        setSharedAi(null);
        setReason(value => value.startsWith("Kết quả kiểm tra da bằng AI") ? "" : value);
        setFeedback({ tone: "info", text: "Đã bỏ kết quả AI khỏi yêu cầu đặt lịch." });
    }

    async function cancel(id: string, cancelReason: string) {
        await request("/appointments/" + id + "/cancel", token, {
            method: "POST", body: JSON.stringify({ reason: cancelReason })
        });
        const latest = await request<Appointment[]>("/appointments/mine", token);
        setItems(latest);
        changed(latest);
    }

    async function hide(id: string) {
        await request("/appointments/" + id + "/hide", token, { method: "PATCH" });
        const latest = await request<Appointment[]>("/appointments/mine", token);
        setItems(latest);
        changed(latest);
    }

    return (
        <>
            {timeConflict && (
                <BookingDialog
                    tone="danger"
                    title="Bạn đã có lịch vào giờ này"
                    titleId="time-conflict-title"
                    descriptionId="time-conflict-description"
                    primaryLabel="Chọn giờ khác"
                    secondaryLabel="Đóng"
                    onPrimary={chooseAnotherTime}
                    onClose={() => setTimeConflict(null)}
                >
                    <p>
                        Lịch với <strong>BS. {timeConflict.doctorName}</strong> từ{" "}
                        <strong>{formatTime(timeConflict.existing.startAt)}</strong> đến{" "}
                        <strong>{formatTime(timeConflict.existing.endAt)}</strong> trùng với khung giờ vừa chọn.
                    </p>
                    <p>Một bệnh nhân không thể khám hai bác sĩ cùng lúc.</p>
                </BookingDialog>
            )}
            {duplicateBooking && (
                <BookingDialog
                    title="Bạn đã đặt lịch với bác sĩ này"
                    titleId="duplicate-doctor-title"
                    descriptionId="duplicate-doctor-description"
                    primaryLabel="Chọn ngày khác"
                    secondaryLabel="Đóng"
                    onPrimary={chooseAnotherDate}
                    onClose={() => setDuplicateBooking(null)}
                >
                    <p>
                        Bạn đã có lịch với <strong>BS. {duplicateBooking.slot.doctorName}</strong>{" "}
                        vào <strong>{formatDateTime(duplicateBooking.existing.startAt)}</strong>.
                    </p>
                    <p>Mỗi bác sĩ chỉ được đặt một lịch trong cùng ngày.</p>
                </BookingDialog>
            )}
            {pendingSlot && (
                <BookingDialog
                    title={"Bạn đang có " + upcomingCount + " lịch sắp tới"}
                    titleId="additional-booking-title"
                    descriptionId="additional-booking-description"
                    primaryLabel="Vẫn đặt thêm"
                    secondaryLabel="Quay lại"
                    onPrimary={() => void confirmAdditionalBooking()}
                    onClose={() => setPendingSlot(null)}
                    note="Tối đa 3 lịch sắp tới. Không thể đặt trùng giờ hoặc cùng bác sĩ hai lần trong một ngày."
                >
                    <p>
                        Bạn vẫn muốn đặt thêm lịch với <strong>BS. {pendingSlot.doctorName}</strong>{" "}
                        vào <strong>{formatDateTime(pendingSlot.startAt)}</strong>?
                    </p>
                </BookingDialog>
            )}
            {clinicClosureNotice && (
                <BookingDialog
                    title="Phòng khám tạm nghỉ"
                    titleId="clinic-closure-title"
                    descriptionId="clinic-closure-description"
                    primaryLabel="Chọn ngày khác"
                    secondaryLabel="Đã hiểu"
                    onPrimary={chooseAnotherDateFromClosure}
                    onClose={() => setClinicClosureNotice(null)}
                >
                    <p>Phòng khám không nhận lịch trong ngày <strong>{formatDateInput(date)}</strong>.</p>
                    <p>Lý do: <strong>{clinicClosureNotice}</strong></p>
                    <p>Vui lòng chọn một ngày khác để tiếp tục đặt lịch.</p>
                </BookingDialog>
            )}

            <div className="patient-booking">
                <header className="booking-page-heading">
                    <div>
                        <h2>Đặt lịch khám da liễu</h2>
                        <p>Chọn lần lượt bác sĩ, ngày và khung giờ phù hợp với bạn.</p>
                    </div>
                    <span><CalendarDays aria-hidden="true" />Tối đa 60 ngày</span>
                </header>

                <section className="booking-layout" aria-label="Thông tin đặt lịch">
                    <div className="booking-flow">
                        <section className="booking-step" aria-labelledby="doctor-step-title">
                            <div className="booking-step-heading">
                                <span aria-hidden="true">1</span>
                                <div>
                                    <h3 id="doctor-step-title">Chọn bác sĩ</h3>
                                    <p>Xem chuyên môn và kinh nghiệm trước khi chọn.</p>
                                </div>
                            </div>
                            {doctors.length === 0 ? (
                                <div className="booking-state booking-state-loading" role="status">
                                    <span className="booking-skeleton booking-skeleton-avatar" />
                                    <span className="booking-skeleton" />
                                    <span>Đang tải danh sách bác sĩ...</span>
                                </div>
                            ) : (
                                <div className="booking-doctor-selector" aria-label="Danh sách bác sĩ">
                                    {doctors.map(item => (
                                        <button
                                            key={item.id}
                                            type="button"
                                            className={doctorId === item.id ? "is-selected" : ""}
                                            aria-pressed={doctorId === item.id}
                                            onClick={() => {
                                                setPendingSlot(null);
                                                setDuplicateBooking(null);
                                                setTimeConflict(null);
                                                setDoctorId(item.id);
                                                void releaseHold();
                                            }}
                                        >
                                            {item.avatarUrl ? (
                                                <img src={item.avatarUrl} alt={"Ảnh BS. " + item.fullName} />
                                            ) : (
                                                <span aria-hidden="true">{item.fullName.slice(0, 1).toUpperCase()}</span>
                                            )}
                                            <div>
                                                <strong>BS. {item.fullName}</strong>
                                                <small>{item.specialtyCode}</small>
                                                <em>{item.experienceYears} năm kinh nghiệm</em>
                                                <span className="booking-doctor-fee">{formatVnd(item.consultationFee)} / lượt</span>
                                            </div>
                                            <CheckCircle2 aria-hidden="true" />
                                        </button>
                                    ))}
                                </div>
                            )}

                            {/* Hồ sơ ngắn giúp bệnh nhân hiểu bác sĩ trước khi chọn lịch. */}
                            {doctor && (
                                <div className="booking-doctor-description" aria-live="polite">
                                    <strong>Giới thiệu BS. {doctor.fullName}</strong>
                                    <p>{doctor.bio?.trim() || "Bác sĩ chưa cập nhật phần giới thiệu chuyên môn."}</p>
                                    <span className="booking-selected-fee">
                                        Giá khám cơ bản: <strong>{formatVnd(doctor.consultationFee)}</strong>
                                    </span>
                                    {doctor.certificateNo && (
                                        <small>Số chứng chỉ hành nghề: {doctor.certificateNo}</small>
                                    )}
                                </div>
                            )}
                        </section>

                        <section className="booking-step" aria-labelledby="date-step-title">
                            <div className="booking-step-heading">
                                <span aria-hidden="true">2</span>
                                <div>
                                    <h3 id="date-step-title">Chọn ngày khám</h3>
                                    <p>Có thể đặt lịch từ hôm nay đến 60 ngày tiếp theo.</p>
                                </div>
                            </div>
                            <div className="booking-field booking-date-field">
                                <label htmlFor="booking-date">Ngày muốn khám</label>
                                <input
                                    id="booking-date"
                                    type="date"
                                    min={clinicDateInput()}
                                    max={clinicDateInput(60)}
                                    value={date}
                                    onChange={event => {
                                        setPendingSlot(null);
                                        setDuplicateBooking(null);
                                        setTimeConflict(null);
                                        setDate(event.target.value);
                                        void releaseHold();
                                    }}
                                />
                                <small>Khung giờ được hiển thị theo giờ Việt Nam.</small>
                            </div>
                        </section>

                        <section className="booking-step" aria-labelledby="time-step-title">
                            <div className="booking-step-heading">
                                <span aria-hidden="true">3</span>
                                <div>
                                    <h3 id="time-step-title">Chọn khung giờ</h3>
                                    <p>Thời lượng theo lịch bác sĩ đã thiết lập.</p>
                                </div>
                            </div>
                            <div className="booking-slot-legend" aria-label="Chú thích trạng thái">
                                <span>Còn trống</span>
                                <span>Bạn đang giữ</span>
                                <span>Không thể chọn</span>
                            </div>
                            <div className="booking-slot-grid" aria-busy={busy} aria-label="Các khung giờ khám">
                                {busy && slots.length === 0 ? (
                                    <div className="booking-slot-loading" role="status">
                                        <span>Đang kiểm tra lịch bác sĩ...</span>
                                        {Array.from({ length: 8 }, (_, index) => <i key={index} aria-hidden="true" />)}
                                    </div>
                                ) : clinicClosureReason !== null ? (
                                    <div className="booking-state booking-state-empty" role="status">
                                        <CalendarDays aria-hidden="true" />
                                        <strong>Phòng khám nghỉ trong ngày này</strong>
                                        <span>Lý do: {clinicClosureReason} Vui lòng chọn ngày khác.</span>
                                    </div>
                                ) : slots.length === 0 ? (
                                    <div className="booking-state booking-state-empty">
                                        <Clock3 aria-hidden="true" />
                                        <strong>Chưa có khung giờ</strong>
                                        <span>Hãy thử chọn ngày khác hoặc bác sĩ khác.</span>
                                    </div>
                                ) : slots.every(slot => slot.status === "ON_LEAVE") ? (
                                    <div className="booking-state booking-state-empty" role="status">
                                        <Clock3 aria-hidden="true" />
                                        <strong>Bác sĩ nghỉ trong ngày này</strong>
                                        <span>Không có khung giờ nào có thể đặt. Hãy chọn ngày hoặc bác sĩ khác.</span>
                                    </div>
                                ) : (
                                    slots.map(slot => {
                                        const unavailable = !["AVAILABLE", "HELD_BY_YOU"].includes(slot.status);
                                        const statusClass = slot.status.toLowerCase().replaceAll("_", "-");
                                        const label = slotLabel(slot.status, holdCountdown);
                                        return (
                                            <button
                                                key={slot.startAt}
                                                type="button"
                                                disabled={unavailable}
                                                className={[
                                                    selected?.startAt === slot.startAt ? "is-selected" : "",
                                                    statusClass
                                                ].filter(Boolean).join(" ")}
                                                aria-pressed={selected?.startAt === slot.startAt}
                                                aria-label={formatTime(slot.startAt) + ", " + label}
                                                onClick={() => void chooseSlot(slot)}
                                            >
                                                <strong>{formatTime(slot.startAt)}</strong>
                                                <small>{label}</small>
                                            </button>
                                        );
                                    })
                                )}
                            </div>
                        </section>

                        <section className="booking-step" aria-labelledby="reason-step-title">
                            <div className="booking-step-heading">
                                <span aria-hidden="true">4</span>
                                <div>
                                    <h3 id="reason-step-title">Nhập lý do khám</h3>
                                    <p>Mô tả ngắn triệu chứng để bác sĩ chuẩn bị tốt hơn.</p>
                                </div>
                            </div>
                            <div className="booking-field">
                                <label htmlFor="booking-reason">Triệu chứng hoặc nhu cầu thăm khám</label>
                                <textarea
                                    id="booking-reason"
                                    required
                                    maxLength={1000}
                                    aria-describedby="booking-reason-help"
                                    value={reason}
                                    onChange={event => setReason(event.target.value)}
                                    placeholder="Ví dụ: nổi mẩn đỏ, ngứa da trong 3 ngày"
                                />
                                <small id="booking-reason-help">Không nhập thông tin không liên quan đến việc thăm khám.</small>
                            </div>
                            {sharedAi && (
                                <div className="ai-booking-context">
                                    <BrainCircuit aria-hidden="true" />
                                    <div>
                                        <strong>Đính kèm kết quả AI tham khảo</strong>
                                        <small>
                                            {patientAiLabel(sharedAi.predictedLabel)} · {formatAiPercentage(sharedAi.confidence)} · phiên bản {sharedAi.modelVersion}
                                        </small>
                                    </div>
                                    <button type="button" onClick={() => void clearSharedAi()}>Bỏ đính kèm</button>
                                </div>
                            )}
                        </section>
                    </div>

                    <aside className="booking-review" aria-labelledby="booking-review-title">
                        <div className="booking-review-heading">
                            <span aria-hidden="true"><Stethoscope /></span>
                            <div>
                                <h3 id="booking-review-title">Xem lại lịch hẹn</h3>
                                <p>Kiểm tra thông tin trước khi xác nhận.</p>
                            </div>
                        </div>
                        <dl>
                            <div><dt>Bác sĩ</dt><dd>{doctor ? "BS. " + doctor.fullName : "Chưa chọn"}</dd></div>
                            <div>
                                <dt>Ngày khám</dt>
                                <dd>{date ? new Date(date + "T00:00:00").toLocaleDateString("vi-VN") : "Chưa chọn"}</dd>
                            </div>
                            <div><dt>Khung giờ</dt><dd>{selected ? formatTime(selected.startAt) : "Chưa chọn"}</dd></div>
                            <div><dt>Giá khám</dt><dd>{doctor ? formatVnd(heldFee ?? doctor.consultationFee) : "Chưa chọn bác sĩ"}</dd></div>
                            <div><dt>Lý do khám</dt><dd className="booking-review-reason">{reason.trim() || "Chưa nhập"}</dd></div>
                        </dl>
                        {holdUntil && (
                            <div className="booking-hold-status" role="status" aria-live="polite">
                                <Clock3 aria-hidden="true" />
                                <span>Giữ riêng trong <strong>{holdCountdown}</strong>. Nhấn lại khung giờ để nhả chỗ.</span>
                            </div>
                        )}
                        <button
                            type="button"
                            className="booking-confirm"
                            disabled={busy || !selected || !reason.trim() || !holdId}
                            onClick={() => void book()}
                        >
                            {busy && selected ? "Đang xử lý..." : "Xác nhận đặt lịch"}
                        </button>
                        <small className="booking-payment-note">Thanh toán trực tiếp tại phòng khám.</small>
                        {(!selected || !reason.trim()) && (
                            <small className="booking-confirm-help">
                                {!selected ? "Chọn một khung giờ để tiếp tục." : "Nhập lý do khám để xác nhận."}
                            </small>
                        )}
                        {feedback && (
                            <div
                                className={"booking-feedback booking-feedback-" + feedback.tone}
                                role={feedback.tone === "error" ? "alert" : "status"}
                                aria-live={feedback.tone === "error" ? "assertive" : "polite"}
                            >
                                {feedback.text}
                            </div>
                        )}
                    </aside>
                </section>

                <AppointmentList
                    token={token}
                    appointments={items}
                    cancel={cancel}
                    hide={hide}
                    patientName={patient.fullName}
                    onBookNew={() => {
                        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
                        document.querySelector(".booking-page-heading")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
                        window.setTimeout(() => document.querySelector<HTMLButtonElement>(".booking-doctor-selector button")?.focus(), 250);
                    }}
                />
            </div>
        </>
    );
}
