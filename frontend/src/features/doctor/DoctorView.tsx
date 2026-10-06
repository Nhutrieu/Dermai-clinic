import { FormEvent, useEffect, useRef, useState } from "react";
import { request } from "../../core/api";
import type { RealtimeConnectionState } from "../../core/realtime";
import type { Appointment, AppointmentPerformedServices, ClinicService, Doctor, MedicalRecord, Medicine, Patient, WorkSchedule } from "../../core/types";
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
    recordSaved?: (record: MedicalRecord) => void;
};

export default function DoctorView({ token, doctor, appointments, records = [], patients, work, resources = { appointments: { loading: false, error: "" }, records: { loading: false, error: "" }, patients: { loading: false, error: "" }, schedule: { loading: false, error: "" } }, realtimeState = "connected", lastUpdated = new Date(), retry = () => {}, transition, requireFollowUp, recordSaved = () => {} }: DoctorViewProps) {
    const [selected, setSelected] = useState<Appointment | null>(null);

    async function startConsultation(appointmentId: string) {
        await transition(appointmentId, "start");
        const appointment = appointments.find(item => item.id === appointmentId);
        if (appointment) setSelected({ ...appointment, status: "IN_PROGRESS" });
    }

    return <>
        <DoctorDashboard token={token} doctor={doctor} appointments={appointments} records={records} patients={patients} work={work} resources={resources} realtimeState={realtimeState} lastUpdated={lastUpdated} onRetry={retry} onStart={startConsultation} onContinue={setSelected} />
        {selected && <Consultation token={token} appointment={selected} patient={patients[selected.patientId]} existingRecord={records.find(record => record.appointmentId === selected.id)} close={() => setSelected(null)} complete={() => transition(selected.id, "complete")} requireFollowUp={(reason, notBefore) => requireFollowUp(selected.id, reason, notBefore)} recordSaved={recordSaved} />}
    </>;
}
type PrescriptionDraft = { medicineId: string; drugName: string; dosage: string; frequency: string; duration: string; quantityRequested: number; instructions: string };

function normalizeMedicineSearch(value: string) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("vi-VN").trim();
}

function MedicinePicker({ medicines, value, index, onChange }: { medicines: Medicine[]; value: string; index: number; onChange: (medicine?: Medicine) => void }) {
    const selected = medicines.find(medicine => medicine.id === value);
    const [query, setQuery] = useState(selected ? `${selected.name} — ${selected.sku}` : "");
    const [open, setOpen] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const normalizedQuery = normalizeMedicineSearch(query);
    const results = medicines.filter(medicine => !normalizedQuery || normalizeMedicineSearch(`${medicine.name} ${medicine.sku} ${medicine.unit}`).includes(normalizedQuery)).slice(0, 12);

    useEffect(() => {
        const medicine = medicines.find(item => item.id === value);
        if (medicine) setQuery(`${medicine.name} — ${medicine.sku}`);
    }, [medicines, value]);

    useEffect(() => {
        inputRef.current?.setCustomValidity(value ? "" : "Vui lòng chọn thuốc trong danh sách gợi ý.");
    }, [value]);

    function choose(medicine: Medicine) {
        setQuery(`${medicine.name} — ${medicine.sku}`);
        onChange(medicine);
        setOpen(false);
        inputRef.current?.setCustomValidity("");
    }

    return (
        <label className="drug-field drug-field-medicine">
            <span>Tên thuốc</span>
            <div className="medicine-picker">
                <input
                    ref={inputRef}
                    type="search"
                    required
                    autoComplete="off"
                    value={query}
                    placeholder="Tìm theo tên hoặc mã thuốc..."
                    aria-label={`Tìm thuốc cho dòng ${index + 1}`}
                    aria-expanded={open}
                    aria-autocomplete="list"
                    aria-controls={`medicine-results-${index}`}
                    onFocus={() => setOpen(true)}
                    onBlur={() => window.setTimeout(() => setOpen(false), 120)}
                    onKeyDown={event => {
                        if (event.key === "Escape") setOpen(false);
                        if (event.key === "Enter" && open && results.length) {
                            event.preventDefault();
                            choose(results[0]);
                        }
                    }}
                    onChange={event => {
                        setQuery(event.target.value);
                        setOpen(true);
                        if (value) onChange(undefined);
                    }}
                />
                {open && (
                    <div id={`medicine-results-${index}`} className="medicine-picker-results" role="listbox">
                        {results.length ? results.map(medicine => (
                            <button key={medicine.id} type="button" role="option" aria-selected={medicine.id === value} onMouseDown={event => event.preventDefault()} onClick={() => choose(medicine)}>
                                <span><strong>{medicine.name}</strong><small>{medicine.sku} · {medicine.unit}</small></span>
                                <em>Còn {medicine.stockQuantity}</em>
                            </button>
                        )) : <p>Không tìm thấy thuốc đang bán phù hợp.</p>}
                    </div>
                )}
            </div>
        </label>
    );
}

function Consultation({ token, appointment, patient, existingRecord, close, complete, requireFollowUp, recordSaved }: { token: string; appointment: Appointment; patient?: Patient; existingRecord?: MedicalRecord; close: () => void; complete: () => Promise<void>; requireFollowUp: (reason: string, notBefore: string) => Promise<void>; recordSaved: (record: MedicalRecord) => void }) {
    const emptyDrug = (): PrescriptionDraft => ({ medicineId: "", drugName: "", dosage: "", frequency: "", duration: "", quantityRequested: 1, instructions: "" });
    const [medicines, setMedicines] = useState<Medicine[]>([]);
    const [services, setServices] = useState<ClinicService[]>([]);
    const [selectedServiceIds, setSelectedServiceIds] = useState<string[]>([]);
    const [servicesConfirmed, setServicesConfirmed] = useState(Boolean(appointment.servicesConfirmedAt));
    const [servicesLoading, setServicesLoading] = useState(true);
    const [consultationStep, setConsultationStep] = useState<"prescription" | "services">(appointment.servicesConfirmedAt ? "services" : "prescription");
    const [diagnosis, setDiagnosis] = useState(existingRecord?.finalDiagnosis || ""); const [notes, setNotes] = useState(existingRecord?.clinicalNotes || ""); const [plan, setPlan] = useState(existingRecord?.treatmentPlan || ""); const [severity, setSeverity] = useState(existingRecord?.severity || "MILD"); const [recordId, setRecordId] = useState(existingRecord?.id || ""); const [items, setItems] = useState<PrescriptionDraft[]>([emptyDrug()]); const [rxInstructions, setRxInstructions] = useState(""); const [prescriptionSigned, setPrescriptionSigned] = useState(false); const [needFollowUp, setNeedFollowUp] = useState(Boolean(existingRecord?.followUpAt)); const [followDate, setFollowDate] = useState(existingRecord?.followUpAt ? new Date(existingRecord.followUpAt).toISOString().slice(0, 10) : ""); const [followReason, setFollowReason] = useState(""); const [message, setMessage] = useState(existingRecord ? "Hồ sơ y khoa đã được ký. Có thể tiếp tục kê đơn thuốc." : ""); const [busy, setBusy] = useState(false);
    const dialogRef = useRef<HTMLElement>(null);
    const closeButtonRef = useRef<HTMLButtonElement>(null);
    const closeRef = useRef(close);

    useEffect(() => {
        Promise.all([
            request<Medicine[]>("/medicines", token),
            request<ClinicService[]>(`/services?doctorId=${encodeURIComponent(appointment.doctorId || "")}`, token),
            request<AppointmentPerformedServices>(`/appointments/${appointment.id}/performed-services`, token),
        ]).then(([medicineCatalog, serviceCatalog, confirmed]) => {
            setMedicines(medicineCatalog);
            setServices(serviceCatalog);
            setSelectedServiceIds(confirmed.items.map(item => item.serviceId));
            setServicesConfirmed(Boolean(confirmed.confirmedAt));
            if (confirmed.confirmedAt) setConsultationStep("services");
        }).catch(error => setMessage((error as Error).message)).finally(() => setServicesLoading(false));
    }, [appointment.id, token]);

    useEffect(() => {
        closeRef.current = close;
    }, [close]);

    useEffect(() => {
        const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const previousBodyOverflow = document.body.style.overflow;

        // The consultation belongs to the selected appointment, so present it immediately
        // as a modal instead of placing it after the entire dashboard's tall content.
        document.body.style.overflow = "hidden";
        closeButtonRef.current?.focus();

        function handleDialogKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") {
                event.preventDefault();
                closeRef.current();
                return;
            }

            if (event.key !== "Tab" || !dialogRef.current) return;
            const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
                'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
            )).filter(element => element.getClientRects().length > 0);

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

        document.addEventListener("keydown", handleDialogKeyDown);
        return () => {
            document.removeEventListener("keydown", handleDialogKeyDown);
            document.body.style.overflow = previousBodyOverflow;
            trigger?.focus();
        };
    }, []);

    function updateItem(index: number, field: keyof PrescriptionDraft, value: string | number) { setItems(current => current.map((item, i) => i === index ? { ...item, [field]: value } : item)) }
    async function saveRecord(e: FormEvent) { e.preventDefault(); if (needFollowUp && (!followDate || !followReason.trim())) { setMessage("Hãy nhập ngày khuyến nghị và lý do tái khám."); return } setMessage(""); try { const r = await request<MedicalRecord>("/medical-records", token, { method: "POST", body: JSON.stringify({ appointmentId: appointment.id, patientId: appointment.patientId, finalDiagnosis: diagnosis, clinicalNotes: notes || null, treatmentPlan: plan || null, severity, followUpAt: needFollowUp ? new Date(`${followDate}T00:00:00`).toISOString() : null }) }); setRecordId(r.id); recordSaved(r); setMessage("Đã ký hồ sơ y khoa.") } catch (x) { setMessage((x as Error).message) } }
    async function savePrescription(e: FormEvent) { e.preventDefault(); setMessage(""); try { await request("/prescriptions", token, { method: "POST", body: JSON.stringify({ recordId, patientId: appointment.patientId, instructions: rxInstructions || null, items }) }); setPrescriptionSigned(true); setConsultationStep("services"); setMessage("Đã ký đơn thuốc với " + items.length + " thuốc. Tiếp theo, hãy xác nhận dịch vụ đã thực hiện.") } catch (x) { setMessage((x as Error).message) } }
    async function confirmServices() { setBusy(true); setMessage(""); try { const confirmed = await request<AppointmentPerformedServices>(`/appointments/${appointment.id}/performed-services`, token, { method: "PUT", body: JSON.stringify({ serviceIds: selectedServiceIds }) }); setSelectedServiceIds(confirmed.items.map(item => item.serviceId)); setServicesConfirmed(true); setMessage(confirmed.items.length ? `Đã xác nhận ${confirmed.items.length} dịch vụ cho ca khám.` : "Đã xác nhận ca khám không phát sinh dịch vụ thêm."); } catch (x) { setMessage((x as Error).message); } finally { setBusy(false); } }
    async function finish() { if (!servicesConfirmed) { setMessage("Vui lòng xác nhận dịch vụ đã thực hiện trước khi hoàn tất ca khám."); return; } setBusy(true); setMessage(""); try { if (needFollowUp) await requireFollowUp(followReason, new Date(`${followDate}T00:00:00`).toISOString()); else await complete(); window.dispatchEvent(new Event("appointments-changed")); close(); } catch (x) { setMessage((x as Error).message); } finally { setBusy(false); } }
    return (
        <div className="consultation-backdrop">
            <section
                ref={dialogRef}
                className="panel consultation consultation-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby={`consultation-title-${appointment.id}`}
                tabIndex={-1}
            >
                <div className="consult-head">
                    <div>
                        <h2 id={`consultation-title-${appointment.id}`}>Ca khám: {patient?.fullName || appointment.patientId}</h2>
                        <p>Chẩn đoán và đơn thuốc chỉ do bác sĩ chịu trách nhiệm.</p>
                    </div>
                    <button ref={closeButtonRef} type="button" onClick={close} aria-label="Đóng chi tiết ca khám">Đóng</button>
                </div>
                <DoctorSharedAi token={token} appointmentId={appointment.id} />
                {!recordId ? (
                    <form onSubmit={saveRecord}>
                        <label>Chẩn đoán cuối<textarea required value={diagnosis} onChange={e => setDiagnosis(e.target.value)} /></label>
                        <label>Ghi chú lâm sàng<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label>
                        <label>Kế hoạch điều trị<textarea value={plan} onChange={e => setPlan(e.target.value)} /></label>
                        <label>Mức độ<select value={severity} onChange={e => setSeverity(e.target.value)}><option value="MILD">Nhẹ</option><option value="MODERATE">Trung bình</option><option value="SEVERE">Nặng</option><option value="URGENT">Khẩn cấp</option></select></label>
                        <label className="follow-check"><input type="checkbox" checked={needFollowUp} onChange={e => setNeedFollowUp(e.target.checked)} /> Yêu cầu bệnh nhân tái khám</label>
                        {needFollowUp && (
                            <div className="follow-box">
                                <label>Ngày bác sĩ khuyến nghị<input type="date" required value={followDate} onChange={e => setFollowDate(e.target.value)} /></label>
                                <label>Lý do tái khám<input required value={followReason} onChange={e => setFollowReason(e.target.value)} /></label>
                                <p>Bác sĩ chỉ đưa ra ngày khuyến nghị. Bệnh nhân sẽ tự chọn giờ còn trống sau khi xem hồ sơ.</p>
                            </div>
                        )}
                        <button className="primary" disabled={needFollowUp && (!followDate || !followReason.trim())}>Ký hồ sơ</button>
                    </form>
                ) : (
                    <>
                    <ol className="doctor-consult-steps" aria-label="Tiến trình hoàn tất ca khám">
                        <li className="is-complete"><span>1</span><div><b>Hồ sơ</b><small>Đã ký</small></div></li>
                        <li className={consultationStep === "prescription" ? "is-current" : "is-complete"}><span>2</span><div><b>Đơn thuốc</b><small>{prescriptionSigned ? "Đã ký" : consultationStep === "services" ? "Không kê đơn" : "Đang thực hiện"}</small></div></li>
                        <li className={consultationStep === "services" ? "is-current" : ""}><span>3</span><div><b>Dịch vụ & hoàn tất</b><small>{servicesConfirmed ? "Đã xác nhận" : consultationStep === "services" ? "Đang thực hiện" : "Bước tiếp theo"}</small></div></li>
                    </ol>
                    <div className={`prescription-stage ${consultationStep === "services" ? "is-service-step" : ""}`}>
                        {consultationStep === "prescription" && <div className="prescription-stage-head">
                            <div>
                                <span>BƯỚC 2 · KÊ ĐƠN ĐIỆN TỬ</span>
                                <h3>Đơn thuốc — chỉ bác sĩ phụ trách</h3>
                            </div>
                            <p>Chọn thuốc trong danh mục và ghi rõ cách dùng cho từng thuốc.</p>
                        </div>}
                        {!prescriptionSigned && consultationStep === "prescription" && (
                            <form onSubmit={savePrescription}>
                                {items.map((item, index) => (
                                    <div className="drug-row" key={index}>
                                        <span className="drug-row-number" aria-hidden="true">{index + 1}</span>
                                        <MedicinePicker medicines={medicines} value={item.medicineId} index={index} onChange={medicine => setItems(current => current.map((value, itemIndex) => itemIndex === index ? { ...value, medicineId: medicine?.id || "", drugName: medicine?.name || "" } : value))} />
                                        <label className="drug-field drug-field-quantity">Số lượng<input aria-label={`Số lượng thuốc ${index + 1}`} required type="number" min="1" max="10000" value={item.quantityRequested} onChange={e => updateItem(index, "quantityRequested", Number(e.target.value))} /></label>
                                        <label className="drug-field drug-field-dosage">Liều dùng<input required placeholder="VD: 1 viên/lần" value={item.dosage} onChange={e => updateItem(index, "dosage", e.target.value)} /></label>
                                        <label className="drug-field drug-field-frequency">Tần suất<input placeholder="VD: 2 lần/ngày" value={item.frequency} onChange={e => updateItem(index, "frequency", e.target.value)} /></label>
                                        <label className="drug-field drug-field-duration">Thời gian dùng<input placeholder="VD: 7 ngày" value={item.duration} onChange={e => updateItem(index, "duration", e.target.value)} /></label>
                                        <label className="drug-field drug-field-instructions">Hướng dẫn riêng<input placeholder="VD: Uống sau ăn" value={item.instructions} onChange={e => updateItem(index, "instructions", e.target.value)} /></label>
                                        {items.length > 1 && <button className="drug-remove" type="button" onClick={() => setItems(items.filter((_, i) => i !== index))}>Xóa thuốc</button>}
                                    </div>
                                ))}
                                <label className="prescription-general-instructions"><span>Hướng dẫn chung</span><small>Dặn dò áp dụng cho toàn bộ đơn thuốc (không bắt buộc).</small><textarea rows={3} placeholder="Nhập lưu ý chung cho bệnh nhân..." value={rxInstructions} onChange={e => setRxInstructions(e.target.value)} /></label>
                                <div className="form-actions prescription-actions">
                                    <button type="button" onClick={() => setItems([...items, emptyDrug()])}>+ Thêm thuốc</button>
                                    <button className="prescription-skip" type="button" onClick={() => { setConsultationStep("services"); setMessage("Ca khám không kê đơn thuốc. Hãy xác nhận dịch vụ đã thực hiện."); }}>Không kê đơn · Sang dịch vụ</button>
                                    <button className="primary">Ký đơn thuốc</button>
                                </div>
                            </form>
                        )}
                        {consultationStep === "services" && <>
                        <section className={`doctor-service-confirmation ${servicesConfirmed ? "is-confirmed" : ""}`}>
                            <header><div><span>BƯỚC 3 · DỊCH VỤ ĐÃ THỰC HIỆN</span><h3>Xác nhận dịch vụ của ca khám</h3></div><b>{selectedServiceIds.length} dịch vụ · {new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(services.filter(item => selectedServiceIds.includes(item.id)).reduce((sum, item) => sum + Number(item.priceFrom || 0), 0))}</b></header>
                            <p>Chỉ chọn dịch vụ thực tế đã làm cho bệnh nhân. Danh sách và đơn giá sẽ được khóa để lễ tân lập hóa đơn chính xác.</p>
                            {servicesLoading ? <div className="doctor-service-empty">Đang tải danh mục dịch vụ...</div> : services.length === 0 ? <div className="doctor-service-empty">Bác sĩ chưa được admin gán dịch vụ nào. Có thể xác nhận ca khám không phát sinh dịch vụ.</div> : <div className="doctor-service-options">{services.map(service => <label className={selectedServiceIds.includes(service.id) ? "selected" : ""} key={service.id}><input type="checkbox" checked={selectedServiceIds.includes(service.id)} onChange={event => { setServicesConfirmed(false); setSelectedServiceIds(current => event.target.checked ? [...current, service.id] : current.filter(id => id !== service.id)); }} /><span><b>{service.name}</b><small>{service.code} · {service.durationMinutes} phút</small></span><em>{new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(service.priceFrom)}</em></label>)}</div>}
                            <footer><span>{servicesConfirmed ? "✓ Danh sách dịch vụ đã được khóa cho ca khám" : "Cần xác nhận, kể cả khi không chọn dịch vụ nào"}</span><button type="button" disabled={busy || servicesLoading} onClick={confirmServices}>{busy ? "Đang xác nhận..." : servicesConfirmed ? "Xác nhận lại dịch vụ" : "Xác nhận dịch vụ"}</button></footer>
                        </section>
                        <div className="finish-visit">
                            <div><strong>Sẵn sàng hoàn tất ca khám</strong><p>{!servicesConfirmed ? "Xác nhận danh sách dịch vụ ở trên để tiếp tục." : needFollowUp ? `Tái khám từ ngày ${new Date(`${followDate}T00:00:00`).toLocaleDateString("vi-VN")}; bệnh nhân tự chọn giờ.` : "Không yêu cầu tái khám."}</p></div>
                            <button className="primary" disabled={busy || servicesLoading || !servicesConfirmed} onClick={finish}>{busy ? "Đang hoàn thành..." : !servicesConfirmed ? "Xác nhận dịch vụ trước" : prescriptionSigned ? "Hoàn thành ca khám" : "Hoàn thành không kê đơn"}</button>
                        </div>
                        {!prescriptionSigned && !servicesConfirmed && <button className="doctor-back-to-prescription" type="button" onClick={() => { setConsultationStep("prescription"); setMessage(""); }}>← Quay lại kê đơn thuốc</button>}
                        </>}
                    </div>
                    </>
                )}
                {message && <p className="form-message" role="status" aria-live="polite">{message}</p>}
            </section>
        </div>
    );
}
