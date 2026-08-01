import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  PhoneCall,
  RefreshCw,
  Search,
  Stethoscope,
  UserPlus,
  UserRound,
  WifiOff,
  X,
} from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import { request } from "../../core/api";
import {
  subscribeRealtime,
  type RealtimeConnectionState,
} from "../../core/realtime";
import type {
  Appointment,
  AvailabilitySlot,
  Doctor,
  Patient,
  Tokens,
} from "../../core/types";
import {
  BookingConflictDialog,
  NotificationDeliveryStatus,
} from "./ReceptionAppointmentActions";
import {
  type BookingIssue,
  clinicDateInput,
  formatReceptionDateTime,
  formatReceptionTime,
  isConfirmedAppointmentStatus,
  receptionSlotDetails,
  toBookingIssue,
} from "./receptionBookingModel";

type PatientPage = { content: Patient[]; totalElements: number };
type LoadState = "idle" | "loading" | "success" | "error";
type BookingSuccess = {
  appointment: Appointment;
  patient: Patient;
  doctor: Doctor;
  slot: AvailabilitySlot;
};
type BookingAttempt = { key: string; appointment?: Appointment };

function patientIdentitySummary(patient: Patient) {
  const phone = patient.phone || "Chưa có số điện thoại";
  const dob = patient.dob
    ? new Date(`${patient.dob}T00:00:00`).toLocaleDateString("vi-VN")
    : "Chưa khai báo ngày sinh";
  return `${phone}, ${dob}`;
}

function connectionLabel(state: RealtimeConnectionState) {
  if (state === "connected") return "Giờ trống đang cập nhật trực tiếp";
  if (state === "reconnecting") return "Mất kết nối trực tiếp, đang dùng cập nhật dự phòng";
  if (state === "closed") return "Kết nối trực tiếp đã đóng";
  return "Đang kết nối dữ liệu giờ trống";
}

export default function ReceptionHotlineBookingView({ session }: { session: Tokens }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [searchState, setSearchState] = useState<LoadState>("idle");
  const [searchAttempted, setSearchAttempted] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState("");
  const [patientNotice, setPatientNotice] = useState("");
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newDob, setNewDob] = useState("");

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [doctorId, setDoctorId] = useState("");
  const [doctorState, setDoctorState] = useState<LoadState>("idle");
  const [doctorError, setDoctorError] = useState("");
  const [date, setDate] = useState(() => clinicDateInput());
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<AvailabilitySlot | null>(null);
  const [slotState, setSlotState] = useState<LoadState>("idle");
  const [slotError, setSlotError] = useState("");
  const [liveNotice, setLiveNotice] = useState("");
  const [changedSlots, setChangedSlots] = useState<Set<string>>(new Set());
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [realtimeState, setRealtimeState] = useState<RealtimeConnectionState>("connecting");

  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [bookingBusy, setBookingBusy] = useState(false);
  const [bookingError, setBookingError] = useState("");
  const [partialAppointment, setPartialAppointment] = useState<Appointment | null>(null);
  const [success, setSuccess] = useState<BookingSuccess | null>(null);
  const [conflict, setConflict] = useState<BookingIssue | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const resultRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const doctorSectionRef = useRef<HTMLElement>(null);
  const dateInputRef = useRef<HTMLInputElement>(null);
  const slotSectionRef = useRef<HTMLElement>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const selectedSlotRef = useRef<AvailabilitySlot | null>(null);
  const previousSlotStatesRef = useRef<Map<string, AvailabilitySlot["status"]>>(new Map());
  const highlightTimerRef = useRef<number | null>(null);
  const bookingAttemptRef = useRef<BookingAttempt | null>(null);

  const doctor = doctors.find(item => item.id === doctorId) || null;
  const workflowLocked = Boolean(partialAppointment) || bookingBusy;

  useEffect(() => {
    selectedSlotRef.current = selectedSlot;
  }, [selectedSlot]);

  const searchPatients = useCallback(async (value = query) => {
    setSearchState("loading");
    setSearchAttempted(true);
    setSearchError("");
    try {
      const page = await request<PatientPage>(
        `/patients?query=${encodeURIComponent(value.trim())}`,
        session.accessToken,
      );
      setPatients(page.content || []);
      setSearchState("success");
    } catch (cause) {
      setPatients([]);
      setSearchState("error");
      setSearchError(toBookingIssue(cause).detail);
    }
  }, [query, session.accessToken]);

  const loadDoctors = useCallback(async () => {
    setDoctorState("loading");
    setDoctorError("");
    try {
      const list = await request<Doctor[]>("/doctors", session.accessToken);
      setDoctors(list);
      setDoctorId(current => current && list.some(item => item.id === current)
        ? current
        : list[0]?.id || "");
      setDoctorState("success");
    } catch (cause) {
      setDoctorState("error");
      setDoctorError(toBookingIssue(cause).detail);
    }
  }, [session.accessToken]);

  const loadSlots = useCallback(async (background = false) => {
    if (!open || !selectedPatient || !doctorId || !date) return;
    if (!background) {
      setSlotState("loading");
      setSlotError("");
    }
    try {
      const result = await request<{ items: AvailabilitySlot[] }>(
        `/appointments/availability?doctorId=${encodeURIComponent(doctorId)}`
          + `&date=${encodeURIComponent(date)}&durationMinutes=30`,
        session.accessToken,
      );
      const nextSlots = result.items || [];
      const previousStates = previousSlotStatesRef.current;
      const changed = new Set<string>();
      nextSlots.forEach(slot => {
        const previous = previousStates.get(slot.startAt);
        if (previous && previous !== slot.status) changed.add(slot.startAt);
      });
      previousSlotStatesRef.current = new Map(nextSlots.map(slot => [slot.startAt, slot.status]));
      if (changed.size) {
        setChangedSlots(changed);
        if (highlightTimerRef.current !== null) window.clearTimeout(highlightTimerRef.current);
        highlightTimerRef.current = window.setTimeout(() => setChangedSlots(new Set()), 900);
      }

      const currentSelection = selectedSlotRef.current;
      if (currentSelection) {
        const latest = nextSlots.find(slot => slot.startAt === currentSelection.startAt);
        if (!latest || latest.status !== "AVAILABLE") {
          selectedSlotRef.current = null;
          setSelectedSlot(null);
          setConflict({
            code: "SLOT_CHANGED",
            title: "Khung giờ vừa thay đổi",
            detail: "Khung giờ đang chọn không còn trống sau lần cập nhật mới nhất.",
            action: "Chọn một khung giờ còn trống khác.",
            conflict: true,
          });
        } else if (latest !== currentSelection) {
          selectedSlotRef.current = latest;
          setSelectedSlot(latest);
        }
      }

      setSlots(nextSlots);
      setSlotState("success");
      setSlotError("");
      setLiveNotice("");
      setLastUpdatedAt(new Date());
    } catch (cause) {
      const issue = toBookingIssue(cause);
      if (background) {
        setLiveNotice("Không thể cập nhật giờ trống mới nhất. Dữ liệu gần nhất vẫn được giữ lại.");
      } else {
        setSlots([]);
        setSlotState("error");
        setSlotError(issue.detail);
      }
    }
  }, [date, doctorId, open, selectedPatient, session.accessToken]);

  async function show() {
    setOpen(true);
    setSuccess(null);
    if (!doctors.length) void loadDoctors();
    if (!searchAttempted) void searchPatients("");
  }

  function close() {
    if (bookingBusy) return;
    setOpen(false);
    setConflict(null);
  }

  useEffect(() => {
    const openFromDashboard = () => { void show() };
    window.addEventListener("open-hotline-booking", openFromDashboard);
    return () => window.removeEventListener("open-hotline-booking", openFromDashboard);
  }, [doctors.length, loadDoctors, searchAttempted, searchPatients]);

  useEffect(() => {
    const refresh = () => { void loadDoctors() };
    window.addEventListener("doctor-profiles-changed", refresh);
    return () => window.removeEventListener("doctor-profiles-changed", refresh);
  }, [loadDoctors]);

  useEffect(() => {
    if (!open || !selectedPatient || !doctorId || !date) return;
    void loadSlots(false);
  }, [date, doctorId, open, selectedPatient?.id]);

  useEffect(() => {
    if (!open || !selectedPatient || !doctorId || !date) return;
    const refresh = () => { void loadSlots(true) };
    const unsubscribe = subscribeRealtime(event => {
      if (event.type === "SLOTS_CHANGED") refresh();
    }, { onConnectionChange: setRealtimeState });
    const fallback = window.setInterval(refresh, 5_000);
    window.addEventListener("focus", refresh);
    return () => {
      unsubscribe();
      window.clearInterval(fallback);
      window.removeEventListener("focus", refresh);
    };
  }, [date, doctorId, loadSlots, open, selectedPatient?.id]);

  useEffect(() => () => {
    if (highlightTimerRef.current !== null) window.clearTimeout(highlightTimerRef.current);
  }, []);

  function selectPatient(patient: Patient) {
    if (workflowLocked) return;
    if (selectedPatient?.id !== patient.id) {
      setReason("");
      setSelectedSlot(null);
      selectedSlotRef.current = null;
      bookingAttemptRef.current = null;
    }
    setSelectedPatient(patient);
    setCreateOpen(false);
    setCreateError("");
    setPatientNotice("");
    setBookingError("");
  }

  function changePatient() {
    if (workflowLocked) return;
    setSelectedPatient(null);
    setSelectedSlot(null);
    selectedSlotRef.current = null;
    setSlots([]);
    setReason("");
    setReasonError("");
    setPatientNotice("Đã bỏ thông tin lịch của bệnh nhân trước. Hãy xác minh lại người gọi.");
    bookingAttemptRef.current = null;
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  }

  async function createPatient(event: FormEvent) {
    event.preventDefault();
    if (createBusy) return;
    setCreateBusy(true);
    setCreateError("");
    try {
      const patient = await request<Patient>("/patients/hotline", session.accessToken, {
        method: "POST",
        body: JSON.stringify({
          fullName: newName.trim(),
          phone: newPhone.trim(),
          dob: newDob || null,
        }),
      });
      setPatients(current => [patient, ...current.filter(item => item.id !== patient.id)]);
      selectPatient(patient);
      setNewName("");
      setNewPhone("");
      setNewDob("");
      setPatientNotice("Đã chọn hồ sơ theo số điện thoại. Nếu hồ sơ đã tồn tại, hệ thống sử dụng hồ sơ cũ.");
    } catch (cause) {
      setCreateError(toBookingIssue(cause).detail);
    } finally {
      setCreateBusy(false);
    }
  }

  function handleResultKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const direction = event.key === "ArrowDown" ? 1 : -1;
    const next = (index + direction + patients.length) % patients.length;
    resultRefs.current[next]?.focus();
  }

  function selectSlot(slot: AvailabilitySlot) {
    if (workflowLocked) return;
    const details = receptionSlotDetails(slot.status);
    if (!details.selectable) return;
    const next = selectedSlot?.startAt === slot.startAt ? null : slot;
    selectedSlotRef.current = next;
    setSelectedSlot(next);
    setBookingError("");
    setConflict(null);
    bookingAttemptRef.current = null;
  }

  function validateBooking() {
    if (!selectedPatient) {
      setBookingError("Chọn đúng bệnh nhân trước khi xác nhận lịch.");
      searchInputRef.current?.focus();
      return false;
    }
    if (!doctor) {
      setBookingError("Chọn bác sĩ trước khi xác nhận lịch.");
      doctorSectionRef.current?.focus();
      return false;
    }
    if (!selectedSlot) {
      setBookingError("Chọn một khung giờ còn trống trước khi xác nhận lịch.");
      slotSectionRef.current?.focus();
      return false;
    }
    if (!reason.trim()) {
      setReasonError("Nhập lý do khám do bệnh nhân cung cấp.");
      reasonRef.current?.focus();
      return false;
    }
    setReasonError("");
    return true;
  }

  function finishBooking(confirmed: Appointment, slot: AvailabilitySlot, patient: Patient, selectedDoctor: Doctor) {
    setSuccess({ appointment: confirmed, patient, doctor: selectedDoctor, slot });
    setPartialAppointment(null);
    setBookingError("");
    bookingAttemptRef.current = null;
    window.dispatchEvent(new Event("reception-appointments-changed"));
  }

  async function confirmCreatedAppointment(
    appointment: Appointment,
    slot: AvailabilitySlot,
    patient: Patient,
    selectedDoctor: Doctor,
  ) {
    try {
      const confirmed = await request<Appointment>(
        `/appointments/${appointment.id}/confirm`,
        session.accessToken,
        { method: "POST" },
      );
      finishBooking(confirmed, slot, patient, selectedDoctor);
      return true;
    } catch (cause) {
      const latest = await request<Appointment>(
        `/appointments/${appointment.id}`,
        session.accessToken,
      ).catch(() => null);
      if (latest && isConfirmedAppointmentStatus(latest.status)) {
        finishBooking(latest, slot, patient, selectedDoctor);
        return true;
      }
      setPartialAppointment(latest || appointment);
      setBookingError(
        "Yêu cầu lịch đã được tạo nhưng bước xác nhận chưa hoàn tất. Không tạo lịch mới, hãy thử xác nhận lại.",
      );
      return false;
    }
  }

  async function book() {
    if (!validateBooking() || bookingBusy || !selectedPatient || !selectedSlot || !doctor) return;
    setBookingBusy(true);
    setBookingError("");
    const patient = selectedPatient;
    const slot = selectedSlot;
    const selectedDoctor = doctor;
    const attempt = bookingAttemptRef.current || { key: crypto.randomUUID() };
    bookingAttemptRef.current = attempt;
    try {
      let appointment = attempt.appointment;
      if (!appointment) {
        appointment = await request<Appointment>("/appointments", session.accessToken, {
          method: "POST",
          headers: { "Idempotency-Key": attempt.key },
          body: JSON.stringify({
            patientId: patient.id,
            patientIdentityId: patient.identityId,
            doctorId: slot.doctorId,
            doctorIdentityId: slot.doctorIdentityId,
            startAt: slot.startAt,
            endAt: slot.endAt,
            reason: reason.trim(),
          }),
        });
        attempt.appointment = appointment;
      }
      await confirmCreatedAppointment(appointment, slot, patient, selectedDoctor);
    } catch (cause) {
      const issue = toBookingIssue(cause);
      if (issue.conflict) {
        setConflict(issue);
        selectedSlotRef.current = null;
        setSelectedSlot(null);
        bookingAttemptRef.current = null;
        void loadSlots(true);
      } else {
        setBookingError(issue.detail);
      }
    } finally {
      setBookingBusy(false);
    }
  }

  async function retryConfirmation() {
    const appointment = partialAppointment;
    const patient = selectedPatient;
    const slot = selectedSlot;
    const selectedDoctor = doctor;
    if (!appointment || !patient || !slot || !selectedDoctor || bookingBusy) return;
    setBookingBusy(true);
    setBookingError("");
    try {
      await confirmCreatedAppointment(appointment, slot, patient, selectedDoctor);
    } finally {
      setBookingBusy(false);
    }
  }

  function resetForAnotherBooking() {
    setSuccess(null);
    setSelectedPatient(null);
    setSelectedSlot(null);
    selectedSlotRef.current = null;
    setSlots([]);
    setReason("");
    setReasonError("");
    setBookingError("");
    setPartialAppointment(null);
    setPatientNotice("");
    bookingAttemptRef.current = null;
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  }

  function openAcceptedAppointments() {
    close();
    window.dispatchEvent(new CustomEvent("reception-navigate", { detail: "records" }));
  }

  function focusSection(target: "patient" | "doctor" | "date" | "slot" | "reason") {
    if (target === "patient") {
      changePatient();
      return;
    }
    const element = target === "doctor" ? doctorSectionRef.current
      : target === "date" ? dateInputRef.current
        : target === "slot" ? slotSectionRef.current
          : reasonRef.current;
    element?.scrollIntoView({ behavior: "smooth", block: "center" });
    element?.focus();
  }

  const availableCount = slots.filter(slot => slot.status === "AVAILABLE").length;

  return (
    <>
      <button
        type="button"
        className="hotline-launch"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => void show()}
      >
        <PhoneCall aria-hidden="true" />
        <span>Đặt lịch hotline</span>
      </button>

      {open && (
        <AccessibleDialog
          title={success ? "Lịch hotline đã được xác nhận" : "Đặt lịch qua hotline"}
          titleId="reception-hotline-title"
          descriptionId="reception-hotline-description"
          className="reception-hotline-dialog"
          backdropClassName="reception-hotline-backdrop"
          closeOnBackdrop={!bookingBusy}
          onClose={close}
        >
          <div className="reception-hotline-intro">
            <div>
              <PhoneCall aria-hidden="true" />
              <span><strong>Hotline phòng khám</strong><a href="tel:0352790904">0352 790 904</a></span>
            </div>
            <p>Xác minh người gọi, đọc lại lịch hẹn và chỉ kết thúc khi hệ thống xác nhận.</p>
          </div>

          {success ? (
            <section className="hotline-success" aria-live="polite">
              <CheckCircle2 aria-hidden="true" />
              <h3>Đã xác nhận lịch khám</h3>
              <p>Thông tin bên dưới là kết quả trả về sau khi thao tác hoàn tất.</p>
              <dl>
                <div><dt>Mã lịch</dt><dd>{success.appointment.id}</dd></div>
                <div><dt>Bệnh nhân</dt><dd>{success.patient.fullName}</dd></div>
                <div><dt>Số điện thoại</dt><dd>{success.patient.phone || "Chưa có"}</dd></div>
                <div><dt>Bác sĩ</dt><dd>BS. {success.doctor.fullName}</dd></div>
                <div><dt>Thời gian</dt><dd>{formatReceptionDateTime(success.slot.startAt)}</dd></div>
                <div><dt>Trạng thái</dt><dd>Đã xác nhận</dd></div>
              </dl>
              <NotificationDeliveryStatus />
              <div className="hotline-success-actions">
                <button type="button" onClick={resetForAnotherBooking}>Tạo lịch khác</button>
                <button type="button" className="hotline-primary-button" onClick={openAcceptedAppointments}>
                  Xem lịch đã nhận
                </button>
              </div>
            </section>
          ) : (
            <div className="reception-hotline-layout">
              <div className="reception-hotline-flow">
                <section className="hotline-work-section" aria-labelledby="hotline-patient-title">
                  <header className="hotline-section-heading">
                    <span aria-hidden="true"><UserRound /></span>
                    <div><h3 id="hotline-patient-title">Xác định bệnh nhân</h3><p>Tìm đúng hồ sơ bằng họ tên hoặc số điện thoại.</p></div>
                  </header>

                  {selectedPatient ? (
                    <div className="hotline-selected-patient" aria-live="polite">
                      <span aria-hidden="true">{selectedPatient.fullName.slice(0, 1).toUpperCase()}</span>
                      <div>
                        <strong>{selectedPatient.fullName}</strong>
                        <small>{patientIdentitySummary(selectedPatient)}</small>
                        <em>{selectedPatient.accountLinked ? "Đã liên kết tài khoản" : "Hồ sơ tiếp nhận qua hotline"}</em>
                      </div>
                      <Check aria-hidden="true" />
                      <button type="button" disabled={workflowLocked} onClick={changePatient}>Đổi bệnh nhân</button>
                    </div>
                  ) : (
                    <>
                      <form className="hotline-search" role="search" onSubmit={event => {
                        event.preventDefault();
                        void searchPatients();
                      }}>
                        <label htmlFor="hotline-patient-search">Họ tên hoặc số điện thoại</label>
                        <div>
                          <Search aria-hidden="true" />
                          <input
                            ref={searchInputRef}
                            id="hotline-patient-search"
                            value={query}
                            onChange={event => setQuery(event.target.value)}
                            placeholder="Ví dụ: Nguyễn An hoặc 0352790904"
                            autoComplete="off"
                          />
                          {query && (
                            <button type="button" aria-label="Xóa nội dung tìm kiếm" onClick={() => {
                              setQuery("");
                              setSearchAttempted(false);
                              setPatients([]);
                              searchInputRef.current?.focus();
                            }}>
                              <X aria-hidden="true" />
                            </button>
                          )}
                        </div>
                        <button type="submit" disabled={searchState === "loading"}>
                          {searchState === "loading" ? "Đang tìm..." : "Tìm bệnh nhân"}
                        </button>
                      </form>

                      <div className="hotline-results" aria-live="polite" aria-busy={searchState === "loading"}>
                        {searchState === "loading" ? (
                          <div className="hotline-state" role="status">
                            <RefreshCw aria-hidden="true" /><span>Đang tìm hồ sơ phù hợp...</span>
                          </div>
                        ) : searchError ? (
                          <div className="hotline-state hotline-state-error" role="alert">
                            <strong>Không thể tìm bệnh nhân</strong><span>{searchError}</span>
                            <button type="button" onClick={() => void searchPatients()}>Thử lại</button>
                          </div>
                        ) : searchAttempted && patients.length === 0 ? (
                          <div className="hotline-state">
                            <strong>Không tìm thấy hồ sơ</strong>
                            <span>Kiểm tra lại tên, số điện thoại hoặc tạo hồ sơ hotline mới.</span>
                          </div>
                        ) : (
                          patients.map((patient, index) => (
                            <button
                              key={patient.id}
                              ref={element => { resultRefs.current[index] = element }}
                              type="button"
                              onKeyDown={event => handleResultKeyDown(event, index)}
                              onClick={() => selectPatient(patient)}
                            >
                              <span aria-hidden="true">{patient.fullName.slice(0, 1).toUpperCase()}</span>
                              <div><strong>{patient.fullName}</strong><small>{patientIdentitySummary(patient)}</small></div>
                              <em>{patient.accountLinked ? "Có tài khoản" : "Hồ sơ hotline"}</em>
                            </button>
                          ))
                        )}
                      </div>

                      <button
                        type="button"
                        className="hotline-create-toggle"
                        aria-expanded={createOpen}
                        aria-controls="hotline-create-patient"
                        onClick={() => {
                          setCreateOpen(current => !current);
                          setCreateError("");
                        }}
                      >
                        <UserPlus aria-hidden="true" />
                        {createOpen ? "Đóng phần tạo hồ sơ" : "Người gọi chưa có hồ sơ"}
                      </button>
                      {createOpen && (
                        <form id="hotline-create-patient" className="hotline-create" onSubmit={createPatient}>
                          <div className="hotline-create-heading">
                            <strong>Tạo hồ sơ tối thiểu</strong>
                            <span>Chỉ tạo sau khi đã đọc lại thông tin với người gọi.</span>
                          </div>
                          <label htmlFor="hotline-new-name">Họ và tên <span aria-hidden="true">*</span></label>
                          <input
                            id="hotline-new-name"
                            required
                            maxLength={160}
                            value={newName}
                            onChange={event => setNewName(event.target.value)}
                          />
                          <label htmlFor="hotline-new-phone">Số điện thoại <span aria-hidden="true">*</span></label>
                          <input
                            id="hotline-new-phone"
                            required
                            type="tel"
                            inputMode="tel"
                            minLength={8}
                            maxLength={20}
                            pattern="[0-9+ .()\-]{8,20}"
                            value={newPhone}
                            onChange={event => setNewPhone(event.target.value)}
                            placeholder="0352790904"
                          />
                          <label htmlFor="hotline-new-dob">Ngày sinh</label>
                          <input
                            id="hotline-new-dob"
                            type="date"
                            max={clinicDateInput()}
                            value={newDob}
                            onChange={event => setNewDob(event.target.value)}
                          />
                          {createError && <div className="hotline-inline-error" role="alert">{createError}</div>}
                          <button type="submit" disabled={createBusy || !newName.trim() || !newPhone.trim()}>
                            {createBusy ? "Đang tạo hồ sơ..." : "Tạo và chọn hồ sơ"}
                          </button>
                        </form>
                      )}
                    </>
                  )}
                  {patientNotice && <div className="hotline-inline-notice" role="status">{patientNotice}</div>}
                </section>

                <section
                  ref={doctorSectionRef}
                  className="hotline-work-section"
                  aria-labelledby="hotline-doctor-title"
                  tabIndex={-1}
                >
                  <header className="hotline-section-heading">
                    <span aria-hidden="true"><Stethoscope /></span>
                    <div><h3 id="hotline-doctor-title">Chọn bác sĩ</h3><p>Chỉ hiển thị thông tin cần để xếp lịch.</p></div>
                  </header>
                  {!selectedPatient ? (
                    <div className="hotline-state"><span>Chọn bệnh nhân trước để tiếp tục.</span></div>
                  ) : doctorState === "loading" ? (
                    <div className="hotline-state" role="status"><RefreshCw aria-hidden="true" /><span>Đang tải bác sĩ...</span></div>
                  ) : doctorError ? (
                    <div className="hotline-state hotline-state-error" role="alert">
                      <strong>Không thể tải bác sĩ</strong><span>{doctorError}</span>
                      <button type="button" onClick={() => void loadDoctors()}>Thử lại</button>
                    </div>
                  ) : doctors.length === 0 ? (
                    <div className="hotline-state"><strong>Chưa có bác sĩ</strong><span>Không thể tạo lịch hotline lúc này.</span></div>
                  ) : (
                    <div className="booking-doctor-selector hotline-doctor-selector" aria-label="Danh sách bác sĩ">
                      {doctors.map(item => (
                        <button
                          key={item.id}
                          type="button"
                          disabled={workflowLocked}
                          className={doctorId === item.id ? "is-selected" : ""}
                          aria-pressed={doctorId === item.id}
                          onClick={() => {
                            setDoctorId(item.id);
                            setSelectedSlot(null);
                            selectedSlotRef.current = null;
                            bookingAttemptRef.current = null;
                          }}
                        >
                          {item.avatarUrl ? <img src={item.avatarUrl} alt={`Ảnh BS. ${item.fullName}`} />
                            : <span aria-hidden="true">{item.fullName.slice(0, 1).toUpperCase()}</span>}
                          <div>
                            <strong>BS. {item.fullName}</strong>
                            <small>{item.specialtyCode}</small>
                            <em>{item.experienceYears} năm kinh nghiệm</em>
                          </div>
                          <Check aria-hidden="true" />
                        </button>
                      ))}
                    </div>
                  )}
                </section>

                <section className="hotline-work-section" aria-labelledby="hotline-date-title">
                  <header className="hotline-section-heading">
                    <span aria-hidden="true"><CalendarDays /></span>
                    <div><h3 id="hotline-date-title">Chọn ngày khám</h3><p>Nhận lịch trong phạm vi 60 ngày tới.</p></div>
                  </header>
                  <div className="booking-field hotline-date-field">
                    <label htmlFor="hotline-date">Ngày khám</label>
                    <input
                      ref={dateInputRef}
                      id="hotline-date"
                      type="date"
                      min={clinicDateInput()}
                      max={clinicDateInput(60)}
                      disabled={!selectedPatient || !doctorId || workflowLocked}
                      value={date}
                      onChange={event => {
                        setDate(event.target.value);
                        setSelectedSlot(null);
                        selectedSlotRef.current = null;
                        bookingAttemptRef.current = null;
                      }}
                    />
                    <small>Giờ khám được hiển thị theo múi giờ Việt Nam.</small>
                  </div>
                </section>

                <section
                  ref={slotSectionRef}
                  className="hotline-work-section"
                  aria-labelledby="hotline-slot-title"
                  tabIndex={-1}
                >
                  <header className="hotline-section-heading hotline-slot-heading">
                    <span aria-hidden="true"><Clock3 /></span>
                    <div><h3 id="hotline-slot-title">Chọn khung giờ</h3><p>Mỗi lượt khám kéo dài 30 phút.</p></div>
                    <div className={`hotline-live-state is-${realtimeState}`}>
                      {realtimeState === "connected" ? <Check aria-hidden="true" /> : <WifiOff aria-hidden="true" />}
                      <span>{connectionLabel(realtimeState)}</span>
                    </div>
                  </header>
                  {lastUpdatedAt && (
                    <div className="hotline-slot-meta" aria-live="polite">
                      <span>{availableCount} giờ còn trống</span>
                      <span>Cập nhật lúc {lastUpdatedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                  )}
                  <div className="booking-slot-grid reception-slot-grid" aria-busy={slotState === "loading"}>
                    {!selectedPatient || !doctorId ? (
                      <div className="booking-state"><span>Chọn bệnh nhân và bác sĩ để xem giờ trống.</span></div>
                    ) : slotState === "loading" && slots.length === 0 ? (
                      <div className="booking-slot-loading" role="status">
                        <span>Đang kiểm tra lịch bác sĩ...</span>
                        {Array.from({ length: 8 }, (_, index) => <i key={index} aria-hidden="true" />)}
                      </div>
                    ) : slotError ? (
                      <div className="booking-state hotline-state-error" role="alert">
                        <strong>Không thể tải giờ trống</strong><span>{slotError}</span>
                        <button type="button" onClick={() => void loadSlots(false)}>Thử lại</button>
                      </div>
                    ) : slots.length === 0 ? (
                      <div className="booking-state">
                        <Clock3 aria-hidden="true" /><strong>Không có khung giờ</strong><span>Chọn ngày khác hoặc bác sĩ khác.</span>
                      </div>
                    ) : (
                      slots.map(slot => {
                        const details = receptionSlotDetails(slot.status);
                        const selected = selectedSlot?.startAt === slot.startAt;
                        return (
                          <button
                            key={slot.startAt}
                            type="button"
                            disabled={!details.selectable || workflowLocked}
                            className={[
                              details.className,
                              selected ? "is-selected" : "",
                              changedSlots.has(slot.startAt) ? "is-updated" : "",
                            ].filter(Boolean).join(" ")}
                            aria-pressed={selected}
                            aria-label={`${formatReceptionTime(slot.startAt)}, ${details.label}`}
                            onClick={() => selectSlot(slot)}
                          >
                            <strong>{formatReceptionTime(slot.startAt)}</strong>
                            <small>{selected ? "Đã chọn" : details.label}</small>
                          </button>
                        );
                      })
                    )}
                  </div>
                  <p className="hotline-no-hold-note">
                    Luồng hotline không giữ slot tạm. Hệ thống kiểm tra lại khung giờ khi lễ tân xác nhận.
                  </p>
                  {liveNotice && <div className="hotline-inline-notice" role="status">{liveNotice}</div>}
                </section>

                <section className="hotline-work-section" aria-labelledby="hotline-reason-title">
                  <header className="hotline-section-heading">
                    <span aria-hidden="true"><Stethoscope /></span>
                    <div><h3 id="hotline-reason-title">Ghi nhận lý do khám</h3><p>Nhập đúng nội dung bệnh nhân cung cấp qua điện thoại.</p></div>
                  </header>
                  <div className="booking-field">
                    <label htmlFor="hotline-reason">Lý do khám <span aria-hidden="true">*</span></label>
                    <textarea
                      ref={reasonRef}
                      id="hotline-reason"
                      required
                      maxLength={500}
                      disabled={!selectedPatient || workflowLocked}
                      aria-describedby="hotline-reason-help"
                      aria-invalid={Boolean(reasonError)}
                      value={reason}
                      onChange={event => {
                        setReason(event.target.value);
                        if (event.target.value.trim()) setReasonError("");
                        bookingAttemptRef.current = null;
                      }}
                      placeholder="Ví dụ: ngứa da kéo dài 3 ngày, bệnh nhân muốn kiểm tra trực tiếp"
                    />
                    <small id="hotline-reason-help">Nội dung này đi cùng lịch hẹn. Không nhập ghi chú nội bộ tại đây.</small>
                    {reasonError && <span className="hotline-field-error" role="alert">{reasonError}</span>}
                  </div>
                </section>
              </div>

              <aside className="hotline-review" aria-labelledby="hotline-review-title">
                <div className="hotline-review-heading">
                  <span aria-hidden="true"><PhoneCall /></span>
                  <div><h3 id="hotline-review-title">Đọc lại với bệnh nhân</h3><p>Kiểm tra đủ thông tin trước khi xác nhận.</p></div>
                </div>
                <dl>
                  <div><dt>Bệnh nhân</dt><dd>{selectedPatient?.fullName || "Chưa chọn"}</dd><button type="button" disabled={workflowLocked} onClick={() => focusSection("patient")}>Sửa</button></div>
                  <div><dt>Số điện thoại</dt><dd>{selectedPatient?.phone || "Chưa có"}</dd></div>
                  <div><dt>Bác sĩ</dt><dd>{doctor ? `BS. ${doctor.fullName}` : "Chưa chọn"}</dd><button type="button" disabled={workflowLocked} onClick={() => focusSection("doctor")}>Sửa</button></div>
                  <div><dt>Ngày khám</dt><dd>{date ? new Date(`${date}T00:00:00`).toLocaleDateString("vi-VN") : "Chưa chọn"}</dd><button type="button" disabled={workflowLocked} onClick={() => focusSection("date")}>Sửa</button></div>
                  <div><dt>Khung giờ</dt><dd>{selectedSlot ? formatReceptionTime(selectedSlot.startAt) : "Chưa chọn"}</dd><button type="button" disabled={workflowLocked} onClick={() => focusSection("slot")}>Sửa</button></div>
                  <div><dt>Lý do khám</dt><dd className="hotline-review-reason">{reason.trim() || "Chưa nhập"}</dd><button type="button" disabled={workflowLocked} onClick={() => focusSection("reason")}>Sửa</button></div>
                  <div><dt>Kênh đặt</dt><dd>Hotline</dd></div>
                  <div><dt>Trạng thái slot</dt><dd>{selectedSlot ? "Sẽ kiểm tra lại khi xác nhận" : "Chưa chọn"}</dd></div>
                </dl>

                {partialAppointment && (
                  <div className="hotline-partial-status" role="alert">
                    <strong>Yêu cầu đã được tạo</strong>
                    <span>Mã lịch: {partialAppointment.id}</span>
                    <p>Không tạo lịch mới. Hãy thử xác nhận lại hoặc mở danh sách yêu cầu để xử lý.</p>
                  </div>
                )}

                {bookingError && <div className="hotline-booking-error" role="alert">{bookingError}</div>}

                <button
                  type="button"
                  className="hotline-confirm"
                  disabled={bookingBusy || (!partialAppointment && (!selectedPatient || !selectedSlot || !reason.trim()))}
                  onClick={() => partialAppointment ? void retryConfirmation() : void book()}
                >
                  {bookingBusy
                    ? "Đang chờ hệ thống xác nhận..."
                    : partialAppointment
                      ? "Thử xác nhận lại"
                      : "Xác nhận đặt lịch"}
                </button>
                {partialAppointment && (
                  <button type="button" className="hotline-secondary-action" onClick={() => {
                    close();
                    window.dispatchEvent(new CustomEvent("reception-navigate", { detail: "appointments" }));
                  }}>
                    Xem yêu cầu đã tạo
                  </button>
                )}
                <small className="hotline-confirm-help">Không báo thành công trước khi nhận xác nhận từ hệ thống.</small>
              </aside>
            </div>
          )}
        </AccessibleDialog>
      )}

      {conflict && (
        <BookingConflictDialog
          issue={conflict}
          onClose={() => setConflict(null)}
          primaryLabel={conflict.code === "SAME_DOCTOR_SAME_DAY" || conflict.code === "BOOKING_TOO_FAR_AHEAD"
            ? "Chọn ngày khác"
            : conflict.code === "ACTIVE_APPOINTMENT_LIMIT"
              ? "Xem lịch đã nhận"
              : "Chọn giờ khác"}
          onChooseAnother={() => {
            const code = conflict.code;
            setConflict(null);
            setSelectedSlot(null);
            selectedSlotRef.current = null;
            if (code === "ACTIVE_APPOINTMENT_LIMIT") {
              close();
              window.dispatchEvent(new CustomEvent("reception-navigate", { detail: "records" }));
              return;
            }
            window.setTimeout(() => {
              if (code === "SAME_DOCTOR_SAME_DAY" || code === "BOOKING_TOO_FAR_AHEAD") {
                dateInputRef.current?.focus();
              } else {
                slotSectionRef.current?.focus();
              }
            }, 0);
          }}
        />
      )}
    </>
  );
}
