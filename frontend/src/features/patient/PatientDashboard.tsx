import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import {
    ArrowRight,
    Bell,
    BrainCircuit,
    CalendarCheck2,
    CalendarDays,
    ChevronDown,
    ClipboardList,
    Clock3,
    FileText,
    MapPin,
    MessageCircle,
    Pill,
    Stethoscope,
    TriangleAlert,
    UserRound,
} from "lucide-react";
import { request, requestBlob } from "../../core/api";
import {
    canPatientSelfManageAppointment,
    patientAppointmentSelfServiceClosesAt,
} from "../../core/appointmentPolicy";
import { subscribeRealtime } from "../../core/realtime";
import type {
    AiAssessment,
    Appointment,
    Doctor,
    MedicalRecord,
    Patient,
    PatientNotification,
    Prescription,
} from "../../core/types";
import {
    AppointmentStatusBadge,
    CancelAppointmentControl,
    RescheduleAppointmentControl,
} from "../../components/PatientAppointmentList";
import PatientProfile from "./PatientProfile";

const ACTIVE_APPOINTMENT_STATUSES = new Set(["PROPOSED", "PENDING", "ASSIGNED", "CONFIRMED", "CHECKED_IN", "IN_PROGRESS"]);
const RESCHEDULABLE_STATUSES = new Set(["PENDING", "ASSIGNED", "CONFIRMED"]);
const IMPORTANT_NOTIFICATION_TYPES = new Set([
    "REQUEST_CREATED",
    "BOOKING_PROPOSAL",
    "PROPOSAL_ACCEPTED",
    "CONFIRMED",
    "CHECKED_IN",
    "RESCHEDULED",
    "CANCELLED",
    "REMINDER_24H",
    "REMINDER_2H",
    "COMPLETED",
    "NO_SHOW",
]);
const CLINIC_ADDRESS = "32/2 Thống Nhất, phường Gò Vấp, TP. Hồ Chí Minh";

const AI_LABELS: Record<string, string> = {
    Acne: "Mụn trứng cá",
    Candidiasis: "Nhiễm nấm Candida",
    Eczema: "Chàm / eczema",
    Lupus: "Biểu hiện da liên quan lupus",
    Psoriasis: "Vảy nến",
    SkinCancer: "Nhóm tổn thương cần được bác sĩ đánh giá",
    Tinea: "Nấm da",
    Warts: "Mụn cóc",
};

export type PatientDashboardResourceState = {
    loading: boolean;
    error: string;
};

type PatientDashboardProps = {
    token: string;
    patient: Patient;
    appointments: Appointment[];
    records: MedicalRecord[];
    prescriptions: Prescription[];
    resourceState: {
        appointments: PatientDashboardResourceState;
        records: PatientDashboardResourceState;
        prescriptions: PatientDashboardResourceState;
    };
    savedPatient: (patient: Patient) => void;
    changedAppointments: (appointments: Appointment[]) => void;
    openAppointments: () => void;
    openAi: () => void;
    openRecords: () => void;
};

type DashboardTask = {
    id: string;
    title: string;
    description: string;
    actionLabel: string;
    icon: ComponentType<{ "aria-hidden"?: boolean }>;
    action: () => void;
};

function formatDate(value: string, options?: Intl.DateTimeFormatOptions) {
    return new Intl.DateTimeFormat("vi-VN", options || {
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric",
    }).format(new Date(value));
}

function formatTime(value: string) {
    return new Date(value).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

function doctorSpecialty(value?: string) {
    if (!value) return "Chuyên khoa Da liễu";
    if (value === "DERMATOLOGY") return "Da liễu tổng quát";
    return value;
}

function DashboardState({
    tone,
    title,
    description,
    action,
    actionLabel,
}: {
    tone: "loading" | "empty" | "error";
    title: string;
    description?: string;
    action?: () => void;
    actionLabel?: string;
}) {
    return <div className={"patient-dashboard-state is-" + tone} role={tone === "error" ? "alert" : "status"}>
        <strong>{title}</strong>
        {description && <p>{description}</p>}
        {action && actionLabel && <button type="button" onClick={action}>{actionLabel}<ArrowRight aria-hidden="true" /></button>}
    </div>;
}

function AiThumbnail({ token, assessment }: { token: string; assessment: AiAssessment }) {
    const [source, setSource] = useState("");

    useEffect(() => {
        if (!assessment.imageAvailable) return;
        let active = true;
        let objectUrl = "";
        requestBlob("/patients/me/ai-assessments/" + assessment.id + "/image", token)
            .then(blob => {
                if (!active) return;
                objectUrl = URL.createObjectURL(blob);
                setSource(objectUrl);
            })
            .catch(() => undefined);
        return () => {
            active = false;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [assessment.id, assessment.imageAvailable, token]);

    return <div className="patient-dashboard-ai-media">
        {source
            ? <img src={source} alt="Ảnh vùng da trong lần phân tích gần nhất" />
            : <BrainCircuit aria-hidden="true" />}
    </div>;
}

export default function PatientDashboard({
    token,
    patient,
    appointments,
    records,
    prescriptions,
    resourceState,
    savedPatient,
    changedAppointments,
    openAppointments,
    openAi,
    openRecords,
}: PatientDashboardProps) {
    const [doctors, setDoctors] = useState<Doctor[]>([]);
    const [doctorState, setDoctorState] = useState<PatientDashboardResourceState>({ loading: true, error: "" });
    const [assessments, setAssessments] = useState<AiAssessment[]>([]);
    const [aiState, setAiState] = useState<PatientDashboardResourceState>({ loading: true, error: "" });
    const [notifications, setNotifications] = useState<PatientNotification[]>([]);
    const [notificationState, setNotificationState] = useState<PatientDashboardResourceState>({ loading: true, error: "" });
    const [feedback, setFeedback] = useState<{ tone: "success" | "error"; text: string } | null>(null);
    const [appointmentRefreshed, setAppointmentRefreshed] = useState(false);
    const [selfServiceNow, setSelfServiceNow] = useState(Date.now());
    const dashboardRef = useRef<HTMLDivElement>(null);
    const previousAppointmentRef = useRef("");
    const profileDetailsRef = useRef<HTMLDetailsElement>(null);

    const loadDoctors = useCallback(() => {
        setDoctorState({ loading: true, error: "" });
        return request<Doctor[]>("/doctors", token)
            .then(setDoctors)
            .catch(cause => setDoctorState({ loading: false, error: (cause as Error).message }))
            .finally(() => setDoctorState(current => ({ ...current, loading: false })));
    }, [token]);

    const loadAi = useCallback(() => {
        setAiState({ loading: true, error: "" });
        return request<AiAssessment[]>("/patients/me/ai-assessments", token)
            .then(setAssessments)
            .catch(cause => setAiState({ loading: false, error: (cause as Error).message }))
            .finally(() => setAiState(current => ({ ...current, loading: false })));
    }, [token]);

    const loadNotifications = useCallback(() => {
        return request<PatientNotification[]>("/appointments/notifications/mine", token)
            .then(value => {
                setNotifications(value);
                setNotificationState({ loading: false, error: "" });
            })
            .catch(cause => setNotificationState({ loading: false, error: (cause as Error).message }))
            .finally(() => setNotificationState(current => ({ ...current, loading: false })));
    }, [token]);

    useEffect(() => { void loadDoctors() }, [loadDoctors]);
    useEffect(() => { void loadAi() }, [loadAi]);
    useEffect(() => {
        void loadNotifications();
        const unsubscribe = subscribeRealtime(() => { void loadNotifications() });
        const refresh = () => { void loadNotifications() };
        window.addEventListener("appointments-changed", refresh);
        window.addEventListener("patient-notifications-changed", refresh);
        return () => {
            unsubscribe();
            window.removeEventListener("appointments-changed", refresh);
            window.removeEventListener("patient-notifications-changed", refresh);
        };
    }, [loadNotifications]);
    useEffect(() => {
        const refresh = () => { void loadDoctors() };
        window.addEventListener("doctor-profiles-changed", refresh);
        return () => window.removeEventListener("doctor-profiles-changed", refresh);
    }, [loadDoctors]);

    const upcoming = useMemo(() => appointments
        .filter(item => ACTIVE_APPOINTMENT_STATUSES.has(item.status) && (["CHECKED_IN", "IN_PROGRESS"].includes(item.status) || new Date(item.endAt).getTime() > Date.now()))
        .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime()), [appointments]);
    const nextAppointment = upcoming[0];
    const nextDoctor = doctors.find(item => item.id === nextAppointment?.doctorId);
    const canSelfManageNextAppointment = nextAppointment
        ? canPatientSelfManageAppointment(nextAppointment.status, nextAppointment.createdAt, selfServiceNow)
        : false;

    // Keep the actions accurate even when the dashboard stays open past the cutoff.
    useEffect(() => {
        if (!nextAppointment || !["PENDING", "ASSIGNED"].includes(nextAppointment.status)) return;
        const closesAt = patientAppointmentSelfServiceClosesAt(nextAppointment.createdAt);
        const now = Date.now();
        if (!Number.isFinite(closesAt) || closesAt < now) return;
        const timer = window.setTimeout(
            () => setSelfServiceNow(Date.now()),
            Math.max(0, closesAt - now + 25),
        );
        return () => window.clearTimeout(timer);
    }, [nextAppointment, selfServiceNow]);
    const latestAssessment = useMemo(() => [...assessments]
        .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())[0], [assessments]);
    const latestRecord = useMemo(() => [...records]
        .sort((left, right) => new Date(right.signedAt).getTime() - new Date(left.signedAt).getTime())[0], [records]);
    const latestPrescription = useMemo(() => [...prescriptions]
        .sort((left, right) => new Date(right.signedAt).getTime() - new Date(left.signedAt).getTime())[0], [prescriptions]);
    const recordAppointment = appointments.find(item => item.id === latestRecord?.appointmentId);
    const importantNotifications = useMemo(() => notifications
        .filter(item => IMPORTANT_NOTIFICATION_TYPES.has(item.notificationType) || item.notificationType.startsWith("MANUAL_REMINDER_"))
        .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
        .slice(0, 3), [notifications]);

    const appointmentSignature = nextAppointment
        ? [nextAppointment.id, nextAppointment.status, nextAppointment.startAt].join(":")
        : "none";
    useEffect(() => {
        if (previousAppointmentRef.current && previousAppointmentRef.current !== appointmentSignature) {
            setAppointmentRefreshed(true);
            const timer = window.setTimeout(() => setAppointmentRefreshed(false), 1200);
            previousAppointmentRef.current = appointmentSignature;
            return () => window.clearTimeout(timer);
        }
        previousAppointmentRef.current = appointmentSignature;
    }, [appointmentSignature]);

    function openSupport() {
        window.dispatchEvent(new Event("open-support-chat"));
    }

    function openNotifications() {
        window.dispatchEvent(new Event("open-patient-notifications"));
    }

    function openProfile() {
        if (!profileDetailsRef.current) return;
        profileDetailsRef.current.open = true;
        window.setTimeout(() => profileDetailsRef.current?.querySelector<HTMLInputElement>("input")?.focus(), 0);
    }

    async function refreshAppointments() {
        const latest = await request<Appointment[]>("/appointments/mine", token);
        changedAppointments(latest);
        window.dispatchEvent(new Event("appointments-changed"));
    }

    async function cancelAppointment(id: string, reason: string) {
        setFeedback(null);
        try {
            await request("/appointments/" + id + "/cancel", token, {
                method: "POST",
                body: JSON.stringify({ reason }),
            });
            await refreshAppointments();
            setFeedback({ tone: "success", text: "Lịch khám đã được hủy. Khung giờ được trả lại để người khác có thể đặt." });
        } catch (cause) {
            setFeedback({ tone: "error", text: (cause as Error).message });
            throw cause;
        }
    }

    async function rescheduleAppointment(id: string, value: string) {
        setFeedback(null);
        const appointment = appointments.find(item => item.id === id);
        if (!appointment) return;
        const startAt = new Date(value);
        const duration = Math.max(10 * 60_000, new Date(appointment.endAt).getTime() - new Date(appointment.startAt).getTime());
        try {
            await request("/appointments/" + id + "/reschedule", token, {
                method: "POST",
                headers: { "Idempotency-Key": crypto.randomUUID() },
                body: JSON.stringify({
                    startAt: startAt.toISOString(),
                    endAt: new Date(startAt.getTime() + duration).toISOString(),
                }),
            });
            await refreshAppointments();
            setFeedback({ tone: "success", text: "Đã gửi lịch khám sang khung giờ mới." });
        } catch (cause) {
            setFeedback({ tone: "error", text: (cause as Error).message });
            throw cause;
        }
    }

    const tasks = useMemo<DashboardTask[]>(() => {
        const items: DashboardTask[] = [];
        if (!patient.phone?.trim() || !patient.dob) {
            items.push({
                id: "profile",
                title: "Hoàn tất hồ sơ cá nhân",
                description: "Bổ sung ngày sinh và số điện thoại để phòng khám liên hệ chính xác.",
                actionLabel: "Cập nhật hồ sơ",
                icon: UserRound,
                action: openProfile,
            });
        }
        const proposed = upcoming.find(item => item.status === "PROPOSED");
        if (proposed) {
            items.push({
                id: "proposal",
                title: "Xác nhận lịch lễ tân đề nghị",
                description: "Đề nghị có thời hạn. Hãy xem thời gian trước khi đồng ý.",
                actionLabel: "Mở thông báo",
                icon: Bell,
                action: openNotifications,
            });
        }
        const followUp = appointments.find(item => item.status === "FOLLOW_UP_REQUIRED");
        if (followUp) {
            items.push({
                id: "follow-up",
                title: "Chọn lịch tái khám",
                description: followUp.followUpReason || "Bác sĩ đã yêu cầu một lần tái khám.",
                actionLabel: "Xem lịch khám",
                icon: CalendarCheck2,
                action: openAppointments,
            });
        } else if (nextAppointment?.status === "CONFIRMED"
            && new Date(nextAppointment.startAt).getTime() - Date.now() <= 48 * 60 * 60_000) {
            items.push({
                id: "prepare",
                title: "Chuẩn bị cho lịch khám sắp tới",
                description: "Kiểm tra lại thời gian, địa chỉ và đến đúng giờ đã hẹn.",
                actionLabel: "Xem lịch hẹn",
                icon: ClipboardList,
                action: openAppointments,
            });
        }
        if (latestAssessment?.sharedWithDoctor && !latestAssessment.appointmentId) {
            items.push({
                id: "ai-booking",
                title: "Đặt lịch sau lần phân tích da",
                description: "Kết quả tham khảo đang sẵn sàng để đính kèm vào lịch khám.",
                actionLabel: "Đặt lịch khám",
                icon: BrainCircuit,
                action: openAppointments,
            });
        }
        return items.slice(0, 4);
    }, [appointments, latestAssessment, nextAppointment, patient.dob, patient.phone, upcoming, openAppointments]);

    useEffect(() => {
        const root = dashboardRef.current;
        if (!root) return;
        const sections = Array.from(root.querySelectorAll<HTMLElement>(".patient-dashboard-reveal"));
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (reducedMotion || !("IntersectionObserver" in window)) {
            sections.forEach(section => section.classList.add("is-visible"));
            return;
        }
        // Một observer duy nhất chỉ reveal các section lớn, không theo dõi từng dòng nội dung.
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.08, rootMargin: "0px 0px -6% 0px" });
        sections.forEach(section => observer.observe(section));
        return () => observer.disconnect();
    }, [tasks.length]);

    const aiStatus = latestAssessment?.uncertain
        ? { label: "Nên được đánh giá trực tiếp", tone: "warning" }
        : latestAssessment?.appointmentId
            ? { label: "Đã chia sẻ cùng lịch hẹn", tone: "info" }
            : latestAssessment?.sharedWithDoctor
                ? { label: "Sẵn sàng đính kèm khi đặt lịch", tone: "info" }
                : { label: "Đã phân tích", tone: "neutral" };

    return <div className="patient-dashboard" ref={dashboardRef}>
        <div className="patient-dashboard-live" role="status" aria-live="polite">{appointmentRefreshed ? "Lịch khám vừa được cập nhật." : ""}</div>

        <section
            className={"patient-dashboard-next patient-dashboard-reveal" + (appointmentRefreshed ? " is-refreshed" : "")}
            aria-labelledby="patient-next-appointment-title"
        >
            <header className="patient-dashboard-section-heading">
                <div>
                    <h2 id="patient-next-appointment-title">Lịch khám sắp tới</h2>
                    <p>Thông tin quan trọng nhất cho lần thăm khám tiếp theo của bạn.</p>
                </div>
                {upcoming.length > 1 && <button type="button" className="patient-dashboard-text-action" onClick={openAppointments}>Xem {upcoming.length} lịch</button>}
            </header>

            {resourceState.appointments.loading ? (
                <DashboardState tone="loading" title="Đang tải lịch khám..." description="Thông tin sẽ xuất hiện ngay khi dịch vụ phản hồi." />
            ) : resourceState.appointments.error ? (
                <DashboardState tone="error" title="Chưa tải được lịch khám" description={resourceState.appointments.error} />
            ) : !nextAppointment ? (
                <DashboardState tone="empty" title="Bạn chưa có lịch khám sắp tới" description="Chọn bác sĩ và khung giờ phù hợp khi bạn cần được đánh giá trực tiếp." action={openAppointments} actionLabel="Đặt lịch khám" />
            ) : (
                <div className="patient-dashboard-appointment">
                    <div className="patient-dashboard-date-block" aria-label={formatDate(nextAppointment.startAt)}>
                        <span>{formatDate(nextAppointment.startAt, { month: "short" })}</span>
                        <strong>{formatDate(nextAppointment.startAt, { day: "2-digit" })}</strong>
                        <small>{formatDate(nextAppointment.startAt, { weekday: "long" })}</small>
                    </div>
                    <div className="patient-dashboard-appointment-body">
                        <div className="patient-dashboard-doctor-line">
                            {nextDoctor?.avatarUrl
                                ? <img src={nextDoctor.avatarUrl} alt={"Ảnh BS. " + nextDoctor.fullName} />
                                : <span aria-hidden="true">{(nextDoctor?.fullName || nextAppointment.doctorName || "B").slice(0, 1).toUpperCase()}</span>}
                            <div>
                                <h3>BS. {nextDoctor?.fullName || nextAppointment.doctorName || "Bác sĩ phụ trách"}</h3>
                                <p>{doctorState.loading ? "Đang tải chuyên khoa..." : doctorState.error ? "Chuyên khoa Da liễu" : doctorSpecialty(nextDoctor?.specialtyCode)}</p>
                            </div>
                            <AppointmentStatusBadge status={nextAppointment.status} />
                        </div>
                        <dl className="patient-dashboard-appointment-facts">
                            <div><dt><Clock3 aria-hidden="true" />Thời gian</dt><dd>{formatTime(nextAppointment.startAt)} - {formatTime(nextAppointment.endAt)}, {formatDate(nextAppointment.startAt, { day: "2-digit", month: "2-digit", year: "numeric" })}</dd></div>
                            <div><dt><MapPin aria-hidden="true" />Địa điểm</dt><dd>{CLINIC_ADDRESS}</dd></div>
                            {nextAppointment.reason && <div><dt><ClipboardList aria-hidden="true" />Lý do khám</dt><dd>{nextAppointment.reason}</dd></div>}
                        </dl>
                        <div className="patient-dashboard-appointment-actions">
                            {RESCHEDULABLE_STATUSES.has(nextAppointment.status)
                                && canSelfManageNextAppointment && (
                                    <>
                                        <RescheduleAppointmentControl token={token} appointment={nextAppointment} submit={value => rescheduleAppointment(nextAppointment.id, value)} />
                                        <CancelAppointmentControl submit={reason => cancelAppointment(nextAppointment.id, reason)} />
                                    </>
                                )}
                            {RESCHEDULABLE_STATUSES.has(nextAppointment.status)
                                && !canSelfManageNextAppointment ? (
                                    <button type="button" className="patient-dashboard-support-action" onClick={openSupport}>
                                        <MessageCircle aria-hidden="true" />Liên hệ hỗ trợ để đổi hoặc hủy lịch
                                    </button>
                                ) : (
                                    <button type="button" className="patient-dashboard-support-action" onClick={openSupport}>
                                        <MessageCircle aria-hidden="true" />Liên hệ hỗ trợ
                                    </button>
                                )}
                        </div>
                    </div>
                </div>
            )}
            {feedback && <p className={"patient-dashboard-feedback is-" + feedback.tone} role={feedback.tone === "error" ? "alert" : "status"} aria-live={feedback.tone === "error" ? "assertive" : "polite"}>{feedback.text}</p>}
        </section>

        {tasks.length > 0 && <section className="patient-dashboard-tasks patient-dashboard-reveal" aria-labelledby="patient-tasks-title">
            <header className="patient-dashboard-section-heading">
                <div><h2 id="patient-tasks-title">Việc cần làm tiếp theo</h2><p>Chỉ hiển thị những việc đang liên quan đến hồ sơ và lịch khám của bạn.</p></div>
            </header>
            <div className="patient-dashboard-task-list">
                {tasks.map(task => <article key={task.id}>
                    <span aria-hidden="true"><task.icon /></span>
                    <div><h3>{task.title}</h3><p>{task.description}</p></div>
                    <button type="button" onClick={task.action}>{task.actionLabel}<ArrowRight aria-hidden="true" /></button>
                </article>)}
            </div>
        </section>}

        <div className="patient-dashboard-secondary">
            <section className="patient-dashboard-ai patient-dashboard-reveal" aria-labelledby="patient-ai-recent-title">
                <header className="patient-dashboard-section-heading">
                    <div><h2 id="patient-ai-recent-title">Phân tích da gần đây</h2><p>Kết quả từ hình ảnh chỉ mang tính tham khảo trước khi bác sĩ đánh giá.</p></div>
                </header>
                {aiState.loading ? (
                    <DashboardState tone="loading" title="Đang tải lần phân tích gần nhất..." />
                ) : aiState.error ? (
                    <DashboardState tone="error" title="Chưa tải được dữ liệu phân tích" description={aiState.error} />
                ) : !latestAssessment ? (
                    <DashboardState tone="empty" title="Chưa có lần phân tích da" description="Bạn có thể tải ảnh rõ nét để nhận gợi ý nhóm hình ảnh tham khảo." action={openAi} actionLabel="Kiểm tra da bằng AI" />
                ) : <div className="patient-dashboard-ai-summary">
                    <AiThumbnail token={token} assessment={latestAssessment} />
                    <div>
                        <div className="patient-dashboard-status-line">
                            <span className={"patient-dashboard-ai-status is-" + aiStatus.tone}>{aiStatus.label}</span>
                            <time dateTime={latestAssessment.createdAt}>{formatDate(latestAssessment.createdAt, { day: "2-digit", month: "2-digit", year: "numeric" })}</time>
                        </div>
                        <h3>Phân tích hình ảnh đã hoàn tất</h3>
                        <p>Nhóm hình ảnh tham khảo: <strong>{AI_LABELS[latestAssessment.predictedLabel] || latestAssessment.predictedLabel}</strong>.</p>
                        <p className="patient-dashboard-medical-note">Kết quả này không phải chẩn đoán cuối cùng. Bạn có thể đặt lịch để được bác sĩ đánh giá trực tiếp.</p>
                        <div className="patient-dashboard-inline-actions">
                            <button type="button" onClick={openAi}>Xem chi tiết</button>
                            <button type="button" onClick={openAppointments}>Đặt lịch khám</button>
                        </div>
                    </div>
                </div>}
            </section>

            <section className="patient-dashboard-notifications patient-dashboard-reveal" aria-labelledby="patient-notifications-title">
                <header className="patient-dashboard-section-heading">
                    <div><h2 id="patient-notifications-title">Thông báo quan trọng</h2><p>Các cập nhật gần nhất về lịch khám của bạn.</p></div>
                    {notifications.length > 0 && <button type="button" className="patient-dashboard-text-action" onClick={openNotifications}>Xem tất cả</button>}
                </header>
                {notificationState.loading ? (
                    <DashboardState tone="loading" title="Đang tải thông báo..." />
                ) : notificationState.error ? (
                    <DashboardState tone="error" title="Chưa tải được thông báo" description={notificationState.error} />
                ) : importantNotifications.length === 0 ? (
                    <DashboardState tone="empty" title="Chưa có thông báo quan trọng" description="Xác nhận, thay đổi và nhắc lịch sẽ xuất hiện tại đây." />
                ) : <div className="patient-dashboard-notification-list">
                    {importantNotifications.map(item => <article className={`${!item.readAt ? "is-unread" : ""} ${item.notificationType === "NO_SHOW" ? "is-warning" : ""}`.trim()} key={item.id}>
                        {item.notificationType === "NO_SHOW" ? <TriangleAlert aria-hidden="true" /> : <Bell aria-hidden="true" />}
                        <div><h3>{item.title}</h3><p>{item.body}</p><time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleString("vi-VN")}</time></div>
                        <span>{item.readAt ? "Đã xem" : "Mới"}</span>
                    </article>)}
                </div>}
            </section>
        </div>

        <section className="patient-dashboard-medical patient-dashboard-reveal" aria-labelledby="patient-medical-title">
            <header className="patient-dashboard-section-heading">
                <div><h2 id="patient-medical-title">Kết quả khám và đơn thuốc gần đây</h2><p>Chỉ hiển thị tóm tắt từ nội dung đã được bác sĩ ký xác nhận.</p></div>
                {(latestRecord || latestPrescription) && <button type="button" className="patient-dashboard-text-action" onClick={openRecords}>Xem kết quả</button>}
            </header>
            {(resourceState.records.loading || resourceState.prescriptions.loading) && !latestRecord && !latestPrescription ? (
                <DashboardState tone="loading" title="Đang tải kết quả khám..." />
            ) : resourceState.records.error && resourceState.prescriptions.error ? (
                <DashboardState tone="error" title="Chưa tải được kết quả và đơn thuốc" description="Bạn có thể thử mở lại mục Kết quả khám sau." />
            ) : !latestRecord && !latestPrescription ? (
                <DashboardState tone="empty" title="Chưa có kết quả khám" description="Kết luận và đơn thuốc sẽ xuất hiện sau khi bác sĩ hoàn tất buổi khám." />
            ) : <div className="patient-dashboard-medical-summary">
                <article>
                    <span aria-hidden="true"><FileText /></span>
                    <div>
                        <h3>Kết quả khám gần nhất</h3>
                        {latestRecord ? <>
                            <time dateTime={latestRecord.signedAt}>{formatDate(latestRecord.signedAt, { day: "2-digit", month: "2-digit", year: "numeric" })}</time>
                            {recordAppointment?.doctorName && <p>Bác sĩ: <strong>{recordAppointment.doctorName}</strong></p>}
                            <p>Kết luận chuyên môn: <strong>{latestRecord.finalDiagnosis}</strong></p>
                            {latestRecord.followUpAt && <p>Tái khám: {new Date(latestRecord.followUpAt).toLocaleString("vi-VN")}</p>}
                        </> : <p role={resourceState.records.error ? "alert" : undefined}>{resourceState.records.error || "Chưa có kết quả khám đã ký."}</p>}
                    </div>
                </article>
                <article>
                    <span aria-hidden="true"><Pill /></span>
                    <div>
                        <h3>Đơn thuốc gần nhất</h3>
                        {latestPrescription ? <>
                            <time dateTime={latestPrescription.signedAt}>{formatDate(latestPrescription.signedAt, { day: "2-digit", month: "2-digit", year: "numeric" })}</time>
                            <p>Đơn thuốc đã ký gồm <strong>{latestPrescription.items.length} mục</strong>.</p>
                            {latestPrescription.instructions && <p>Có hướng dẫn sử dụng từ bác sĩ.</p>}
                        </> : <p role={resourceState.prescriptions.error ? "alert" : undefined}>{resourceState.prescriptions.error || "Chưa có đơn thuốc đã ký."}</p>}
                    </div>
                </article>
            </div>}
        </section>

        <section className="patient-dashboard-quick patient-dashboard-reveal" aria-labelledby="patient-quick-title">
            <header className="patient-dashboard-section-heading"><div><h2 id="patient-quick-title">Truy cập nhanh</h2></div></header>
            <nav aria-label="Truy cập nhanh cho bệnh nhân">
                <button type="button" onClick={openAppointments}><CalendarDays aria-hidden="true" /><span><strong>Đặt lịch khám</strong><small>Chọn bác sĩ và khung giờ</small></span><ArrowRight aria-hidden="true" /></button>
                <button type="button" onClick={openAi}><BrainCircuit aria-hidden="true" /><span><strong>Kiểm tra da bằng AI</strong><small>Phân tích hình ảnh tham khảo</small></span><ArrowRight aria-hidden="true" /></button>
                <button type="button" onClick={openAppointments}><CalendarCheck2 aria-hidden="true" /><span><strong>Xem lịch hẹn</strong><small>Theo dõi và điều chỉnh lịch</small></span><ArrowRight aria-hidden="true" /></button>
                <button type="button" onClick={openRecords}><Stethoscope aria-hidden="true" /><span><strong>Xem kết quả</strong><small>Kết luận khám và đơn thuốc</small></span><ArrowRight aria-hidden="true" /></button>
            </nav>
        </section>

        <details className="patient-dashboard-profile patient-dashboard-reveal" ref={profileDetailsRef}>
            <summary>
                <span><strong>Thông tin cá nhân</strong><small>Xem hoặc cập nhật hồ sơ dùng khi đặt lịch</small></span>
                <ChevronDown aria-hidden="true" />
            </summary>
            <PatientProfile token={token} patient={patient} saved={savedPatient} />
        </details>
    </div>;
}
