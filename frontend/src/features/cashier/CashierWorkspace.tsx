import { FormEvent, useEffect, useMemo, useState } from "react";
import { Banknote, CheckCircle2, ChevronDown, ChevronUp, ExternalLink, PackageCheck, Printer, ReceiptText, RefreshCw, Search, X } from "lucide-react";
import { ApiError, request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import { subscribeRealtime } from "../../core/realtime";
import type { Appointment, AppointmentPerformedServices, Invoice, Medicine, Patient, Prescription } from "../../core/types";
import { PrescriptionPdfModal } from "../../components/PrescriptionPdfModal";

type OnlinePayment = { checkoutUrl: string; expiresAt: string; status: string };
type DepositPayment = { amount: number; status: string };
const invoicePageSize = 6;

function normalizePatientSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLocaleLowerCase("vi-VN")
    .trim();
}

function invoiceStatusLabel(status: Invoice["status"]) {
  return status === "AWAITING_PAYMENT" ? "Chờ thanh toán"
    : status === "PAID" ? "Đã thanh toán"
      : status === "DISPENSED" ? "Đã giao thuốc"
        : "Đã hủy";
}

export default function CashierWorkspace({ token }: { token: string }) {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [performedServices, setPerformedServices] = useState<AppointmentPerformedServices | null>(null);
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [prescriptions, setPrescriptions] = useState<Record<string, Prescription[]>>({});
  const [deposits, setDeposits] = useState<Record<string, DepositPayment | null>>({});
  const [selectedId, setSelectedId] = useState("");
  const [appointmentQuery, setAppointmentQuery] = useState("");
  const [appointmentPickerOpen, setAppointmentPickerOpen] = useState(false);
  const [activeCandidateIndex, setActiveCandidateIndex] = useState(0);
  const [buyMedicines, setBuyMedicines] = useState(true);
  const [prescriptionId, setPrescriptionId] = useState("");
  const [cash, setCash] = useState<Record<string, string>>({});
  const [station, setStation] = useState("Quầy 1");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingPrescription, setLoadingPrescription] = useState(false);
  const [pdfPrescription, setPdfPrescription] = useState<Prescription | null>(null);
  const [invoiceQuery, setInvoiceQuery] = useState("");
  const [visibleInvoiceCount, setVisibleInvoiceCount] = useState(invoicePageSize);
  const [expandedInvoiceIds, setExpandedInvoiceIds] = useState<Set<string>>(() => new Set());

  async function load() {
    const from = new Date(); from.setDate(from.getDate() - 30); from.setHours(0, 0, 0, 0);
    const to = new Date(); to.setDate(to.getDate() + 1);
    const [queue, bills, medicineCatalog] = await Promise.all([
      request<Appointment[]>(`/appointments/queue?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token),
      request<Invoice[]>("/billing/invoices", token),
      request<Medicine[]>("/medicines", token),
    ]);
    const completed = queue.filter(item => ["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(item.status));
    const [synchronizedBills, depositEntries] = await Promise.all([
      Promise.all(bills.map(async invoice => {
        if (invoice.status !== "AWAITING_PAYMENT" || invoice.depositApplied > 0) return invoice;
        try { return await request<Invoice>(`/billing/invoices/${invoice.id}/refresh-deposit`, token, { method: "POST" }); }
        catch { return invoice; }
      })),
      Promise.all(completed.map(async appointment => {
        try {
          const payment = await request<DepositPayment>(`/payments/booking/${appointment.id}`, token);
          return [appointment.id, payment] as const;
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) return [appointment.id, null] as const;
          throw error;
        }
      })),
    ]);
    setAppointments(completed); setInvoices(synchronizedBills); setMedicines(medicineCatalog);
    setDeposits(Object.fromEntries(depositEntries));
    const ids = [...new Set([...completed.map(x => x.patientId), ...synchronizedBills.map(x => x.patientId)])];
    const entries = await Promise.all(ids.map(async id => [id, await request<Patient>(`/patients/${id}`, token)] as const));
    setPatients(Object.fromEntries(entries));
  }

  useEffect(() => {
    const refresh = () => void load().catch(error => setMessage((error as Error).message));
    refresh();
    const timer = window.setInterval(refresh, 15_000);
    const unsubscribe = subscribeRealtime(event => {
      if (event.type === "RECEPTION_NOTIFICATIONS_CHANGED") refresh();
    });
    const visible = () => { if (!document.hidden) refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { window.clearInterval(timer); unsubscribe(); document.removeEventListener("visibilitychange", visible); };
  }, [token]);
  const billedAppointments = useMemo(() => new Set(invoices.map(item => item.appointmentId)), [invoices]);
  const candidates = appointments
    .filter(item => !billedAppointments.has(item.id) && deposits[item.id]?.status === "SUCCESS" && (deposits[item.id]?.amount || 0) > 0)
    .sort((a, b) => new Date(b.startAt).getTime() - new Date(a.startAt).getTime());
  const normalizedAppointmentQuery = normalizePatientSearch(appointmentQuery);
  const filteredCandidates = candidates.filter(item => {
    if (!normalizedAppointmentQuery) return true;
    const patient = patients[item.patientId];
    return normalizePatientSearch([
      patient?.fullName,
      patient?.phone,
      patient?.id,
      item.patientId,
      item.id,
      new Date(item.startAt).toLocaleString("vi-VN"),
    ].filter(Boolean).join(" ")).includes(normalizedAppointmentQuery);
  });
  const selected = appointments.find(item => item.id === selectedId);
  const selectedPrescriptions = selected ? prescriptions[selected.patientId] || [] : [];
  const matchingPrescriptions = selected ? selectedPrescriptions.filter(item => item.appointmentId === selected.id) : [];
  const selectedPrescription = matchingPrescriptions.find(item => item.id === prescriptionId);
  const selectedDeposit = selected ? deposits[selected.id] : undefined;
  const selectedHasDeposit = selectedDeposit?.status === "SUCCESS";
  const medicineById = useMemo(() => new Map(medicines.map(item => [item.id, item])), [medicines]);
  const selectedServiceTotal = performedServices?.items.reduce((total, item) => total + Number(item.unitPrice || 0), 0) || 0;
  const unavailableMedicineItems = buyMedicines
    ? selectedPrescription?.items.filter(item => !item.medicineId || !medicineById.has(item.medicineId)) || []
    : [];
  const selectedMedicineTotal = buyMedicines
    ? selectedPrescription?.items.reduce((total, item) => {
        const medicine = item.medicineId ? medicineById.get(item.medicineId) : undefined;
        return total + Number(medicine?.salePrice || 0) * Number(item.quantityRequested || 0);
      }, 0) || 0
    : 0;
  const previewSubtotal = Number(selected?.consultationFeeSnapshot || 0) + selectedServiceTotal + selectedMedicineTotal;
  const previewDeposit = selectedHasDeposit ? Math.min(Number(selectedDeposit.amount || 0), previewSubtotal) : 0;
  const previewRemaining = Math.max(0, previewSubtotal - previewDeposit);
  const appointmentById = useMemo(() => new Map(appointments.map(item => [item.id, item])), [appointments]);
  const normalizedInvoiceQuery = invoiceQuery.trim().toLocaleLowerCase("vi-VN");
  const filteredInvoices = invoices.filter(invoice => {
    if (!normalizedInvoiceQuery) return true;
    const searchable = [
      invoice.id,
      invoice.appointmentId,
      patients[invoice.patientId]?.fullName,
      invoiceStatusLabel(invoice.status),
      new Date(invoice.createdAt).toLocaleString("vi-VN"),
      formatVnd(invoice.totalAmount),
      formatVnd(invoice.remainingAmount),
      ...invoice.serviceItems.map(item => item.serviceName),
      ...invoice.items.map(item => item.medicineName),
    ].filter(Boolean).join(" ").toLocaleLowerCase("vi-VN");
    return searchable.includes(normalizedInvoiceQuery);
  });
  const visibleInvoices = filteredInvoices.slice(0, visibleInvoiceCount);

  function toggleInvoiceDetails(invoiceId: string) {
    setExpandedInvoiceIds(current => {
      const next = new Set(current);
      if (next.has(invoiceId)) next.delete(invoiceId);
      else next.add(invoiceId);
      return next;
    });
  }

  function selectCandidate(appointment: Appointment) {
    const patient = patients[appointment.patientId];
    setAppointmentQuery([patient?.fullName || appointment.patientId, patient?.phone].filter(Boolean).join(" · "));
    setAppointmentPickerOpen(false);
    setActiveCandidateIndex(0);
    void chooseAppointment(appointment.id);
  }

  function clearCandidate() {
    setAppointmentQuery("");
    setAppointmentPickerOpen(true);
    setActiveCandidateIndex(0);
    if (selectedId) void chooseAppointment("");
  }

  async function chooseAppointment(id: string) {
    setSelectedId(id); setPrescriptionId(""); setPerformedServices(null); setMessage(""); setLoadingPrescription(Boolean(id));
    const appointment = appointments.find(item => item.id === id);
    if (!appointment) { setLoadingPrescription(false); return; }
    if (!(id in deposits)) {
      request<DepositPayment>(`/payments/booking/${id}`, token)
        .then(value => setDeposits(current => ({ ...current, [id]: value })))
        .catch(error => {
          if (error instanceof ApiError && error.status === 404) setDeposits(current => ({ ...current, [id]: null }));
          else setMessage((error as Error).message);
        });
    }
    try {
      // Always refresh here: a doctor may have signed the prescription after this
      // patient's prescriptions were first cached in the receptionist workspace.
      const [value, confirmedServices] = await Promise.all([
        request<Prescription[]>(`/prescriptions/patient/${appointment.patientId}`, token),
        request<AppointmentPerformedServices>(`/appointments/${id}/performed-services`, token),
      ]);
      setPrescriptions(current => ({ ...current, [appointment.patientId]: value }));
      setPerformedServices(confirmedServices);
      const matching = value.find(item => item.appointmentId === id);
      if (matching) setPrescriptionId(matching.id);
    } catch (error) {
      setMessage(`Không tải được đơn thuốc của lượt khám: ${(error as Error).message}`);
    } finally {
      setLoadingPrescription(false);
    }
  }

  async function createInvoice(event: FormEvent) {
    event.preventDefault();
    if (!selected) { setMessage("Vui lòng chọn lượt khám."); return; }
    if (!selectedHasDeposit) { setMessage("Lượt khám chưa có tiền cọc thành công."); return; }
    if (!performedServices?.confirmedAt) { setMessage("Bác sĩ chưa xác nhận dịch vụ đã thực hiện cho lượt khám này."); return; }
    if ((buyMedicines || matchingPrescriptions.length > 0) && !prescriptionId) {
      setMessage(matchingPrescriptions.length === 0
        ? "Lượt khám chưa có đơn thuốc đã ký. Vui lòng chọn “Bệnh nhân tự mua thuốc ngoài” nếu bác sĩ không kê đơn."
        : "Vui lòng chọn đơn thuốc của lượt khám trước khi tạo hóa đơn.");
      return;
    }
    if (unavailableMedicineItems.length > 0) {
      setMessage("Đơn có thuốc không còn trong danh mục bán. Vui lòng kiểm tra lại với bác sĩ hoặc quản trị viên.");
      return;
    }
    setBusy(true); setMessage("");
    try {
      const invoice = await request<Invoice>("/billing/invoices", token, { method: "POST", body: JSON.stringify({ appointmentId: selected.id, prescriptionId: prescriptionId || null, buyMedicines }) });
      setInvoices(current => [invoice, ...current.filter(item => item.id !== invoice.id)]); setSelectedId(""); setAppointmentQuery(""); setAppointmentPickerOpen(false); setMessage("Đã lập hóa đơn. Số tiền và tiền cọc được tính từ dữ liệu hệ thống."); if (invoice.medicineFulfillment === "OUTSIDE_PHARMACY") { const linked = selectedPrescriptions.find(item => item.id === invoice.prescriptionId); if (linked) setPdfPrescription(linked); }
    } catch (error) { setMessage((error as Error).message); } finally { setBusy(false); }
  }

  async function openPrescription(invoice: Invoice) {
    if (!invoice.prescriptionId) { setMessage("Hóa đơn này không có đơn thuốc điện tử."); return; }
    let available = prescriptions[invoice.patientId];
    if (!available) {
      try {
        available = await request<Prescription[]>(`/prescriptions/patient/${invoice.patientId}`, token);
        setPrescriptions(current => ({ ...current, [invoice.patientId]: available! }));
      } catch (error) { setMessage((error as Error).message); return; }
    }
    const prescription = available.find(item => item.id === invoice.prescriptionId);
    if (!prescription) { setMessage("Không tìm thấy đơn thuốc đã liên kết với hóa đơn."); return; }
    setPdfPrescription(prescription);
  }

  async function collectCash(invoice: Invoice) {
    setBusy(true); setMessage("");
    try {
      const result = await request<{ invoice: Invoice; cashPayment: { amountDue: number; amountReceived: number; changeAmount: number } }>(`/billing/invoices/${invoice.id}/cash`, token, { method: "POST", body: JSON.stringify({ amountReceived: Number(cash[invoice.id] || 0), cashierStation: station }) });
      setInvoices(current => current.map(item => item.id === invoice.id ? result.invoice : item)); setMessage(`Đã nhận ${formatVnd(result.cashPayment.amountReceived)} · Đã thối khách ${formatVnd(result.cashPayment.changeAmount)} · Thực thu ${formatVnd(result.cashPayment.amountDue)}.`); if (result.invoice.medicineFulfillment === "OUTSIDE_PHARMACY") void openPrescription(result.invoice);
    } catch (error) { setMessage((error as Error).message); } finally { setBusy(false); }
  }

  async function payOnline(invoice: Invoice) {
    setBusy(true); setMessage("");
    try { const payment = await request<OnlinePayment>(`/billing/invoices/${invoice.id}/online-payment`, token, { method: "POST" }); window.open(payment.checkoutUrl, "_blank", "noopener,noreferrer"); setMessage("Đã mở cổng thanh toán. Hóa đơn chỉ chuyển sang Đã thanh toán sau khi hệ thống nhận xác nhận thành công."); }
    catch (error) { setMessage((error as Error).message); } finally { setBusy(false); }
  }

  return <div className="cashier-workspace">
    <header className="cashier-hero"><div><span>Vận hành sau khám</span><h1>Hóa đơn</h1><p>Giá được lấy từ hệ thống; bác sĩ không nhập giá và không thu tiền.</p></div><button type="button" onClick={() => load().catch(error => setMessage((error as Error).message))}><RefreshCw /> Làm mới</button></header>
    {message && <p className="cashier-message" role="status">{message}</p>}
    <section className="cashier-grid">
      <article className="panel cashier-create"><h2><ReceiptText /> Lập hóa đơn mới</h2>{candidates.length === 0 ? <p>Không có lượt khám đã hoàn tất, đặt cọc thành công và đang chờ lập hóa đơn.</p> : <form onSubmit={createInvoice} noValidate>
        <div className="cashier-appointment-picker"><span id="cashier-patient-picker-label">Lượt khám cần thanh toán</span><div className={"cashier-patient-combobox " + (appointmentPickerOpen ? "is-open" : "")}><Search aria-hidden="true" /><input id="cashier-patient-picker" type="search" role="combobox" aria-labelledby="cashier-patient-picker-label" aria-controls="cashier-patient-results" aria-expanded={appointmentPickerOpen} aria-autocomplete="list" aria-activedescendant={appointmentPickerOpen && filteredCandidates[activeCandidateIndex] ? "cashier-patient-option-" + filteredCandidates[activeCandidateIndex].id : undefined} autoComplete="off" value={appointmentQuery} placeholder="Tìm tên, SĐT hoặc mã bệnh nhân..." onFocus={() => setAppointmentPickerOpen(true)} onBlur={() => window.setTimeout(() => setAppointmentPickerOpen(false), 120)} onChange={event => { setAppointmentQuery(event.target.value); setAppointmentPickerOpen(true); setActiveCandidateIndex(0); if (selectedId) void chooseAppointment(""); }} onKeyDown={event => { if (event.key === "ArrowDown") { event.preventDefault(); setAppointmentPickerOpen(true); setActiveCandidateIndex(index => Math.min(index + 1, Math.max(filteredCandidates.length - 1, 0))); } else if (event.key === "ArrowUp") { event.preventDefault(); setActiveCandidateIndex(index => Math.max(index - 1, 0)); } else if (event.key === "Enter" && appointmentPickerOpen && filteredCandidates.length > 0) { event.preventDefault(); selectCandidate(filteredCandidates[Math.min(activeCandidateIndex, filteredCandidates.length - 1)]); } else if (event.key === "Escape") { setAppointmentPickerOpen(false); } }} />{appointmentQuery && <button type="button" onMouseDown={event => event.preventDefault()} onClick={clearCandidate} aria-label="Xóa bệnh nhân đã tìm"><X aria-hidden="true" /></button>}</div>{appointmentPickerOpen && <div className="cashier-patient-results" id="cashier-patient-results" role="listbox" aria-label="Bệnh nhân có lượt khám cần thanh toán">{filteredCandidates.length === 0 ? <p>Không tìm thấy bệnh nhân phù hợp.</p> : filteredCandidates.map((item, index) => { const patient = patients[item.patientId]; return <button id={"cashier-patient-option-" + item.id} type="button" role="option" aria-selected={selectedId === item.id} className={index === activeCandidateIndex ? "is-active" : ""} key={item.id} onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActiveCandidateIndex(index)} onClick={() => selectCandidate(item)}><span><b>{patient?.fullName || item.patientId}</b><small>{patient?.phone || "Chưa có SĐT"} · Mã {item.patientId.slice(0, 8).toUpperCase()}</small></span><time dateTime={item.startAt}>{new Date(item.startAt).toLocaleString("vi-VN")}</time></button>; })}</div>}{!selected && <small>Gõ tên, số điện thoại hoặc mã bệnh nhân để tìm nhanh lượt khám.</small>}</div>
        {selected && <><div className="cashier-fee"><span>Phí khám đã chốt</span><b>{formatVnd(selected.consultationFeeSnapshot || 0)}</b></div><div className={`cashier-deposit-check ${selectedHasDeposit ? "has-deposit" : "no-deposit"}`}><span>Tiền cọc của đúng lượt khám này</span><b>{selectedDeposit === undefined ? "Đang kiểm tra..." : selectedHasDeposit ? formatVnd(selectedDeposit.amount) : "Chưa có cọc thành công"}</b>{selectedDeposit !== undefined && !selectedHasDeposit && <small>Hóa đơn của lượt khám này sẽ không được khấu trừ tiền cọc.</small>}</div></>}
        {selected && <section className={`cashier-services-confirmed ${performedServices?.confirmedAt ? "is-confirmed" : ""}`}><header><div><span>Dịch vụ bác sĩ đã xác nhận</span><small>Lễ tân không cần chọn lại; hệ thống tự đưa vào hóa đơn.</small></div><b>{formatVnd(selectedServiceTotal)}</b></header>{loadingPrescription ? <p>Đang tải dịch vụ của ca khám...</p> : !performedServices?.confirmedAt ? <p className="is-warning">Bác sĩ chưa xác nhận dịch vụ cho ca khám này.</p> : performedServices.items.length === 0 ? <p>Ca khám được xác nhận không phát sinh dịch vụ thêm.</p> : <ul>{performedServices.items.map(item => <li key={item.serviceId}><span>{item.serviceName}<small>{item.serviceCode}</small></span><b>{formatVnd(item.unitPrice)}</b></li>)}</ul>}</section>}
        <fieldset className="cashier-fulfillment" disabled={!selected}><legend>Cách nhận thuốc theo đơn</legend><label className={buyMedicines ? "selected" : ""}><input type="radio" name="medicineFulfillment" checked={buyMedicines} onChange={() => setBuyMedicines(true)} /><span><b>Mua tại phòng khám</b><small>Tính tiền thuốc và chuyển đơn sang quầy Dược.</small></span></label><label className={!buyMedicines ? "selected outside" : ""}><input type="radio" name="medicineFulfillment" checked={!buyMedicines} onChange={() => setBuyMedicines(false)} /><span><b>Bệnh nhân tự mua thuốc ngoài</b><small>Chỉ thu phí khám/dịch vụ, không chuyển quầy Dược và không trừ kho.</small></span></label></fieldset>
        {selected && <label>Đơn thuốc<select value={prescriptionId} disabled={loadingPrescription} onChange={event => setPrescriptionId(event.target.value)}><option value="">{loadingPrescription ? "Đang tải đơn thuốc..." : buyMedicines ? "Chọn đơn đã ký" : "Không có đơn thuốc"}</option>{matchingPrescriptions.map(item => <option key={item.id} value={item.id}>{item.items.length} thuốc — {new Date(item.signedAt).toLocaleString("vi-VN")}</option>)}</select><small>{buyMedicines ? "Đơn sẽ được tính tiền thuốc và gửi sang quầy Dược sau khi thanh toán." : "Đơn vẫn được liên kết để in/gửi cho bệnh nhân, nhưng tiền thuốc bằng 0 đồng."}</small></label>}
        {selected && <section className="cashier-preview" aria-label="Tạm tính hóa đơn">
          <header><b>Tạm tính hóa đơn</b><small>Giá được lấy từ hệ thống</small></header>
          {buyMedicines && selectedPrescription?.items.length ? <ul>{selectedPrescription.items.map((item, index) => {
            const medicine = item.medicineId ? medicineById.get(item.medicineId) : undefined;
            const quantity = Number(item.quantityRequested || 0);
            return <li key={item.medicineId || `${item.drugName}-${index}`}><span>{item.drugName} × {quantity}</span><b>{medicine ? formatVnd(Number(medicine.salePrice) * quantity) : "Không có giá"}</b></li>;
          })}</ul> : null}
          <dl>
            <div><dt>Phí khám</dt><dd>{formatVnd(Number(selected.consultationFeeSnapshot || 0))}</dd></div>
            <div><dt>Dịch vụ</dt><dd>{formatVnd(selectedServiceTotal)}</dd></div>
            <div><dt>Tiền thuốc</dt><dd>{formatVnd(selectedMedicineTotal)}</dd></div>
            <div className="preview-deposit"><dt>Đã cọc</dt><dd>-{formatVnd(previewDeposit)}</dd></div>
            <div className="preview-total"><dt>Còn thanh toán</dt><dd>{formatVnd(previewRemaining)}</dd></div>
          </dl>
          {unavailableMedicineItems.length > 0 && <p>Đơn có thuốc không còn trong danh mục bán tại phòng khám.</p>}
        </section>}
        <button className="primary" disabled={busy || loadingPrescription || !selected || !selectedHasDeposit || !performedServices?.confirmedAt || unavailableMedicineItems.length > 0}>{busy ? "Đang lập..." : !selected ? "Chọn lượt khám để tiếp tục" : loadingPrescription ? "Đang tải dữ liệu ca khám..." : selectedDeposit === undefined ? "Đang kiểm tra tiền cọc..." : !selectedHasDeposit ? "Chưa thể lập hóa đơn" : !performedServices?.confirmedAt ? "Chờ bác sĩ xác nhận dịch vụ" : unavailableMedicineItems.length > 0 ? "Kiểm tra lại đơn thuốc" : "Tạo hóa đơn"}</button>
      </form>}</article>
      <article className="panel cashier-station"><h2><Banknote /> Thông tin quầy</h2><label>Ca / quầy tiếp nhận<input value={station} maxLength={120} onChange={event => setStation(event.target.value)} /></label><p>Giao dịch đã thu không được sửa hoặc xóa. Sai sót cần admin lập phiếu điều chỉnh có lý do.</p></article>
    </section>
    <section className="cashier-invoices">
      <header className="cashier-invoices-heading"><div><span>GIAO DỊCH GẦN NHẤT</span><h2>Hóa đơn gần đây</h2><p>Theo dõi thanh toán và trạng thái cấp thuốc tại một nơi.</p></div><b>{invoices.length} hóa đơn</b></header>
      {invoices.length === 0 ? <div className="cashier-invoices-empty"><span><ReceiptText /></span><b>Chưa có hóa đơn</b><p>Hóa đơn mới sẽ xuất hiện tại đây sau khi lễ tân lập từ lượt khám hợp lệ.</p></div> : <>
      <div className="cashier-invoices-toolbar"><label><Search aria-hidden="true" /><input type="search" value={invoiceQuery} onChange={event => { setInvoiceQuery(event.target.value); setVisibleInvoiceCount(invoicePageSize); }} placeholder="Tìm bệnh nhân, mã hóa đơn, thuốc…" aria-label="Tìm trong hóa đơn gần đây" />{invoiceQuery && <button type="button" onClick={() => { setInvoiceQuery(""); setVisibleInvoiceCount(invoicePageSize); }} aria-label="Xóa nội dung tìm kiếm"><X aria-hidden="true" /></button>}</label><span>{filteredInvoices.length === invoices.length ? `${invoices.length} kết quả` : `${filteredInvoices.length} / ${invoices.length} kết quả`}</span></div>
      {filteredInvoices.length === 0 ? <div className="cashier-invoices-empty is-search"><span><Search /></span><b>Không tìm thấy hóa đơn</b><p>Thử tìm bằng tên bệnh nhân, mã hóa đơn, trạng thái hoặc tên thuốc.</p></div> : <>
      {visibleInvoices.map(invoice => {
        const expanded = expandedInvoiceIds.has(invoice.id);
        const detailId = `cashier-invoice-details-${invoice.id}`;
        const cashReceived = Number(cash[invoice.id] || 0);
        const cashChange = Math.max(cashReceived - Number(invoice.remainingAmount), 0);
        return <article className={`cashier-invoice ${expanded ? "is-expanded" : ""}`} key={invoice.id}>
          <header>
            <div className="cashier-invoice-identity"><span className="cashier-invoice-mark"><ReceiptText /></span><div><b>{patients[invoice.patientId]?.fullName || invoice.patientId}</b><small>Mã hóa đơn #{invoice.id.slice(0, 8).toUpperCase()}</small><small>Lập lúc {new Date(invoice.createdAt).toLocaleString("vi-VN")}</small></div></div>
            <div className="cashier-invoice-head-actions"><span className={`invoice-status status-${invoice.status.toLowerCase()}`}>{invoiceStatusLabel(invoice.status)}</span><button type="button" className="cashier-invoice-toggle" aria-expanded={expanded} aria-controls={detailId} onClick={() => toggleInvoiceDetails(invoice.id)}>{expanded ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}{expanded ? "Thu gọn" : "Xem chi tiết"}</button></div>
          </header>
          <div className="cashier-invoice-summary"><span>Tổng hóa đơn <b>{formatVnd(invoice.totalAmount)}</b></span><span className={Number(invoice.remainingAmount) > 0 ? "has-balance" : ""}>Còn thanh toán <b>{formatVnd(invoice.remainingAmount)}</b></span></div>
          {expanded && <div className="cashier-invoice-detail-content" id={detailId}>
            <p className="cashier-invoice-appointment">Lượt khám: {appointmentById.has(invoice.appointmentId) ? new Date(appointmentById.get(invoice.appointmentId)!.startAt).toLocaleString("vi-VN") : `Mã ${invoice.appointmentId.slice(0, 8)}`}</p>
            <dl><div><dt>Phí khám</dt><dd>{formatVnd(invoice.consultationFee)}</dd></div><div><dt>Phí dịch vụ</dt><dd>{formatVnd(invoice.serviceFee)}</dd></div><div><dt>Tiền thuốc</dt><dd>{formatVnd(invoice.medicineTotal)}</dd></div><div className="deposit"><dt>Đã cọc</dt><dd>-{formatVnd(invoice.depositApplied)}</dd></div><div className="total"><dt>Còn thanh toán</dt><dd>{formatVnd(invoice.remainingAmount)}</dd></div></dl>
            {invoice.serviceItems?.length > 0 && <section className="cashier-invoice-lines"><header><b>Dịch vụ / thủ thuật</b><span>{invoice.serviceItems.length} mục</span></header><ul>{invoice.serviceItems.map(item => <li key={item.serviceId}>{item.serviceName}<span>{formatVnd(item.unitPrice)}</span></li>)}</ul></section>}
            {invoice.items.length > 0 && <section className="cashier-invoice-lines"><header><b>Thuốc theo đơn</b><span>{invoice.items.length} thuốc</span></header><ul>{invoice.items.map(item => <li key={item.medicineId}>{item.medicineName} × {item.prescribedQuantity} {item.unit} <span>{formatVnd(item.lineTotal)}</span></li>)}</ul></section>}
            {invoice.medicineFulfillment === "CLINIC_PHARMACY" && <p className="cashier-fulfillment-note">Nhận thuốc tại phòng khám</p>}
            {invoice.medicineFulfillment === "OUTSIDE_PHARMACY" && invoice.prescriptionId && <div className="cashier-document-actions"><button type="button" onClick={() => void openPrescription(invoice)} aria-label="Xem, in hoặc lưu đơn thuốc thành PDF"><Printer /><span>Xem / In / Lưu PDF</span></button></div>}
            {invoice.status === "AWAITING_PAYMENT" && <footer className="cashier-payment-actions"><label className="cashier-cash-field"><span>Khách đưa</span><input type="number" min={invoice.remainingAmount} step="1000" value={cash[invoice.id] || ""} onChange={event => setCash(current => ({ ...current, [invoice.id]: event.target.value }))} placeholder={String(invoice.remainingAmount)} aria-describedby={`cashier-change-${invoice.id}`} /><span className={`cashier-change-preview ${cashChange > 0 ? "has-change" : ""}`} id={`cashier-change-${invoice.id}`} aria-live="polite"><span><small>Cần thu</small><b>{formatVnd(invoice.remainingAmount)}</b></span><span><small>Tiền thối khách</small><b>{formatVnd(cashChange)}</b></span></span></label><button className="cashier-cash-action" type="button" disabled={busy || cashReceived < invoice.remainingAmount || !station.trim()} onClick={() => collectCash(invoice)}><span className="cashier-payment-action-icon"><Banknote /></span><span className="cashier-payment-action-copy"><b>Thu tiền mặt</b><small>{!station.trim() ? "Chọn quầy thu ngân" : cashReceived < invoice.remainingAmount ? "Nhập đủ số tiền" : `Thối lại ${formatVnd(cashChange)}`}</small></span></button><button className="primary cashier-online-action" type="button" disabled={busy} onClick={() => payOnline(invoice)}><span className="cashier-payment-action-icon"><ExternalLink /></span><span className="cashier-payment-action-copy"><b>Thanh toán online</b></span></button></footer>}
            {invoice.status === "PAID" && invoice.medicineFulfillment === "CLINIC_PHARMACY" && invoice.items.length > 0 && <p className="cashier-pharmacy-queued"><PackageCheck /><span><strong>Đã chuyển sang quầy Dược</strong><small>Dược sĩ sẽ chọn lô, giao thuốc và trừ kho.</small></span></p>}
            {invoice.status === "DISPENSED" && <p className="cashier-done"><CheckCircle2 /> Dược sĩ đã giao thuốc và trừ kho.</p>}
          </div>}
        </article>;
      })}
      <div className="cashier-invoices-controls"><span>Đang hiển thị {Math.min(visibleInvoiceCount, filteredInvoices.length)} / {filteredInvoices.length} hóa đơn</span><div>{visibleInvoiceCount > invoicePageSize && <button type="button" onClick={() => setVisibleInvoiceCount(invoicePageSize)}><ChevronUp aria-hidden="true" /> Thu gọn</button>}{visibleInvoiceCount < filteredInvoices.length && <button type="button" className="is-primary" onClick={() => setVisibleInvoiceCount(count => Math.min(count + invoicePageSize, filteredInvoices.length))}>Xem thêm {Math.min(invoicePageSize, filteredInvoices.length - visibleInvoiceCount)} <ChevronDown aria-hidden="true" /></button>}</div></div>
      </>}</>}
    </section>
    {pdfPrescription && <PrescriptionPdfModal appointment={pdfPrescription.appointmentId ? appointmentById.get(pdfPrescription.appointmentId) : undefined} prescription={pdfPrescription} patient={patients[pdfPrescription.patientId]} token={token} onClose={() => setPdfPrescription(null)} />}
  </div>;
}
