import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { FileText, Printer, ZoomIn, ZoomOut, X } from "lucide-react";
import { request } from "../core/api";
import type { Appointment, MedicalRecord, Patient, Prescription } from "../core/types";

const CLINIC_ADDRESS = "32/2 Thống Nhất, phường Gò Vấp, TP. Hồ Chí Minh";
const CLINIC_HOTLINE = "0352 790 904";

function formatDate(value: string) {
    return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function formatTime(value: string) {
    return new Date(value).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function focusableElements(container: HTMLElement) {
    return Array.from(container.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )).filter(element => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true");
}

export function PrescriptionPdfModal({
    appointment,
    record: initialRecord,
    prescription: initialPrescription,
    patient: initialPatient,
    patientName: initialPatientName,
    token,
    onClose,
}: {
    appointment?: Appointment;
    record?: MedicalRecord;
    prescription?: Prescription;
    patient?: Patient;
    patientName?: string;
    token?: string;
    onClose: () => void;
}) {
    const [zoomLevel, setZoomLevel] = useState(1);
    const [record, setRecord] = useState<MedicalRecord | null>(initialRecord || null);
    const [prescription, setPrescription] = useState<Prescription | null>(initialPrescription || null);
    const [patient, setPatient] = useState<Patient | null>(initialPatient || null);
    const [loading, setLoading] = useState(Boolean(token && (!initialRecord || !initialPrescription || !initialPatient)));
    const [loadError, setLoadError] = useState("");
    const [printNotice, setPrintNotice] = useState("");
    const dialogRef = useRef<HTMLDivElement>(null);
    const closeButtonRef = useRef<HTMLButtonElement>(null);
    const previousFocusRef = useRef<HTMLElement | null>(null);

    useEffect(() => {
        if (!token) {
            setLoading(false);
            return;
        }
        const needsRelatedDocument = !initialRecord || !initialPrescription;
        const needsPatientProfile = !initialPatient;
        if (!needsRelatedDocument && !needsPatientProfile) {
            setLoading(false);
            return;
        }
        let active = true;
        setLoading(true);
        setLoadError("");

        // Related resources load independently so one failure never blanks the signed prescription.
        const loadRelatedDocument = async () => {
            let resolvedRecord = initialRecord || null;
            let resolvedPrescription = initialPrescription || null;

            if (!resolvedRecord && initialPrescription) {
                resolvedRecord = await request<MedicalRecord>(`/medical-records/${initialPrescription.recordId}`, token);
                if (active) setRecord(resolvedRecord);
            } else if (!resolvedRecord && appointment) {
                const availableRecords = await request<MedicalRecord[]>("/medical-records/mine", token)
                    .catch(() => request<MedicalRecord[]>("/medical-records/doctor/mine", token));
                resolvedRecord = availableRecords.find(item => item.appointmentId === appointment.id) || null;
                if (active) setRecord(resolvedRecord);
            }

            if (!resolvedPrescription && resolvedRecord) {
                const availablePrescriptions = await request<Prescription[]>("/prescriptions/mine", token);
                resolvedPrescription = availablePrescriptions.find(item => item.recordId === resolvedRecord?.id) || null;
                if (active) setPrescription(resolvedPrescription);
            }
        };

        const loadPatient = async () => {
            if (initialPatient) return;
            const patientId = appointment?.patientId || initialRecord?.patientId || initialPrescription?.patientId;
            const profile = await request<Patient>("/patients/me", token)
                .catch(() => {
                    if (!patientId) throw new Error("Không có mã hồ sơ bệnh nhân.");
                    return request<Patient>(`/patients/${patientId}`, token);
                });
            if (active) setPatient(profile);
        };

        Promise.allSettled([loadRelatedDocument(), loadPatient()])
            .then(results => {
                if (!active) return;
                const rejected = results.find(result => result.status === "rejected") as PromiseRejectedResult | undefined;
                if (rejected) setLoadError((rejected.reason as Error)?.message || "Một phần thông tin đơn thuốc chưa tải được.");
            })
            .finally(() => {
                if (active) setLoading(false);
            });

        return () => { active = false };
    }, [appointment, initialPatient, initialPrescription, initialRecord, token]);

    useEffect(() => {
        previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);

        function handleKeyDown(event: globalThis.KeyboardEvent) {
            if (event.key === "Escape") {
                event.preventDefault();
                onClose();
                return;
            }
            if (event.key !== "Tab" || !dialogRef.current) return;
            const focusable = focusableElements(dialogRef.current);
            if (focusable.length === 0) {
                event.preventDefault();
                dialogRef.current.focus();
                return;
            }
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }

        document.addEventListener("keydown", handleKeyDown);
        return () => {
            window.clearTimeout(focusTimer);
            document.removeEventListener("keydown", handleKeyDown);
            document.body.style.overflow = previousOverflow;
            previousFocusRef.current?.focus();
        };
    }, [onClose]);

    function handlePrint() {
        setPrintNotice("Đã mở hộp thoại in. Bạn có thể chọn Lưu dưới dạng PDF trong trình duyệt.");
        window.print();
    }

    const items = prescription?.items || [];
    const dateSource = appointment?.startAt || record?.signedAt || prescription?.signedAt;
    const docId = prescription?.id || record?.id || appointment?.id;
    const displayName = patient?.fullName || initialPatientName || "Chưa có thông tin";
    const displayPhone = patient?.phone || "Chưa có thông tin";
    const doctorName = appointment?.doctorName || "Bác sĩ phụ trách";
    const hasDocumentData = Boolean(record || prescription || appointment);
    const zoomStyle = { "--prescription-zoom": zoomLevel } as CSSProperties;

    const modal = <div className="clinical-pdf-backdrop" onMouseDown={event => {
        if (event.target === event.currentTarget) onClose();
    }}>
        <div
            className="clinical-pdf-dialog"
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="clinical-pdf-title"
            aria-describedby="clinical-pdf-description"
            tabIndex={-1}
        >
            <header className="clinical-pdf-toolbar no-print">
                <div>
                    <FileText aria-hidden="true" />
                    <span><strong id="clinical-pdf-title">Đơn thuốc đã ký</strong><small id="clinical-pdf-description">Xem nội dung, in hoặc lưu thành PDF bằng trình duyệt.</small></span>
                </div>
                <div className="clinical-pdf-actions">
                    <div className="clinical-pdf-zoom" aria-label="Điều chỉnh kích thước tài liệu">
                        <button type="button" onClick={() => setZoomLevel(value => Math.max(0.9, value - 0.1))} aria-label="Thu nhỏ tài liệu" disabled={zoomLevel <= 0.9}><ZoomOut aria-hidden="true" /></button>
                        <output aria-live="polite">{Math.round(zoomLevel * 100)}%</output>
                        <button type="button" onClick={() => setZoomLevel(value => Math.min(1.4, value + 0.1))} aria-label="Phóng to tài liệu" disabled={zoomLevel >= 1.4}><ZoomIn aria-hidden="true" /></button>
                    </div>
                    <button type="button" className="clinical-pdf-print" onClick={handlePrint} disabled={!hasDocumentData}><Printer aria-hidden="true" />In hoặc lưu PDF</button>
                    <button type="button" className="clinical-pdf-close" ref={closeButtonRef} onClick={onClose} aria-label="Đóng cửa sổ đơn thuốc"><X aria-hidden="true" /></button>
                </div>
            </header>

            <div className="clinical-pdf-scroll">
                {loading && !hasDocumentData ? (
                    <div className="clinical-pdf-state is-loading" role="status" aria-live="polite">
                        <div aria-hidden="true"><i /><i /><i /></div>
                        <strong>Đang tải đơn thuốc...</strong>
                        <p>Nội dung sẽ xuất hiện khi các dịch vụ phản hồi.</p>
                    </div>
                ) : !hasDocumentData ? (
                    <div className="clinical-pdf-state is-empty" role="status">
                        <FileText aria-hidden="true" />
                        <strong>Chưa có nội dung đơn thuốc</strong>
                        <p>Không tìm thấy hồ sơ hoặc đơn thuốc để hiển thị.</p>
                    </div>
                ) : <>
                    {loading && <div className="clinical-pdf-inline-status" role="status" aria-live="polite">Đang bổ sung thông tin hồ sơ...</div>}
                    {loadError && <div className="clinical-pdf-inline-status is-error" role="alert">Một phần thông tin chưa tải được: {loadError}</div>}
                    <div className="clinical-pdf-scale" style={zoomStyle}>
                        <article className="clinical-pdf-paper printable-area" aria-label="Nội dung đơn thuốc điện tử">
                            <header className="clinical-pdf-document-header">
                                <div>
                                    <strong>Derm Clinic</strong>
                                    <p>Phòng khám chuyên khoa Da liễu</p>
                                    <address>{CLINIC_ADDRESS}<br />Hotline: {CLINIC_HOTLINE}</address>
                                </div>
                                <dl>
                                    <div><dt>Mã đơn</dt><dd>{docId ? `RX-${docId.slice(0, 8).toUpperCase()}` : "Chưa có"}</dd></div>
                                    {dateSource && <div><dt>Ngày kê đơn</dt><dd>{formatDate(dateSource)}</dd></div>}
                                </dl>
                            </header>

                            <div className="clinical-pdf-document-title">
                                <h1>Đơn thuốc điện tử</h1>
                                <p>Nội dung được trình bày theo dữ liệu bác sĩ đã ký trong hệ thống.</p>
                            </div>

                            <section className="clinical-pdf-patient" aria-labelledby="clinical-pdf-patient-title">
                                <h2 id="clinical-pdf-patient-title">Thông tin người bệnh</h2>
                                <dl>
                                    <div><dt>Họ và tên</dt><dd>{displayName}</dd></div>
                                    <div><dt>Số điện thoại</dt><dd>{displayPhone}</dd></div>
                                    <div><dt>Bác sĩ kê đơn</dt><dd>BS. {doctorName}</dd></div>
                                    {dateSource && <div><dt>Thời gian</dt><dd>{formatTime(dateSource)}, {formatDate(dateSource)}</dd></div>}
                                    <div className="is-wide"><dt>Chẩn đoán được ghi nhận</dt><dd>{record?.finalDiagnosis || "Chưa tải được kết luận từ hồ sơ khám."}</dd></div>
                                </dl>
                            </section>

                            <section className="clinical-pdf-prescription" aria-labelledby="clinical-pdf-prescription-title">
                                <h2 id="clinical-pdf-prescription-title">Thuốc và hướng dẫn sử dụng</h2>
                                {items.length > 0 ? <ol>
                                    {items.map((item, index) => <li key={`${item.drugName}-${index}`}>
                                        <div className="clinical-pdf-drug-name"><span>{index + 1}</span><div><strong>{item.drugName}</strong>{item.dosage && <p>{item.dosage}</p>}</div></div>
                                        <dl>
                                            {item.frequency && <div><dt>Tần suất</dt><dd>{item.frequency}</dd></div>}
                                            {item.duration && <div><dt>Thời gian dùng</dt><dd>{item.duration}</dd></div>}
                                        </dl>
                                        {item.instructions && <div className="clinical-pdf-drug-instruction"><strong>Cách dùng theo đơn</strong><p>{item.instructions}</p></div>}
                                    </li>)}
                                </ol> : <div className="clinical-pdf-document-empty">Không có thuốc được ghi nhận trong dữ liệu đơn này.</div>}
                            </section>

                            {prescription?.instructions && <section className="clinical-pdf-instructions" aria-labelledby="clinical-pdf-instructions-title">
                                <h2 id="clinical-pdf-instructions-title">Hướng dẫn chung theo đơn</h2>
                                <p>{prescription.instructions}</p>
                            </section>}

                            {record?.treatmentPlan && <section className="clinical-pdf-treatment" aria-labelledby="clinical-pdf-treatment-title">
                                <h2 id="clinical-pdf-treatment-title">Hướng điều trị được ghi nhận</h2>
                                <p>{record.treatmentPlan}</p>
                            </section>}

                            <footer className="clinical-pdf-document-footer">
                                <div><span>Hồ sơ được ký lúc</span><strong>{prescription?.signedAt ? `${formatTime(prescription.signedAt)}, ${formatDate(prescription.signedAt)}` : record?.signedAt ? `${formatTime(record.signedAt)}, ${formatDate(record.signedAt)}` : "Chưa có thông tin"}</strong></div>
                                <div><span>Bác sĩ phụ trách</span><strong>BS. {doctorName}</strong></div>
                            </footer>
                        </article>
                    </div>
                </>}
            </div>

            {printNotice && <div className="clinical-pdf-print-notice no-print" role="status" aria-live="polite">{printNotice}</div>}
        </div>
    </div>;

    return createPortal(modal, document.body);
}
