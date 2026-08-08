import { useEffect, useMemo, useRef, useState } from "react";
import {
    ArrowRight,
    CalendarClock,
    CheckCircle2,
    ChevronRight,
    FileText,
    MessageCircle,
    Pill,
    Search,
    Stethoscope,
    X,
} from "lucide-react";
import { request } from "../../core/api";
import type { Appointment, Doctor, MedicalRecord, Patient, Prescription } from "../../core/types";
import { PrescriptionPdfModal } from "../../components/PrescriptionPdfModal";

type ResourceState = {
    loading: boolean;
    error: string;
};

type PatientMedicalRecordsProps = {
    token: string;
    patient: Patient;
    appointments: Appointment[];
    records: MedicalRecord[];
    prescriptions: Prescription[];
    resourceState: {
        appointments: ResourceState;
        records: ResourceState;
        prescriptions: ResourceState;
    };
    openAppointments: () => void;
};

export type PatientRecordEntry = {
    record: MedicalRecord;
    appointment?: Appointment;
    prescription?: Prescription;
};

const AI_REASON_MARKERS = [
    "kết quả kiểm tra da bằng ai",
    "ket qua kiem tra da bang ai",
    "phân tích da bằng ai",
];

const SEVERITY_LABELS: Record<string, string> = {
    MILD: "Mức độ nhẹ",
    MODERATE: "Mức độ trung bình",
    SEVERE: "Mức độ nặng",
    URGENT: "Cần được ưu tiên",
};

export function isAiSupportedReason(reason?: string) {
    const normalized = (reason || "").trim().toLocaleLowerCase("vi");
    return AI_REASON_MARKERS.some(marker => normalized.includes(marker));
}

export function buildPatientRecordEntries(
    records: MedicalRecord[],
    appointments: Appointment[],
    prescriptions: Prescription[],
) {
    const appointmentsById = new Map(appointments.map(item => [item.id, item]));
    const prescriptionsByRecordId = new Map(prescriptions.map(item => [item.recordId, item]));

    return records.map(record => ({
        record,
        appointment: appointmentsById.get(record.appointmentId),
        prescription: prescriptionsByRecordId.get(record.id),
    })).sort((left, right) => {
        const leftDate = left.appointment?.startAt || left.record.signedAt;
        const rightDate = right.appointment?.startAt || right.record.signedAt;
        return new Date(rightDate).getTime() - new Date(leftDate).getTime();
    });
}

export function isPatientRecordComplete(entry: PatientRecordEntry) {
    if (!entry.record.finalDiagnosis?.trim() || !entry.record.signedAt) return false;
    if (!entry.appointment) return true;
    return ["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(entry.appointment.status);
}

function formatDate(value: string, options?: Intl.DateTimeFormatOptions) {
    return new Intl.DateTimeFormat("vi-VN", options || {
        day: "2-digit",
        month: "2-digit",
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

function RecordState({
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
    return <div
        className={`patient-medical-state is-${tone}`}
        role={tone === "error" ? "alert" : "status"}
        aria-live={tone === "error" ? "assertive" : "polite"}
    >
        {tone === "loading" && <div className="patient-medical-skeleton" aria-hidden="true"><i /><i /><i /></div>}
        <strong>{title}</strong>
        {description && <p>{description}</p>}
        {action && actionLabel && <button type="button" onClick={action}>{actionLabel}<ArrowRight aria-hidden="true" /></button>}
    </div>;
}

function RecordStatus({ complete }: { complete: boolean }) {
    return <span className={`patient-medical-status ${complete ? "is-complete" : "is-updating"}`}>
        {complete && <CheckCircle2 aria-hidden="true" />}
        {complete ? "Kết quả đã hoàn tất" : "Bác sĩ đang cập nhật"}
    </span>;
}

function PrescriptionContent({ prescription }: { prescription: Prescription }) {
    return <>
        <ol className="patient-prescription-items" aria-label="Danh sách thuốc trong đơn">
            {prescription.items.map((item, index) => <li key={`${item.drugName}-${index}`}>
                <div className="patient-prescription-name">
                    <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                    <div>
                        <h4>{item.drugName}</h4>
                        {item.dosage && <p>{item.dosage}</p>}
                    </div>
                </div>
                <dl>
                    {item.frequency && <div><dt>Tần suất</dt><dd>{item.frequency}</dd></div>}
                    {item.duration && <div><dt>Thời gian dùng</dt><dd>{item.duration}</dd></div>}
                </dl>
                {item.instructions && <div className="patient-prescription-instruction">
                    <strong>Cách dùng theo đơn</strong>
                    <p>{item.instructions}</p>
                </div>}
            </li>)}
        </ol>
        {prescription.instructions && <div className="patient-prescription-general">
            <strong>Hướng dẫn chung theo đơn</strong>
            <p>{prescription.instructions}</p>
        </div>}
    </>;
}

function StandalonePrescriptions({
    prescriptions,
    token,
    patient,
}: {
    prescriptions: Prescription[];
    token: string;
    patient: Patient;
}) {
    const [selected, setSelected] = useState<Prescription | null>(null);

    if (prescriptions.length === 0) return null;
    return <section className="patient-medical-orphans" aria-labelledby="patient-orphan-prescriptions-title">
        <div>
            <h2 id="patient-orphan-prescriptions-title">Đơn thuốc đã ký</h2>
            <p>Nội dung đơn thuốc vẫn được hiển thị ngay cả khi kết quả khám chưa tải được.</p>
        </div>
        <ul>
            {prescriptions.map(prescription => <li key={prescription.id}>
                <div><Pill aria-hidden="true" /><span><strong>{prescription.items.length} thuốc</strong><time dateTime={prescription.signedAt}>Ký ngày {formatDate(prescription.signedAt)}</time></span></div>
                <button type="button" onClick={() => setSelected(prescription)}>Xem đơn thuốc<ChevronRight aria-hidden="true" /></button>
            </li>)}
        </ul>
        {selected && <PrescriptionPdfModal prescription={selected} patient={patient} token={token} onClose={() => setSelected(null)} />}
    </section>;
}

export default function PatientMedicalRecords({
    token,
    patient,
    appointments,
    records,
    prescriptions,
    resourceState,
    openAppointments,
}: PatientMedicalRecordsProps) {
    const [doctors, setDoctors] = useState<Doctor[]>([]);
    const [doctorError, setDoctorError] = useState("");
    const [selectedRecordId, setSelectedRecordId] = useState("");
    const [query, setQuery] = useState("");
    const [period, setPeriod] = useState("all");
    const [kind, setKind] = useState("all");
    const [order, setOrder] = useState("newest");
    const [pdfPrescription, setPdfPrescription] = useState<Prescription | null>(null);
    const detailRef = useRef<HTMLElement>(null);

    useEffect(() => {
        let active = true;
        const loadDoctors = () => request<Doctor[]>("/doctors", token)
            .then(value => {
                if (!active) return;
                setDoctors(value);
                setDoctorError("");
            })
            .catch(cause => {
                if (active) setDoctorError((cause as Error).message);
            });
        void loadDoctors();
        const refresh = () => { void loadDoctors() };
        window.addEventListener("doctor-profiles-changed", refresh);
        return () => {
            active = false;
            window.removeEventListener("doctor-profiles-changed", refresh);
        };
    }, [token]);

    const entries = useMemo(
        () => buildPatientRecordEntries(records, appointments, prescriptions),
        [appointments, prescriptions, records],
    );
    const doctorsById = useMemo(() => new Map(doctors.map(doctor => [doctor.id, doctor])), [doctors]);

    const filteredEntries = useMemo(() => {
        const normalized = query.trim().toLocaleLowerCase("vi");
        const cutoff = period === "all" ? 0 : Date.now() - Number(period) * 86_400_000;
        const result = entries.filter(entry => {
            const doctor = entry.appointment?.doctorId ? doctorsById.get(entry.appointment.doctorId) : undefined;
            const searchable = [
                doctor?.fullName,
                entry.appointment?.doctorName,
                entry.appointment?.reason,
                entry.record.finalDiagnosis,
                entry.record.clinicalNotes,
                entry.record.treatmentPlan,
            ].filter(Boolean).join(" ").toLocaleLowerCase("vi");
            const date = entry.appointment?.startAt || entry.record.signedAt;
            if (normalized && !searchable.includes(normalized)) return false;
            if (cutoff && new Date(date).getTime() < cutoff) return false;
            if (kind === "prescription" && !entry.prescription) return false;
            if (kind === "followup" && !entry.record.followUpAt) return false;
            return true;
        });
        return order === "newest" ? result : [...result].reverse();
    }, [doctorsById, entries, kind, order, period, query]);

    useEffect(() => {
        if (filteredEntries.some(entry => entry.record.id === selectedRecordId)) return;
        setSelectedRecordId(filteredEntries[0]?.record.id || "");
    }, [filteredEntries, selectedRecordId]);

    const selectedEntry = filteredEntries.find(entry => entry.record.id === selectedRecordId);
    const unmatchedPrescriptions = prescriptions.filter(item => !records.some(record => record.id === item.recordId));

    function selectRecord(id: string) {
        setSelectedRecordId(id);
        if (window.matchMedia("(max-width: 768px)").matches) {
            window.setTimeout(() => {
                detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                detailRef.current?.focus({ preventScroll: true });
            }, 0);
        }
    }

    const selectedDoctor = selectedEntry?.appointment?.doctorId
        ? doctorsById.get(selectedEntry.appointment.doctorId)
        : undefined;
    const selectedDoctorName = selectedDoctor?.fullName
        || selectedEntry?.appointment?.doctorName
        || "Bác sĩ phụ trách";
    const selectedDate = selectedEntry
        ? selectedEntry.appointment?.startAt || selectedEntry.record.signedAt
        : "";
    const reasonIsAiSupport = isAiSupportedReason(selectedEntry?.appointment?.reason);

    function openSupport() {
        window.dispatchEvent(new Event("open-support-chat"));
    }

    return <div className="patient-medical-records">
        <header className="patient-medical-heading">
            <div>
                <h2>Kết quả khám của bạn</h2>
                <p>Xem kết luận đã được bác sĩ ghi nhận, đơn thuốc và khuyến nghị tái khám theo từng lần khám.</p>
            </div>
            <span>{records.length} lần khám</span>
        </header>

        {doctorError && records.length > 0 && <div className="patient-medical-alert is-info" role="status">
            Kết quả vẫn xem được. Thông tin tên hoặc chuyên khoa bác sĩ chưa tải đầy đủ.
        </div>}
        {resourceState.appointments.error && records.length > 0 && <div className="patient-medical-alert is-info" role="status">
            Kết quả vẫn xem được. Ngày khám, lý do hoặc bác sĩ của một số lần khám chưa tải đầy đủ.
        </div>}
        {resourceState.records.error && records.length > 0 && <div className="patient-medical-alert is-error" role="alert">
            Một phần danh sách kết quả có thể chưa được cập nhật: {resourceState.records.error}
        </div>}

        <div className="patient-medical-layout">
            <section className="patient-medical-browser" aria-labelledby="patient-medical-history-title">
                <div className="patient-medical-browser-heading">
                    <div><h3 id="patient-medical-history-title">Lịch sử khám</h3><p>Gần nhất được hiển thị trước.</p></div>
                    <span aria-live="polite">{filteredEntries.length}/{entries.length}</span>
                </div>

                {records.length > 0 && <div className="patient-medical-filters" aria-label="Bộ lọc kết quả khám">
                    <label className="patient-medical-search"><span>Tìm trong kết quả</span><div><Search aria-hidden="true" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Bác sĩ, lý do hoặc kết luận" />{query && <button type="button" onClick={() => setQuery("")} aria-label="Xóa nội dung tìm kiếm"><X aria-hidden="true" /></button>}</div></label>
                    <label><span>Thời gian</span><select value={period} onChange={event => setPeriod(event.target.value)}><option value="all">Tất cả</option><option value="90">3 tháng gần đây</option><option value="365">1 năm gần đây</option></select></label>
                    <label><span>Nội dung</span><select value={kind} onChange={event => setKind(event.target.value)}><option value="all">Tất cả kết quả</option><option value="prescription">Có đơn thuốc</option><option value="followup">Có tái khám</option></select></label>
                    <label><span>Sắp xếp</span><select value={order} onChange={event => setOrder(event.target.value)}><option value="newest">Mới nhất</option><option value="oldest">Cũ nhất</option></select></label>
                </div>}

                {resourceState.records.loading && records.length === 0 ? (
                    <RecordState tone="loading" title="Đang tải kết quả khám..." description="Nội dung đã ký sẽ xuất hiện khi dịch vụ phản hồi." />
                ) : resourceState.records.error && records.length === 0 ? (
                    <RecordState tone="error" title="Chưa tải được kết quả khám" description={resourceState.records.error} />
                ) : records.length === 0 ? (
                    <RecordState tone="empty" title="Chưa có kết quả khám" description="Kết quả sẽ xuất hiện sau khi bác sĩ hoàn tất và ký nội dung buổi khám." action={openAppointments} actionLabel="Đặt lịch khám" />
                ) : filteredEntries.length === 0 ? (
                    <RecordState tone="empty" title="Không có kết quả phù hợp" description="Hãy thay đổi từ khóa hoặc bộ lọc để xem các lần khám khác." />
                ) : <ol className="patient-medical-list">
                    {filteredEntries.map(entry => {
                        const appointment = entry.appointment;
                        const doctor = appointment?.doctorId ? doctorsById.get(appointment.doctorId) : undefined;
                        const date = appointment?.startAt || entry.record.signedAt;
                        const complete = isPatientRecordComplete(entry);
                        return <li key={entry.record.id} className={selectedRecordId === entry.record.id ? "is-selected" : ""}>
                            <article>
                                <div className="patient-medical-list-date">
                                    <time dateTime={date}>{formatDate(date, { day: "2-digit", month: "short", year: "numeric" })}</time>
                                    <RecordStatus complete={complete} />
                                </div>
                                <h4>BS. {doctor?.fullName || appointment?.doctorName || "Bác sĩ phụ trách"}</h4>
                                {doctor?.specialtyCode && <p className="patient-medical-specialty">{doctorSpecialty(doctor.specialtyCode)}</p>}
                                <p className="patient-medical-list-reason">{appointment?.reason || "Không có lý do khám được ghi nhận."}</p>
                                <div className="patient-medical-list-meta">
                                    <span><FileText aria-hidden="true" />Kết luận đã ký</span>
                                    <span><Pill aria-hidden="true" />{entry.prescription ? "Có đơn thuốc" : !complete ? "Đơn thuốc đang cập nhật" : resourceState.prescriptions.loading ? "Đang kiểm tra đơn thuốc" : resourceState.prescriptions.error ? "Chưa tải được đơn thuốc" : "Không kê đơn"}</span>
                                    {entry.record.followUpAt && <span><CalendarClock aria-hidden="true" />Có khuyến nghị tái khám</span>}
                                </div>
                                <button type="button" className="patient-medical-open" aria-pressed={selectedRecordId === entry.record.id} onClick={() => selectRecord(entry.record.id)}>Xem chi tiết<ChevronRight aria-hidden="true" /></button>
                            </article>
                        </li>;
                    })}
                </ol>}
            </section>

            {selectedEntry && <article className="patient-medical-detail" ref={detailRef} tabIndex={-1} aria-labelledby="patient-medical-detail-title">
                <header>
                    <div>
                        <span>Kết quả lần khám</span>
                        <h3 id="patient-medical-detail-title">{selectedEntry.record.finalDiagnosis || "Kết quả đang được bác sĩ cập nhật"}</h3>
                        <p>{selectedEntry.appointment ? "Khám ngày" : "Bác sĩ ký ngày"} <time dateTime={selectedDate}>{formatDate(selectedDate, { weekday: "long", day: "2-digit", month: "long", year: "numeric" })}</time></p>
                    </div>
                    <RecordStatus complete={isPatientRecordComplete(selectedEntry)} />
                </header>

                <section className="patient-medical-section" aria-labelledby="patient-visit-information-title">
                    <div className="patient-medical-section-heading"><Stethoscope aria-hidden="true" /><h4 id="patient-visit-information-title">Thông tin buổi khám</h4></div>
                    <dl className="patient-medical-facts">
                        <div><dt>Bác sĩ</dt><dd>BS. {selectedDoctorName}</dd></div>
                        {selectedDoctor && <div><dt>Chuyên khoa</dt><dd>{doctorSpecialty(selectedDoctor.specialtyCode)}</dd></div>}
                        {selectedEntry.appointment && <div><dt>Thời gian</dt><dd>{formatTime(selectedEntry.appointment.startAt)} - {formatTime(selectedEntry.appointment.endAt)}</dd></div>}
                        <div><dt>Ngày xác nhận</dt><dd>{formatDate(selectedEntry.record.signedAt)} lúc {formatTime(selectedEntry.record.signedAt)}</dd></div>
                    </dl>
                    {!reasonIsAiSupport && <div className="patient-medical-provided">
                        <strong>Triệu chứng hoặc lý do khám do bệnh nhân cung cấp</strong>
                        <p>{selectedEntry.appointment?.reason || "Không có nội dung được ghi nhận."}</p>
                    </div>}
                    {reasonIsAiSupport && <div className="patient-medical-support-info">
                        <strong>Thông tin hỗ trợ được đính kèm khi đặt lịch</strong>
                        <p>{selectedEntry.appointment?.reason}</p>
                        <small>Nội dung này được tách khỏi chẩn đoán chính thức của bác sĩ.</small>
                    </div>}
                </section>

                <section className="patient-medical-section patient-medical-diagnosis" aria-labelledby="patient-doctor-diagnosis-title">
                    <div className="patient-medical-section-heading"><FileText aria-hidden="true" /><h4 id="patient-doctor-diagnosis-title">Chẩn đoán được bác sĩ ghi nhận</h4></div>
                    <p className="patient-medical-diagnosis-value">{selectedEntry.record.finalDiagnosis || "Chưa có chẩn đoán được ký."}</p>
                    <dl className="patient-medical-diagnosis-meta">
                        <div><dt>Bác sĩ xác nhận</dt><dd>BS. {selectedDoctorName}</dd></div>
                        <div><dt>Thời gian xác nhận</dt><dd>{formatDate(selectedEntry.record.signedAt)} lúc {formatTime(selectedEntry.record.signedAt)}</dd></div>
                        {selectedEntry.record.severity && <div><dt>Mức độ được ghi nhận</dt><dd>{SEVERITY_LABELS[selectedEntry.record.severity] || selectedEntry.record.severity}</dd></div>}
                    </dl>
                </section>

                <section className="patient-medical-section" aria-labelledby="patient-doctor-notes-title">
                    <div className="patient-medical-section-heading"><FileText aria-hidden="true" /><h4 id="patient-doctor-notes-title">Ghi chú và hướng điều trị</h4></div>
                    <div className="patient-medical-notes">
                        <div><strong>Nhận xét của bác sĩ</strong><p>{selectedEntry.record.clinicalNotes || "Bác sĩ không ghi thêm nhận xét lâm sàng cho lần khám này."}</p></div>
                        <div><strong>Hướng điều trị</strong><p>{selectedEntry.record.treatmentPlan || "Không có kế hoạch điều trị được ghi nhận."}</p></div>
                    </div>
                </section>

                <section className="patient-medical-section" aria-labelledby="patient-prescription-title">
                    <div className="patient-medical-section-heading"><Pill aria-hidden="true" /><div><h4 id="patient-prescription-title">Đơn thuốc</h4>{selectedEntry.prescription && <p>Ký ngày {formatDate(selectedEntry.prescription.signedAt)}</p>}</div></div>
                    {resourceState.prescriptions.error && <div className="patient-medical-alert is-error" role="alert">Một phần dữ liệu đơn thuốc chưa tải được: {resourceState.prescriptions.error}</div>}
                    {selectedEntry.prescription ? (
                        <PrescriptionContent prescription={selectedEntry.prescription} />
                    ) : resourceState.prescriptions.loading ? (
                        <RecordState tone="loading" title="Đang tải đơn thuốc..." />
                    ) : resourceState.prescriptions.error ? null : !isPatientRecordComplete(selectedEntry) ? (
                        <div className="patient-medical-inline-empty"><strong>Đơn thuốc đang được cập nhật</strong><p>Bác sĩ đang hoàn tất nội dung của lần khám này.</p></div>
                    ) : (
                        <div className="patient-medical-inline-empty"><strong>Không có đơn thuốc cho lần khám này</strong><p>Bác sĩ không kê đơn thuốc sau khi hoàn tất khám.</p></div>
                    )}
                    {selectedEntry.prescription && <button type="button" className="patient-medical-pdf-action" onClick={() => setPdfPrescription(selectedEntry.prescription || null)}><FileText aria-hidden="true" />Xem và in đơn thuốc</button>}
                </section>

                <section className="patient-medical-section patient-medical-followup" aria-labelledby="patient-follow-up-title">
                    <div className="patient-medical-section-heading"><CalendarClock aria-hidden="true" /><h4 id="patient-follow-up-title">Tái khám</h4></div>
                    {selectedEntry.record.followUpAt ? <>
                        <p>Bác sĩ khuyến nghị tái khám vào <strong>{formatDate(selectedEntry.record.followUpAt, { weekday: "long", day: "2-digit", month: "long", year: "numeric" })}</strong>.</p>
                        {selectedEntry.appointment?.followUpReason && <p>Lý do: {selectedEntry.appointment.followUpReason}</p>}
                        <button type="button" onClick={openAppointments}>Xem lịch khám<ArrowRight aria-hidden="true" /></button>
                    </> : <p>Không có khuyến nghị tái khám cho lần khám này.</p>}
                </section>

                <footer className="patient-medical-detail-footer">
                    <p>Liên hệ phòng khám nếu bạn cần hỗ trợ thêm về kết quả hoặc lịch tái khám.</p>
                    <button type="button" onClick={openSupport}><MessageCircle aria-hidden="true" />Liên hệ hỗ trợ</button>
                </footer>
            </article>}
        </div>

        {resourceState.records.error && <StandalonePrescriptions prescriptions={prescriptions} token={token} patient={patient} />}
        {!resourceState.records.error && unmatchedPrescriptions.length > 0 && <StandalonePrescriptions prescriptions={unmatchedPrescriptions} token={token} patient={patient} />}

        <div className="patient-medical-live" role="status" aria-live="polite">
            {selectedEntry ? `Đang xem kết quả ngày ${formatDate(selectedDate)}` : ""}
        </div>

        {pdfPrescription && selectedEntry && <PrescriptionPdfModal
            appointment={selectedEntry.appointment ? { ...selectedEntry.appointment, doctorName: selectedDoctorName } : undefined}
            record={selectedEntry.record}
            prescription={pdfPrescription}
            patient={patient}
            token={token}
            onClose={() => setPdfPrescription(null)}
        />}
    </div>;
}
