import { FormEvent, useState } from "react";
import { request } from "../../core/api";
import type { RealtimeConnectionState } from "../../core/realtime";
import type { Appointment, Doctor, MedicalRecord, Patient, WorkSchedule } from "../../core/types";
import DoctorDashboard, { type DoctorDashboardResources } from "./DoctorDashboard";
import DoctorSharedAi from "./DoctorSharedAi";

type DoctorViewProps = {
    token: string;
    doctor: Doctor;
    appointments: Appointment[];
    records?: MedicalRecord[];
    patients: Record<string, Patient>;
    work: WorkSchedule[];
    leave?: any[];
    resources?: DoctorDashboardResources;
    realtimeState?: RealtimeConnectionState;
    lastUpdated?: Date;
    retry?: () => void;
    transition: (id: string, action: "start" | "complete") => Promise<void>;
    requireFollowUp: (id: string, reason: string, notBefore: string) => Promise<void>;
};

export default function DoctorView({ token, doctor, appointments, records = [], patients, work, resources = { appointments: { loading: false, error: "" }, records: { loading: false, error: "" }, patients: { loading: false, error: "" }, schedule: { loading: false, error: "" } }, realtimeState = "connected", lastUpdated = new Date(), retry = () => {}, transition, requireFollowUp }: DoctorViewProps) {
    const [selected, setSelected] = useState<Appointment | null>(null);

    async function startConsultation(appointmentId: string) {
        await transition(appointmentId, "start");
        const appointment = appointments.find(item => item.id === appointmentId);
        if (appointment) setSelected({ ...appointment, status: "IN_PROGRESS" });
    }

    return <>
        <DoctorDashboard token={token} doctor={doctor} appointments={appointments} records={records} patients={patients} work={work} resources={resources} realtimeState={realtimeState} lastUpdated={lastUpdated} onRetry={retry} onStart={startConsultation} onComplete={appointmentId => transition(appointmentId, "complete")} onContinue={setSelected} />
        {selected && <Consultation token={token} appointment={selected} patient={patients[selected.patientId]} close={() => setSelected(null)} complete={() => transition(selected.id, "complete")} requireFollowUp={(reason, notBefore) => requireFollowUp(selected.id, reason, notBefore)} />}
    </>;
}
type PrescriptionDraft = { drugName: string; dosage: string; frequency: string; duration: string; instructions: string };
function Consultation({ token, appointment, patient, close, complete, requireFollowUp }: { token: string; appointment: Appointment; patient?: Patient; close: () => void; complete: () => Promise<void>; requireFollowUp: (reason: string, notBefore: string) => Promise<void> }) {
    const emptyDrug = (): PrescriptionDraft => ({ drugName: "", dosage: "", frequency: "", duration: "", instructions: "" });
    const [diagnosis, setDiagnosis] = useState(""); const [notes, setNotes] = useState(""); const [plan, setPlan] = useState(""); const [severity, setSeverity] = useState("MILD"); const [recordId, setRecordId] = useState(""); const [items, setItems] = useState<PrescriptionDraft[]>([emptyDrug()]); const [rxInstructions, setRxInstructions] = useState(""); const [prescriptionSigned, setPrescriptionSigned] = useState(false); const [needFollowUp, setNeedFollowUp] = useState(false); const [followDate, setFollowDate] = useState(""); const [followReason, setFollowReason] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
    function updateItem(index: number, field: keyof PrescriptionDraft, value: string) { setItems(current => current.map((item, i) => i === index ? { ...item, [field]: value } : item)) }
    async function saveRecord(e: FormEvent) { e.preventDefault(); if (needFollowUp && (!followDate || !followReason.trim())) { setMessage("Hãy nhập ngày khuyến nghị và lý do tái khám."); return } setMessage(""); try { const r = await request<{ id: string }>("/medical-records", token, { method: "POST", body: JSON.stringify({ appointmentId: appointment.id, patientId: appointment.patientId, finalDiagnosis: diagnosis, clinicalNotes: notes || null, treatmentPlan: plan || null, severity, followUpAt: needFollowUp ? new Date(`${followDate}T00:00:00`).toISOString() : null }) }); setRecordId(r.id); setMessage("Đã ký hồ sơ y khoa.") } catch (x) { setMessage((x as Error).message) } }
    async function savePrescription(e: FormEvent) { e.preventDefault(); setMessage(""); try { await request("/prescriptions", token, { method: "POST", body: JSON.stringify({ recordId, patientId: appointment.patientId, instructions: rxInstructions || null, items }) }); setPrescriptionSigned(true); setMessage("Đã ký đơn thuốc với " + items.length + " thuốc.") } catch (x) { setMessage((x as Error).message) } }
    async function finish() { setBusy(true); setMessage(""); try { if (needFollowUp) await requireFollowUp(followReason, new Date(`${followDate}T00:00:00`).toISOString()); else await complete(); window.dispatchEvent(new Event("appointments-changed")); close(); } catch (x) { setMessage((x as Error).message); } finally { setBusy(false); } }
    return <section className="panel consultation"><div className="consult-head"><div><h2>Ca khám: {patient?.fullName || appointment.patientId}</h2><p>Chẩn đoán và đơn thuốc chỉ do bác sĩ chịu trách nhiệm.</p></div><button onClick={close}>Đóng</button></div><DoctorSharedAi token={token} appointmentId={appointment.id} />{!recordId ? <form onSubmit={saveRecord}><label>Chẩn đoán cuối<textarea required value={diagnosis} onChange={e => setDiagnosis(e.target.value)} /></label><label>Ghi chú lâm sàng<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label><label>Kế hoạch điều trị<textarea value={plan} onChange={e => setPlan(e.target.value)} /></label><label>Mức độ<select value={severity} onChange={e => setSeverity(e.target.value)}><option value="MILD">Nhẹ</option><option value="MODERATE">Trung bình</option><option value="SEVERE">Nặng</option><option value="URGENT">Khẩn cấp</option></select></label><label className="follow-check"><input type="checkbox" checked={needFollowUp} onChange={e => setNeedFollowUp(e.target.checked)} /> Yêu cầu bệnh nhân tái khám</label>{needFollowUp && <div className="follow-box"><label>Ngày bác sĩ khuyến nghị<input type="date" required value={followDate} onChange={e => setFollowDate(e.target.value)} /></label><label>Lý do tái khám<input required value={followReason} onChange={e => setFollowReason(e.target.value)} /></label><p>Bác sĩ chỉ đưa ra ngày khuyến nghị. Bệnh nhân sẽ tự chọn giờ còn trống sau khi xem hồ sơ.</p></div>}<button className="primary" disabled={needFollowUp && (!followDate || !followReason.trim())}>Ký hồ sơ</button></form> : <div className="prescription-stage"><h3>Đơn thuốc — chỉ bác sĩ</h3>{!prescriptionSigned && <form onSubmit={savePrescription}>{items.map((item, index) => <div className="drug-row" key={index}><label>Tên thuốc<input required value={item.drugName} onChange={e => updateItem(index, "drugName", e.target.value)} /></label><label>Liều dùng<input required value={item.dosage} onChange={e => updateItem(index, "dosage", e.target.value)} /></label><label>Tần suất<input value={item.frequency} onChange={e => updateItem(index, "frequency", e.target.value)} /></label><label>Thời gian dùng<input value={item.duration} onChange={e => updateItem(index, "duration", e.target.value)} /></label><label>Hướng dẫn riêng<input value={item.instructions} onChange={e => updateItem(index, "instructions", e.target.value)} /></label>{items.length > 1 && <button type="button" onClick={() => setItems(items.filter((_, i) => i !== index))}>Xóa thuốc</button>}</div>)}<label>Hướng dẫn chung<textarea value={rxInstructions} onChange={e => setRxInstructions(e.target.value)} /></label><div className="form-actions"><button type="button" onClick={() => setItems([...items, emptyDrug()])}>Thêm thuốc</button><button className="primary">Ký đơn thuốc</button></div></form>}<div className="finish-visit"><p>{needFollowUp ? `Bác sĩ yêu cầu tái khám từ ngày ${new Date(`${followDate}T00:00:00`).toLocaleDateString("vi-VN")}; bệnh nhân tự chọn giờ.` : "Không yêu cầu tái khám"}</p><button className="primary" disabled={busy} onClick={finish}>{busy ? "Đang hoàn thành..." : prescriptionSigned ? "Hoàn thành ca khám" : "Hoàn thành không kê đơn"}</button></div></div>}{message && <p className="form-message">{message}</p>}</section>
}
