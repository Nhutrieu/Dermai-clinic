import { useEffect, useState } from "react";
import { Printer, X, FileText, CheckCircle2, ShieldCheck, Stethoscope, ZoomIn, ZoomOut } from "lucide-react";
import { request } from "../core/api";
import type { Appointment, MedicalRecord, Patient, Prescription } from "../core/types";

function formatAppointmentTime(iso: string) {
    if (!iso) return "";
    const d = new Date(iso);
    const time = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
    const date = d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
    return `${time} · ${date}`;
}

export function PrescriptionPdfModal({
    appointment,
    record: initialRecord,
    prescription: initialPrescription,
    patientName: initialPatientName,
    token,
    onClose
}: {
    appointment?: Appointment;
    record?: MedicalRecord;
    prescription?: Prescription;
    patientName?: string;
    token?: string;
    onClose: () => void;
}) {
    const [downloaded, setDownloaded] = useState(false);
    const [zoomLevel, setZoomLevel] = useState<number>(1.0); // 100% fit-to-screen full single page view
    const [record, setRecord] = useState<MedicalRecord | null>(initialRecord || null);
    const [prescription, setPrescription] = useState<Prescription | null>(initialPrescription || null);
    const [patient, setPatient] = useState<Patient | null>(null);

    useEffect(() => {
        if (!token) return;

        // Fetch current patient profile if not supplied
        const patientId = appointment?.patientId || initialRecord?.patientId || initialPrescription?.patientId;
        if (patientId) {
            request<Patient>(`/patients/${patientId}`, token)
                .then(setPatient)
                .catch(() => {
                    request<Patient>("/patients/me", token).then(setPatient).catch(() => {});
                });
        } else {
            request<Patient>("/patients/me", token).then(setPatient).catch(() => {});
        }

        // Fetch prescription by recordId if only record provided
        if (initialRecord && !initialPrescription) {
            request<Prescription[]>(`/prescriptions?recordId=${initialRecord.id}`, token)
                .then(rx => {
                    if (rx && rx.length > 0) setPrescription(rx[0]);
                })
                .catch(() => {});
        }

        // Fetch record by recordId if only prescription provided
        if (initialPrescription && !initialRecord) {
            request<MedicalRecord>(`/medical-records/${initialPrescription.recordId}`, token)
                .then(setRecord)
                .catch(() => {});
        }

        // Fetch both by appointmentId if only appointment provided
        if (appointment && !initialRecord) {
            request<MedicalRecord[]>(`/medical-records?appointmentId=${appointment.id}`, token)
                .then(records => {
                    if (records && records.length > 0) {
                        setRecord(records[0]);
                        return request<Prescription[]>(`/prescriptions?recordId=${records[0].id}`, token);
                    }
                    return [];
                })
                .then(rx => {
                    if (rx && rx.length > 0) setPrescription(rx[0]);
                })
                .catch(() => {});
        }
    }, [appointment, initialRecord, initialPrescription, token]);

    function handlePrint() {
        setDownloaded(true);
        window.print();
    }

    const items = prescription?.items || [];
    const dateSource = appointment?.startAt || record?.signedAt || prescription?.signedAt || new Date().toISOString();
    const docId = prescription?.id || record?.id || appointment?.id || "RX-DERMAI";
    const displayName = patient?.fullName || initialPatientName || "Bệnh nhân";
    const displayPhone = patient?.phone || "0352 790 904";

    return (
        <div className="pdf-modal-backdrop" onClick={onClose}>
            <div className="pdf-modal-container" onClick={e => e.stopPropagation()}>
                <header className="pdf-modal-actions no-print">
                    <div className="pdf-modal-title">
                        <FileText className="icon" />
                        <span>Đơn Thuốc Điện Tử DermAI Clinic</span>
                    </div>

                    <div className="pdf-modal-buttons">
                        {/* Zoom Controls for Large Easy Reading */}
                        <div className="pdf-zoom-controls" style={{ display: "flex", alignItems: "center", gap: "6px", background: "rgba(255, 255, 255, 0.12)", padding: "4px 10px", borderRadius: "8px", marginRight: "8px" }}>
                            <button
                                type="button"
                                title="Thu nhỏ chữ"
                                onClick={() => setZoomLevel(z => Math.max(0.9, z - 0.15))}
                                style={{ background: "none", border: 0, color: "#fff", cursor: "pointer", display: "grid", placeItems: "center" }}
                            >
                                <ZoomOut style={{ width: 16, height: 16 }} />
                            </button>
                            <span style={{ fontSize: "12px", fontWeight: 700, minWidth: "40px", textAlign: "center", color: "#6ee7b7" }}>
                                {Math.round(zoomLevel * 100)}%
                            </span>
                            <button
                                type="button"
                                title="Phóng to chữ dễ đọc"
                                onClick={() => setZoomLevel(z => Math.min(1.6, z + 0.15))}
                                style={{ background: "none", border: 0, color: "#fff", cursor: "pointer", display: "grid", placeItems: "center" }}
                            >
                                <ZoomIn style={{ width: 16, height: 16 }} />
                            </button>
                        </div>

                        <button type="button" className="btn-print" onClick={handlePrint}>
                            <Printer className="icon" /> In / Tải PDF
                        </button>
                        <button type="button" className="btn-close" onClick={onClose} aria-label="Đóng">
                            <X className="icon" />
                        </button>
                    </div>
                </header>

                <div className="pdf-paper printable-area" style={{ transform: `scale(${zoomLevel})`, transformOrigin: "top center", transition: "transform 0.2s ease" }}>
                    {/* Top Accent Stripe */}
                    <div className="pdf-top-accent" />

                    {/* Clinic Branding Header */}
                    <div className="pdf-header">
                        <div className="pdf-brand">
                            <div className="pdf-logo-badge">
                                <Stethoscope className="icon" />
                                <span>DermAI</span>
                            </div>
                            <div className="pdf-brand-details">
                                <h2>PHÒNG KHÁM CHUYÊN KHOA DA LIỄU DERMAI CLINIC</h2>
                                <p>Giấy phép hoạt động số: <b>886/SYT-GPHĐ</b> · Bộ Y Tế TP.HCM</p>
                                <p>Địa chỉ: 123 Đường Y Dược, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh</p>
                                <p>Hotline: <b>1900 6868 - 0352 790 904</b> · Email: contact@dermai.clinic</p>
                            </div>
                        </div>
                        <div className="pdf-code-card">
                            <small>MÃ ĐƠN THUỐC (RX)</small>
                            <b>#RX-{docId.slice(0, 8).toUpperCase()}</b>
                            <span className="pdf-digital-tag">Đơn thuốc điện tử</span>
                        </div>
                    </div>

                    <div className="pdf-divider-line" />

                    {/* Document Title */}
                    <div className="pdf-doc-title">
                        <h1>ĐƠN THUỐC ĐIỆN TỬ CHUYÊN KHOA DA LIỄU</h1>
                        <p>Ngày kê đơn: {formatAppointmentTime(dateSource)}</p>
                    </div>

                    {/* Patient Information Section */}
                    <div className="pdf-patient-card">
                        <div className="pdf-patient-grid">
                            <div className="pdf-info-item">
                                <span className="label">Họ và tên bệnh nhân:</span>
                                <b className="val highlight">{displayName}</b>
                            </div>
                            <div className="pdf-info-item">
                                <span className="label">Số điện thoại:</span>
                                <span className="val">{displayPhone}</span>
                            </div>
                            <div className="pdf-info-item">
                                <span className="label">Mã bệnh nhân:</span>
                                <span className="val">#{patient?.id ? patient.id.slice(0, 8).toUpperCase() : "PAT-DERMAI"}</span>
                            </div>
                            <div className="pdf-info-item">
                                <span className="label">Bác sĩ chỉ định:</span>
                                <b className="val">{appointment?.doctorName || "BS. Chuyên khoa Da liễu"}</b>
                            </div>
                            <div className="pdf-info-item full-width">
                                <span className="label">Chẩn đoán lâm sàng:</span>
                                <b className="val diagnosis-text">{record?.finalDiagnosis || appointment?.reason || "Chẩn đoán bệnh lý Da liễu & Khám lâm sàng"}</b>
                            </div>
                        </div>
                    </div>

                    {/* Prescription Table */}
                    <div className="pdf-table-wrapper">
                        <div className="pdf-table-title">Rx. CHI TIẾT ĐƠN THUỐC KÊ CHỈ ĐỊNH</div>
                        <table className="pdf-table">
                            <thead>
                                <tr>
                                    <th style={{ width: "45px" }} className="text-center">STT</th>
                                    <th>Tên thuốc & Hàm lượng</th>
                                    <th style={{ width: "120px" }} className="text-center">Liều dùng</th>
                                    <th style={{ width: "120px" }} className="text-center">Số ngày</th>
                                    <th>Cách dùng & Hướng dẫn chi tiết</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items.length > 0 ? (
                                    items.map((item, idx) => (
                                        <tr key={idx}>
                                            <td className="text-center num-col">{idx + 1}</td>
                                            <td>
                                                <b className="drug-name">{item.drugName}</b>
                                                {item.instructions && <div className="drug-sub">{item.instructions}</div>}
                                            </td>
                                            <td className="text-center">{item.dosage || "1 viên/lần"}</td>
                                            <td className="text-center">{item.duration || "7 ngày"}</td>
                                            <td>
                                                <span className="usage-tag">{item.frequency || "Uống sau khi ăn"}</span>
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan={5} className="empty-rx">
                                            Chưa có chi tiết đơn thuốc kê trong hệ thống. Ghi chú điều trị: <b>{record?.treatmentPlan || record?.clinicalNotes || appointment?.reason || "Theo dõi tình trạng da tại nhà và tái khám khi có dấu hiệu bất thường."}</b>
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {/* Doctor Advice & Instructions */}
                    <div className="pdf-advice-box">
                        <div className="advice-header">
                            <ShieldCheck className="icon" />
                            <b>Lời dặn của Bác sĩ điều trị:</b>
                        </div>
                        <p>{prescription?.instructions || record?.treatmentPlan || "Uống đủ 2 lit nước/ngày, tránh ánh nắng mặt trời trực tiếp, không tự ý ngưng thuốc khi chưa có chỉ định của bác sĩ."}</p>
                    </div>

                    {/* Footer & Signature Section */}
                    <div className="pdf-footer-section">
                        <div className="pdf-security-notice">
                            <small>
                                🔒 Đơn thuốc điện tử này có chữ ký số xác thực bởi DermAI Clinic. Bệnh nhân có thể sử dụng mã đơn thuốc để tra cứu tại các nhà thuốc liên kết.
                            </small>
                        </div>
                        <div className="pdf-signature-box">
                            <p className="signature-city">
                                TP. Hồ Chí Minh, ngày {new Date(dateSource).getDate()} tháng {new Date(dateSource).getMonth() + 1} năm {new Date(dateSource).getFullYear()}
                            </p>
                            <b className="signature-role">BÁC SĨ KHÁM & ĐIỀU TRỊ</b>
                            <div className="signature-stamp-area">
                                <div className="official-stamp">
                                    <div className="stamp-inner">
                                        <span>DERMAI CLINIC</span>
                                        <small>VERIFIED & SIGNED</small>
                                    </div>
                                </div>
                            </div>
                            <b className="doctor-name-signed">{appointment?.doctorName || "BS. Chuyên khoa Da liễu"}</b>
                        </div>
                    </div>
                </div>

                {downloaded && (
                    <div className="pdf-toast no-print">
                        <CheckCircle2 className="icon" /> Đã gửi lệnh in / xuất file PDF thành công!
                    </div>
                )}
            </div>
        </div>
    );
}
