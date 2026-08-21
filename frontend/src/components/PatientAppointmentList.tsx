import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, ChevronDown, ChevronUp, CircleAlert, MessageCircle, Search, Trash2, X } from "lucide-react";
import { request } from "../core/api";
import { formatVnd } from "../core/currency";
import {
    canPatientSelfManageAppointment,
    isStaleInProgressAppointment,
    patientAppointmentSelfServiceClosesAt,
} from "../core/appointmentPolicy";
import type { Appointment, ClinicReview, Recommendation, RecommendationResult } from "../core/types";
import AccessibleDialog from "./AccessibleDialog";
import { EmptyState } from "./Ui";

type AppointmentListProps = {
    appointments: Appointment[];
    token?: string;
    cancel?: (id: string, reason: string) => Promise<void>;
    reschedule?: (id: string, value: string) => Promise<void>;
    bookFollowUp?: (id: string, slot: Recommendation) => Promise<void>;
    hide?: (id: string) => Promise<void>;
    patientName?: string;
    onBookNew?: () => void;
};

const PATIENT_HIDEABLE_STATUSES = new Set(["CANCELLED", "COMPLETED", "NO_SHOW"]);
const APPOINTMENT_PAGE_SIZE = 5;

export function canHideAppointmentFromHistory(status: string) {
    return PATIENT_HIDEABLE_STATUSES.has(status);
}

function formatAppointmentTime(iso: string) {
    if (!iso) return "";
    const date = new Date(iso);
    const time = date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
    const day = date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
    return time + " · " + day;
}

export function statusDetails(status: string) {
    switch (status) {
        case "PROPOSED": return { label: "Chờ bạn xác nhận", className: "is-proposed" };
        case "PENDING": return { label: "Chờ tiếp nhận", className: "is-pending" };
        case "ASSIGNED": return { label: "Đã xếp bác sĩ", className: "is-assigned" };
        case "CONFIRMED": return { label: "Đã xác nhận", className: "is-confirmed" };
        case "CHECKED_IN": return { label: "Đã đến phòng khám", className: "is-checked-in" };
        case "IN_PROGRESS": return { label: "Đang khám", className: "is-in-progress" };
        case "COMPLETED": return { label: "Đã hoàn thành", className: "is-completed" };
        case "CANCELLED": return { label: "Đã hủy", className: "is-cancelled" };
        case "FOLLOW_UP_REQUIRED": return { label: "Cần tái khám", className: "is-follow-up" };
        case "NO_SHOW": return { label: "Không đến khám", className: "is-cancelled" };
        default: return { label: status, className: "is-default" };
    }
}

export function AppointmentStatusBadge({ status, awaitingClinicUpdate = false }: { status: string; awaitingClinicUpdate?: boolean }) {
    if (awaitingClinicUpdate) {
        return <span className="appointment-status is-clinic-update">Chờ phòng khám cập nhật</span>;
    }
    const details = statusDetails(status);
    return <span className={"appointment-status " + details.className}>{details.label}</span>;
}

export function CancelAppointmentControl({ submit }: { submit: (reason: string) => Promise<void> }) {
    const [open, setOpen] = useState(false);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    async function confirmCancel() {
        if (!reason.trim()) return;
        setBusy(true);
        setError("");
        try {
            await submit(reason.trim());
            setOpen(false);
            setReason("");
        } catch (cause) {
            setError((cause as Error).message);
        } finally {
            setBusy(false);
        }
    }

    if (!open) {
        return <button type="button" className="appointment-action-danger" onClick={() => setOpen(true)}>Hủy lịch</button>;
    }

    return (
        <div className="appointment-inline-form">
            <label>
                Lý do hủy
                <input
                    required
                    maxLength={500}
                    value={reason}
                    onChange={event => setReason(event.target.value)}
                    placeholder="Nhập lý do hủy lịch"
                />
            </label>
            <div>
                <button type="button" disabled={busy || !reason.trim()} onClick={() => void confirmCancel()}>
                    {busy ? "Đang hủy..." : "Xác nhận hủy"}
                </button>
                <button type="button" onClick={() => { setOpen(false); setError("") }}>Đóng</button>
            </div>
            {error && <small role="alert">{error}</small>}
        </div>
    );
}

export function RescheduleAppointmentControl({
    token,
    appointment,
    submit
}: {
    token: string;
    appointment: Appointment;
    submit: (value: string) => Promise<void>;
}) {
    const [open, setOpen] = useState(false);
    const [value, setValue] = useState("");
    const [slots, setSlots] = useState<Recommendation[]>([]);
    const [message, setMessage] = useState("");

    async function find() {
        if (!appointment.doctorId) {
            await submit(value);
            setOpen(false);
            return;
        }
        try {
            const result = await request<RecommendationResult>("/appointments/recommendations", token, {
                method: "POST",
                body: JSON.stringify({
                    patientId: appointment.patientId,
                    preferredDoctorId: appointment.doctorId,
                    preferredStart: new Date(value).toISOString(),
                    durationMinutes: Math.round((new Date(appointment.endAt).getTime() - new Date(appointment.startAt).getTime()) / 60000),
                    limit: 5
                })
            });
            setSlots(result.items);
            setMessage(result.items.length ? "Chọn một giờ đã được kiểm tra." : "Không có giờ phù hợp trong 7 ngày.");
        } catch (cause) {
            setMessage((cause as Error).message);
        }
    }

    if (!open) return <button type="button" onClick={() => setOpen(true)}>Đổi lịch</button>;
    return (
        <div className="appointment-inline-form">
            <label>
                Thời gian mong muốn
                <input type="datetime-local" required value={value} onChange={event => {
                    setValue(event.target.value);
                    setSlots([]);
                }} />
            </label>
            <div>
                <button type="button" disabled={!value} onClick={() => void find()}>
                    {appointment.doctorId ? "Tìm giờ" : "Lưu"}
                </button>
                <button type="button" onClick={() => setOpen(false)}>Đóng</button>
            </div>
            {message && <small role="status">{message}</small>}
            {slots.map(slot => (
                <button type="button" className="appointment-recommended-slot" key={slot.startAt} onClick={async () => {
                    await submit(slot.startAt);
                    setOpen(false);
                }}>
                    {formatAppointmentTime(slot.startAt)}
                </button>
            ))}
        </div>
    );
}

function FollowUpControl({
    token,
    appointment,
    submit
}: {
    token: string;
    appointment: Appointment;
    submit: (slot: Recommendation) => Promise<void>;
}) {
    const [open, setOpen] = useState(false);
    const [value, setValue] = useState("");
    const [slots, setSlots] = useState<Recommendation[]>([]);
    const [message, setMessage] = useState("");
    const minimum = appointment.followUpNotBefore
        ? new Date(appointment.followUpNotBefore).toISOString().slice(0, 16)
        : undefined;

    async function find() {
        try {
            const result = await request<RecommendationResult>("/appointments/recommendations", token, {
                method: "POST",
                body: JSON.stringify({
                    patientId: appointment.patientId,
                    preferredDoctorId: appointment.doctorId,
                    preferredStart: new Date(value).toISOString(),
                    durationMinutes: 30,
                    limit: 5
                })
            });
            setSlots(result.items);
            setMessage(result.items.length ? "Chọn giờ tái khám phù hợp." : "Không có giờ trống trong 7 ngày.");
        } catch (cause) {
            setMessage((cause as Error).message);
        }
    }

    if (!open) return <button type="button" onClick={() => setOpen(true)}>Chọn giờ tái khám</button>;
    return (
        <div className="appointment-inline-form">
            <p><strong>Lý do:</strong> {appointment.followUpReason || "Bác sĩ yêu cầu tái khám"}</p>
            <label>
                Thời gian mong muốn
                <input type="datetime-local" required min={minimum} value={value} onChange={event => {
                    setValue(event.target.value);
                    setSlots([]);
                }} />
            </label>
            <div>
                <button type="button" disabled={!value} onClick={() => void find()}>Tìm giờ</button>
                <button type="button" onClick={() => setOpen(false)}>Đóng</button>
            </div>
            {message && <small role="status">{message}</small>}
            {slots.map(slot => (
                <button type="button" className="appointment-recommended-slot" key={slot.startAt} onClick={async () => {
                    await submit(slot);
                    setOpen(false);
                }}>
                    {formatAppointmentTime(slot.startAt)}
                </button>
            ))}
        </div>
    );
}

function AppointmentReviewControl({
    token,
    appointmentId,
    patientName
}: {
    token: string;
    appointmentId: string;
    patientName: string;
}) {
    const [open, setOpen] = useState(false);
    const [rating, setRating] = useState(5);
    const [comment, setComment] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const [message, setMessage] = useState<{ text: string; tone: "success" | "error" } | null>(null);

    useEffect(() => {
        request<ClinicReview[]>("/appointments/reviews/mine", token)
            .then(items => setSubmitted(items.some(item => item.appointmentId === appointmentId)))
            .catch(() => undefined);
    }, [appointmentId, token]);

    async function submit(event: FormEvent) {
        event.preventDefault();
        try {
            await request("/appointments/reviews/" + appointmentId, token, {
                method: "PUT",
                body: JSON.stringify({ rating, comment, displayName: patientName })
            });
            setSubmitted(true);
            setOpen(false);
            // Patient only needs confirmation that the review was received; moderation remains internal.
            setMessage({ text: "Cảm ơn bạn đã gửi đánh giá.", tone: "success" });
        } catch (cause) {
            setMessage({ text: (cause as Error).message, tone: "error" });
        }
    }

    return (
        <div className={"appointment-review-control" + (open ? " is-open" : "")}>
            {submitted ? (
                <button type="button" disabled>Đã đánh giá</button>
            ) : open ? (
                <form onSubmit={submit}>
                    <label>
                        Mức độ hài lòng
                        <select value={rating} onChange={event => setRating(Number(event.target.value))}>
                            {[5, 4, 3, 2, 1].map(value => <option key={value} value={value}>{value} sao</option>)}
                        </select>
                    </label>
                    <label>
                        Chia sẻ trải nghiệm
                        <textarea
                            required
                            minLength={5}
                            maxLength={1000}
                            value={comment}
                            onChange={event => setComment(event.target.value)}
                            placeholder="Nhập nhận xét của bạn"
                        />
                    </label>
                    <div>
                        <button type="submit">Gửi đánh giá</button>
                        <button type="button" onClick={() => setOpen(false)}>Đóng</button>
                    </div>
                </form>
            ) : (
                <button type="button" onClick={() => { setMessage(null); setOpen(true); }}>Đánh giá phòng khám</button>
            )}
            {message && (
                <small
                    className={"appointment-review-feedback is-" + message.tone}
                    role={message.tone === "error" ? "alert" : "status"}
                    aria-live="polite"
                >
                    {message.tone === "success" ? <CheckCircle2 aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
                    {message.text}
                </small>
            )}
        </div>
    );
}

export function DeleteAppointmentControl({
    appointment,
    submit,
}: {
    appointment: Appointment;
    submit: () => Promise<void>;
}) {
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const titleId = "delete-appointment-title-" + appointment.id;
    const appointmentTime = formatAppointmentTime(appointment.startAt);

    async function confirmDelete() {
        setBusy(true);
        setError("");
        try {
            await submit();
            setOpen(false);
        } catch (cause) {
            setError((cause as Error).message);
        } finally {
            setBusy(false);
        }
    }

    return (
        <>
            <button
                type="button"
                className="appointment-delete-action"
                title="Xóa khỏi danh sách"
                aria-label={"Xóa lịch " + appointmentTime + " khỏi danh sách"}
                aria-haspopup="dialog"
                aria-expanded={open}
                onClick={() => { setError(""); setOpen(true); }}
            >
                <Trash2 aria-hidden="true" />
            </button>
            {open && (
                <AccessibleDialog
                    role="alertdialog"
                    tone="danger"
                    title="Bạn có chắc muốn xóa lịch này?"
                    titleId={titleId}
                    icon={<Trash2 />}
                    closeDisabled={busy}
                    closeOnBackdrop={!busy}
                    onClose={() => { if (!busy) setOpen(false); }}
                    footer={(
                        <>
                            <button
                                type="button"
                                data-dialog-initial-focus
                                disabled={busy}
                                onClick={() => setOpen(false)}
                            >
                                Giữ lại
                            </button>
                            <button
                                type="button"
                                className="appointment-delete-confirm"
                                disabled={busy}
                                onClick={() => void confirmDelete()}
                            >
                                {busy ? "Đang xóa..." : "Xóa khỏi danh sách"}
                            </button>
                        </>
                    )}
                >
                    {error && <p className="appointment-delete-error" role="alert">{error}</p>}
                </AccessibleDialog>
            )}
        </>
    );
}

export default function PatientAppointmentList({
    appointments,
    token,
    cancel,
    reschedule,
    bookFollowUp,
    hide,
    patientName = "Bệnh nhân",
    onBookNew,
}: AppointmentListProps) {
    const [searchKw, setSearchKw] = useState("");
    const [statusFilter, setStatusFilter] = useState("ALL");
    const [dateFilter, setDateFilter] = useState("ALL");
    const [selfServiceNow, setSelfServiceNow] = useState(Date.now());
    const [visibleCount, setVisibleCount] = useState(APPOINTMENT_PAGE_SIZE);

    // Switch to receptionist support as soon as the nearest 30-minute window closes.
    useEffect(() => {
        const now = Date.now();
        const nearestClosingTime = appointments
            .filter(item => ["PENDING", "ASSIGNED"].includes(item.status))
            .map(item => patientAppointmentSelfServiceClosesAt(item.createdAt))
            .filter(closesAt => Number.isFinite(closesAt) && closesAt >= now)
            .sort((left, right) => left - right)[0];
        if (nearestClosingTime === undefined) return;
        const timer = window.setTimeout(
            () => setSelfServiceNow(Date.now()),
            Math.max(0, nearestClosingTime - now + 25),
        );
        return () => window.clearTimeout(timer);
    }, [appointments, selfServiceNow]);

    const filtered = appointments.filter(item => {
        const keyword = searchKw.trim().toLowerCase();
        if (keyword && !(item.reason || "").toLowerCase().includes(keyword)
            && !(item.followUpReason || "").toLowerCase().includes(keyword)) return false;
        if (statusFilter !== "ALL" && item.status !== statusFilter) return false;
        if (dateFilter === "TODAY" && new Date(item.startAt).toDateString() !== new Date().toDateString()) return false;
        if (dateFilter === "UPCOMING" && new Date(item.startAt).getTime() < Date.now()) return false;
        if (dateFilter === "PAST" && new Date(item.startAt).getTime() >= Date.now()) return false;
        return true;
    });
    const visibleAppointments = filtered.slice(0, visibleCount);
    const remainingAppointments = Math.max(0, filtered.length - visibleAppointments.length);

    // A new search or filter starts from a compact five-row view again.
    useEffect(() => setVisibleCount(APPOINTMENT_PAGE_SIZE), [searchKw, statusFilter, dateFilter]);

    return (
        <section className="patient-appointment-history" aria-labelledby="appointment-history-title">
            <header className="appointment-history-heading">
                <div>
                    <h2 id="appointment-history-title">Lịch đã đặt</h2>
                    <p>Theo dõi trạng thái, đổi lịch hoặc liên hệ lễ tân khi cần.</p>
                </div>
                <span aria-live="polite">{filtered.length} lịch</span>
            </header>

            {appointments.length > 0 && (
                <div className="appointment-filters" aria-label="Bộ lọc lịch khám">
                    <div className="appointment-search">
                        <Search aria-hidden="true" />
                        <label className="visually-hidden" htmlFor="appointment-search">Tìm theo lý do khám</label>
                        <input
                            id="appointment-search"
                            type="search"
                            value={searchKw}
                            onChange={event => setSearchKw(event.target.value)}
                            placeholder="Tìm theo lý do khám"
                        />
                        {searchKw && (
                            <button type="button" aria-label="Xóa nội dung tìm kiếm" onClick={() => setSearchKw("")}>
                                <X aria-hidden="true" />
                            </button>
                        )}
                    </div>
                    <label>
                        Trạng thái
                        <select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
                            <option value="ALL">Tất cả</option>
                            <option value="PENDING">Chờ tiếp nhận</option>
                            <option value="CONFIRMED">Đã xác nhận</option>
                            <option value="CHECKED_IN">Đã đến phòng khám</option>
                            <option value="COMPLETED">Đã hoàn thành</option>
                            <option value="CANCELLED">Đã hủy</option>
                            <option value="NO_SHOW">Không đến khám</option>
                            <option value="FOLLOW_UP_REQUIRED">Cần tái khám</option>
                        </select>
                    </label>
                    <label>
                        Thời gian
                        <select value={dateFilter} onChange={event => setDateFilter(event.target.value)}>
                            <option value="ALL">Tất cả ngày</option>
                            <option value="TODAY">Hôm nay</option>
                            <option value="UPCOMING">Sắp tới</option>
                            <option value="PAST">Đã qua</option>
                        </select>
                    </label>
                    {(searchKw || statusFilter !== "ALL" || dateFilter !== "ALL") && (
                        <button type="button" className="appointment-reset-filters" onClick={() => {
                            setSearchKw("");
                            setStatusFilter("ALL");
                            setDateFilter("ALL");
                        }}>
                            Xóa bộ lọc
                        </button>
                    )}
                </div>
            )}

            {filtered.length === 0 ? (
                <EmptyState
                    compact
                    icon={appointments.length === 0 ? CalendarDays : Search}
                    title={appointments.length === 0 ? "Bạn chưa có lịch khám" : "Không tìm thấy lịch phù hợp"}
                    description={appointments.length === 0
                        ? "Chọn bác sĩ, ngày và khung giờ phù hợp để tạo lịch hẹn đầu tiên."
                        : "Hãy thay đổi từ khóa hoặc xóa các bộ lọc đang áp dụng."}
                    action={appointments.length === 0 && onBookNew
                        ? { label: "Đặt lịch mới", onClick: onBookNew }
                        : appointments.length > 0
                            ? { label: "Xóa bộ lọc", onClick: () => { setSearchKw(""); setStatusFilter("ALL"); setDateFilter("ALL"); } }
                            : undefined}
                />
            ) : (
                <>
                <div className="appointment-history-list" id="patient-appointment-history-list">
                    {visibleAppointments.map(item => {
                        const canSelfManage = canPatientSelfManageAppointment(item.status, item.createdAt, selfServiceNow);
                        const hasSelfServiceAction = ["PENDING", "ASSIGNED", "CONFIRMED"].includes(item.status);
                        return (
                            <article className="patient-appointment-row" key={item.id}>
                                <div className="appointment-date-icon" aria-hidden="true"><CalendarDays /></div>
                                <div className="patient-appointment-details">
                                    <time dateTime={item.startAt}>{formatAppointmentTime(item.startAt)}</time>
                                    <p>{item.status === "FOLLOW_UP_REQUIRED"
                                        ? item.followUpReason || "Bác sĩ yêu cầu tái khám"
                                        : item.reason || "Không có ghi chú"}</p>
                                    {item.consultationFeeSnapshot !== undefined && item.consultationFeeSnapshot !== null && (
                                        <p className="patient-appointment-fee">
                                            <span>Giá khám đã chốt</span>
                                            <strong>{formatVnd(item.consultationFeeSnapshot)}</strong>
                                        </p>
                                    )}
                                </div>
                                <div className="patient-appointment-actions">
                                    <AppointmentStatusBadge status={item.status} awaitingClinicUpdate={isStaleInProgressAppointment(item, selfServiceNow)} />
                                    {hasSelfServiceAction && canSelfManage && reschedule && token && (
                                            <RescheduleAppointmentControl
                                                token={token}
                                                appointment={item}
                                                submit={value => reschedule(item.id, value)}
                                            />
                                        )}
                                    {hasSelfServiceAction && canSelfManage && cancel && (
                                        <CancelAppointmentControl submit={reason => cancel(item.id, reason)} />
                                    )}
                                    {hasSelfServiceAction && !canSelfManage && (reschedule || cancel) && (
                                        <button
                                            type="button"
                                            className="appointment-support-action"
                                            onClick={() => window.dispatchEvent(new Event("open-support-chat"))}
                                        >
                                            <MessageCircle aria-hidden="true" />
                                            Liên hệ hỗ trợ để đổi hoặc hủy lịch
                                        </button>
                                    )}
                                    {item.status === "FOLLOW_UP_REQUIRED" && token && bookFollowUp && (
                                        <FollowUpControl token={token} appointment={item} submit={slot => bookFollowUp(item.id, slot)} />
                                    )}
                                    {item.status === "COMPLETED" && token && patientName && (
                                        <AppointmentReviewControl token={token} appointmentId={item.id} patientName={patientName} />
                                    )}
                                    {token && hide && canHideAppointmentFromHistory(item.status) && (
                                        <DeleteAppointmentControl appointment={item} submit={() => hide(item.id)} />
                                    )}
                                </div>
                            </article>
                        );
                    })}
                </div>
                {filtered.length > APPOINTMENT_PAGE_SIZE && (
                    <div className="appointment-history-pagination" aria-live="polite">
                        <span>Đang hiển thị {visibleAppointments.length}/{filtered.length} lịch</span>
                        <button
                            type="button"
                            aria-controls="patient-appointment-history-list"
                            aria-expanded={remainingAppointments === 0}
                            onClick={() => setVisibleCount(current => remainingAppointments > 0
                                ? Math.min(current + APPOINTMENT_PAGE_SIZE, filtered.length)
                                : APPOINTMENT_PAGE_SIZE)}
                        >
                            {remainingAppointments > 0
                                ? `Xem thêm ${Math.min(APPOINTMENT_PAGE_SIZE, remainingAppointments)} lịch`
                                : "Thu gọn"}
                            {remainingAppointments > 0 ? <ChevronDown aria-hidden="true" /> : <ChevronUp aria-hidden="true" />}
                        </button>
                    </div>
                )}
                </>
            )}
        </section>
    );
}
