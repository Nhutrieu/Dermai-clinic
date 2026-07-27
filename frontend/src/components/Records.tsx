import { useMemo, useState } from "react";
import { Printer } from "lucide-react";
import type { MedicalRecord, Patient, Prescription } from "../core/types";
import { State } from "./Ui";
import { PrescriptionPdfModal } from "./PrescriptionPdfModal";

export function RecordList({ records, patients }: { records: MedicalRecord[]; patients: Record<string, Patient> }) {
    const [query, setQuery] = useState("");
    const [period, setPeriod] = useState("all");
    const [order, setOrder] = useState("newest");

    const normalized = query.trim().toLocaleLowerCase("vi");
    const cutoff = period === "all" ? 0 : Date.now() - Number(period) * 86400000;
    const filtered = records.filter(r => {
        const patientName = patients[r.patientId]?.fullName || "Hồ sơ của tôi";
        const matches = !normalized || `${patientName} ${r.finalDiagnosis} ${r.clinicalNotes || ""} ${r.treatmentPlan || ""}`.toLocaleLowerCase("vi").includes(normalized);
        return matches && (!cutoff || new Date(r.signedAt).getTime() >= cutoff);
    }).sort((a, b) => (new Date(b.signedAt).getTime() - new Date(a.signedAt).getTime()) * (order === "newest" ? 1 : -1));

    return (
        <section className="panel records medical-record-browser">
            <div className="record-heading">
                <div>
                    <h2>Hồ sơ y khoa đã ký</h2>
                    <p>{filtered.length} / {records.length} hồ sơ</p>
                </div>
                <div className="record-filters">
                    <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Tìm bệnh nhân, chẩn đoán..." />
                    <select value={period} onChange={e => setPeriod(e.target.value)}>
                        <option value="all">Tất cả thời gian</option>
                        <option value="30">30 ngày gần đây</option>
                        <option value="90">3 tháng gần đây</option>
                        <option value="365">1 năm gần đây</option>
                    </select>
                    <select value={order} onChange={e => setOrder(e.target.value)}>
                        <option value="newest">Mới nhất trước</option>
                        <option value="oldest">Cũ nhất trước</option>
                    </select>
                </div>
            </div>

            {records.length === 0 ? (
                <State text="Chưa có hồ sơ y khoa." />
            ) : filtered.length === 0 ? (
                <State text="Không tìm thấy hồ sơ phù hợp." />
            ) : (
                filtered.map(r => {
                    const pName = patients[r.patientId]?.fullName || "Hồ sơ của tôi";
                    return (
                        <article key={r.id}>
                            <div>
                                <b>{pName}</b>
                                <span>{r.severity}</span>
                            </div>
                            <h3>{r.finalDiagnosis}</h3>
                            <p>{r.clinicalNotes || "Không có ghi chú lâm sàng"}</p>
                            {r.treatmentPlan && <p><b>Kế hoạch điều trị:</b> {r.treatmentPlan}</p>}
                            {r.followUpAt && <p><b>Tái khám:</b> {new Date(r.followUpAt).toLocaleString("vi-VN")}</p>}
                            <small>Ký lúc {new Date(r.signedAt).toLocaleString("vi-VN")}</small>
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
