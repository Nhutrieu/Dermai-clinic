import { useMemo, useState } from "react";
import { CalendarDays, Printer, Search } from "lucide-react";
import type { MedicalRecord, Patient, Prescription } from "../core/types";
import { State } from "./Ui";
import { PrescriptionPdfModal } from "./PrescriptionPdfModal";

export function RecordList({ records, patients }: { records: MedicalRecord[]; patients: Record<string, Patient> }) {
    const [query, setQuery] = useState("");
    const [period, setPeriod] = useState("all");
    const [order, setOrder] = useState("newest");

    const filtered = useMemo(() => {
        const normalized = query.trim().toLocaleLowerCase("vi");
        const cutoff = period === "all" ? 0 : Date.now() - Number(period) * 86400000;

        return records.filter(record => {
            const patientName = patients[record.patientId]?.fullName || "Hồ sơ của tôi";
            const searchableText = `${patientName} ${record.finalDiagnosis} ${record.clinicalNotes || ""} ${record.treatmentPlan || ""}`.toLocaleLowerCase("vi");
            return (!normalized || searchableText.includes(normalized))
                && (!cutoff || new Date(record.signedAt).getTime() >= cutoff);
        }).sort((a, b) => (
            new Date(b.signedAt).getTime() - new Date(a.signedAt).getTime()
        ) * (order === "newest" ? 1 : -1));
    }, [order, patients, period, query, records]);

    const severityLabel: Record<string, string> = {
        MILD: "Nhẹ",
        MODERATE: "Trung bình",
        SEVERE: "Nặng",
        URGENT: "Khẩn cấp",
    };

    const formatSignedAt = (value: string) => new Intl.DateTimeFormat("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(new Date(value));

    const getInitials = (name: string) => name
        .trim()
        .split(/\s+/)
        .slice(-2)
        .map(part => part.charAt(0))
        .join("")
        .toLocaleUpperCase("vi");

    return (
        <section className="panel records medical-record-browser">
            <header className="record-heading">
                <div>
                    <h2>Hồ sơ y khoa đã ký</h2>
                    <p>Tra cứu chẩn đoán, ghi chú và kế hoạch điều trị đã lưu.</p>
                </div>
                <output className="record-result-count" aria-live="polite">
                    <strong>{filtered.length}</strong>
                    <span>trên {records.length} hồ sơ</span>
                </output>
            </header>

            <div className="record-filters" aria-label="Bộ lọc hồ sơ y khoa">
                <label className="record-search-field">
                    <span>Tìm hồ sơ</span>
                    <span className="record-control-with-icon">
                        <Search aria-hidden="true" />
                        <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Tên bệnh nhân hoặc chẩn đoán" />
                    </span>
                </label>
                <label>
                    <span>Thời gian</span>
                    <select value={period} onChange={e => setPeriod(e.target.value)}>
                        <option value="all">Tất cả thời gian</option>
                        <option value="30">30 ngày gần đây</option>
                        <option value="90">3 tháng gần đây</option>
                        <option value="365">1 năm gần đây</option>
                    </select>
                </label>
                <label>
                    <span>Sắp xếp</span>
                    <select value={order} onChange={e => setOrder(e.target.value)}>
                        <option value="newest">Mới nhất trước</option>
                        <option value="oldest">Cũ nhất trước</option>
                    </select>
                </label>
            </div>

            {records.length === 0 ? (
                <State text="Chưa có hồ sơ y khoa." />
            ) : filtered.length === 0 ? (
                <State text="Không tìm thấy hồ sơ phù hợp." />
            ) : (
                filtered.map(r => {
                    const pName = patients[r.patientId]?.fullName || "Hồ sơ của tôi";
                    return (
                        <article className="medical-record-row" key={r.id}>
                            <header className="medical-record-row-header">
                                <span className="medical-record-avatar" aria-hidden="true">{getInitials(pName)}</span>
                                <div>
                                    <h3>{pName}</h3>
                                    <time dateTime={r.signedAt}><CalendarDays aria-hidden="true" />Đã ký {formatSignedAt(r.signedAt)}</time>
                                </div>
                                <span className="medical-record-severity" data-severity={r.severity}>
                                    {severityLabel[r.severity] || r.severity}
                                </span>
                            </header>

                            <div className="medical-record-summary">
                                <div className="medical-record-diagnosis">
                                    <span>Chẩn đoán</span>
                                    <strong>{r.finalDiagnosis}</strong>
                                </div>
                                <div>
                                    <span>Ghi chú lâm sàng</span>
                                    <p>{r.clinicalNotes || "Chưa ghi nhận"}</p>
                                </div>
                                <div>
                                    <span>Kế hoạch điều trị</span>
                                    <p>{r.treatmentPlan || "Chưa ghi nhận"}</p>
                                </div>
                            </div>

                            {r.followUpAt && (
                                <p className="medical-record-follow-up">
                                    <strong>Tái khám dự kiến</strong>
                                    <time dateTime={r.followUpAt}>{new Date(r.followUpAt).toLocaleString("vi-VN")}</time>
                                </p>
                            )}
                        </article>
                    );
                })
            )}
        </section>
    );
}

export function PrescriptionList({ prescriptions, token }: { prescriptions: Prescription[]; token?: string }) {
    const [selectedPrescription, setSelectedPrescription] = useState<Prescription | null>(null);

    return (
        <section className="panel records">
            <h2>Đơn thuốc đã ký</h2>
            {prescriptions.length === 0 ? (
                <State text="Chưa có đơn thuốc trong database." />
            ) : (
                prescriptions.map(rx => (
                    <article key={rx.id}>
                        <div className="record-card-header">
                            <div>
                                <b>Đơn thuốc điện tử</b>
                                <span>Ký lúc: {new Date(rx.signedAt).toLocaleString("vi-VN")}</span>
                            </div>
                            <button type="button" className="btn-print-pdf-sm" onClick={() => setSelectedPrescription(rx)}>
                                <Printer className="icon" /> In / Tải PDF
                            </button>
                        </div>
                        {rx.items.map((item, index) => (
                            <p key={index}>{item.drugName} · {[item.dosage, item.frequency, item.duration].filter(Boolean).join(" · ")}</p>
                        ))}
                        {rx.instructions && <small>{rx.instructions}</small>}
                    </article>
                ))
            )}

            {selectedPrescription && (
                <PrescriptionPdfModal
                    prescription={selectedPrescription}
                    token={token}
                    onClose={() => setSelectedPrescription(null)}
                />
            )}
        </section>
    );
}
