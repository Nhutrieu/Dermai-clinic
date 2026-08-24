import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertTriangle,
  CalendarPlus,
  Headphones,
  History,
  RefreshCw,
  Search,
  ShieldCheck,
  UserPlus,
  UserRound,
  X,
} from "lucide-react";
import { request } from "../../core/api";
import type { Appointment, Patient } from "../../core/types";
import {
  ReceptionCancelControl,
  ReceptionRescheduleControl,
} from "./ReceptionAppointmentActions";
import { toBookingIssue } from "./receptionBookingModel";
import { getReceptionStatus } from "./receptionDashboardModel";
import {
  duplicatePatientNameIds,
  maskPatientPhone,
  nextPatientAppointment,
  patientRecordCode,
  splitPatientAppointments,
} from "./receptionPatientModel";

type LoadState = "idle" | "loading" | "success" | "error";

type Props = {
  token: string;
  appointments: Appointment[];
  searchResults: Patient[];
  selectedPatientId: string;
  query: string;
  lastSearchTerm: string;
  searchLoading: boolean;
  searchAttempted: boolean;
  searchError: string;
  doctorName: (appointment: Appointment) => string;
  onQueryChange: (value: string) => void;
  onSearch: () => Promise<void>;
  onClearSearch: () => void;
  onSelectPatient: (patientId: string) => void;
  onOpenSupport: (patient: Patient) => void;
  onOpenHotline: (patient?: Patient) => void;
};

const HISTORY_MONTHS = 18;
const UPCOMING_MONTHS = 12;

function formatDate(value?: string) {
  if (!value) return "Chưa khai báo";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(`${value}T00:00:00`));
}

function formatAppointmentDateTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}

function PatientStatusBadge({ patient }: { patient: Patient }) {
  const label = patient.accountLinked === true
    ? "Đã liên kết tài khoản"
    : patient.accountLinked === false
      ? "Hồ sơ qua điện thoại"
      : "Chưa có trạng thái tài khoản";
  return <span className={`reception-patient-account ${patient.accountLinked ? "is-linked" : ""}`}>{label}</span>;
}

function AppointmentStatusBadge({ status }: { status: string }) {
  const presentation = getReceptionStatus(status);
  return <span className={`reception-status reception-status-${presentation.tone}`}>{presentation.label}</span>;
}

function AppointmentRow({
  appointment,
  patient,
  doctorName,
  token,
  onChanged,
}: {
  appointment: Appointment;
  patient: Patient;
  doctorName: string;
  token: string;
  onChanged: () => void;
}) {
  const rescheduleKeys = useRef(new Map<string, string>());

  async function reschedule(value: string) {
    const attempt = `${appointment.id}:${value}`;
    const key = rescheduleKeys.current.get(attempt) || crypto.randomUUID();
    rescheduleKeys.current.set(attempt, key);
    const start = new Date(value);
    return request<Appointment>(`/appointments/${appointment.id}/reschedule`, token, {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: JSON.stringify({
        startAt: start.toISOString(),
        // Keep the existing receptionist reschedule payload and its 30-minute slot rule.
        endAt: new Date(start.getTime() + 30 * 60_000).toISOString(),
      }),
    });
  }

  async function cancel(reason: string) {
    return request<Appointment>(`/appointments/${appointment.id}/cancel`, token, {
      method: "POST",
      body: JSON.stringify({ reason: reason.trim() }),
    });
  }

  return (
    <article className="reception-patient-appointment-row">
      <div className="reception-patient-appointment-main">
        <time dateTime={appointment.startAt}>{formatAppointmentDateTime(appointment.startAt)}</time>
        <strong>BS. {doctorName}</strong>
        {appointment.reason && <p>{appointment.reason}</p>}
      </div>
      <AppointmentStatusBadge status={appointment.status} />
      {appointment.status === "CONFIRMED" && (
        <div className="reception-patient-appointment-actions">
          <ReceptionRescheduleControl
            token={token}
            appointment={appointment}
            patientName={patient.fullName}
            doctorName={doctorName}
            submit={reschedule}
            onSuccess={onChanged}
          />
          <ReceptionCancelControl
            appointment={appointment}
            patientName={patient.fullName}
            doctorName={doctorName}
            submit={cancel}
            onSuccess={onChanged}
          />
        </div>
      )}
    </article>
  );
}

export default function ReceptionPatientLookup(props: Props) {
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const [detailError, setDetailError] = useState("");
  const [detailRevision, setDetailRevision] = useState(0);
  const [patientAppointments, setPatientAppointments] = useState<Appointment[]>([]);
  const [appointmentState, setAppointmentState] = useState<LoadState>("idle");
  const [appointmentError, setAppointmentError] = useState("");
  const [appointmentRevision, setAppointmentRevision] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const resultActionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const detailRequestRevisionRef = useRef(0);
  const appointmentRequestRevisionRef = useRef(0);

  const duplicateIds = useMemo(
    () => duplicatePatientNameIds(props.searchResults),
    [props.searchResults],
  );
  const { upcoming, history } = useMemo(
    () => splitPatientAppointments(patientAppointments),
    [patientAppointments],
  );

  useEffect(() => {
    const revision = ++detailRequestRevisionRef.current;
    if (!props.selectedPatientId) {
      setSelectedPatient(null);
      setDetailState("idle");
      return;
    }

    setSelectedPatient(null);
    setDetailState("loading");
    setDetailError("");
    void request<Patient>(`/patients/${props.selectedPatientId}`, props.token)
      .then(patient => {
        if (revision !== detailRequestRevisionRef.current) return;
        setSelectedPatient(patient);
        setDetailState("success");
      })
      .catch(cause => {
        if (revision !== detailRequestRevisionRef.current) return;
        setDetailError(toBookingIssue(cause).detail);
        setDetailState("error");
      });
  }, [detailRevision, props.selectedPatientId, props.token]);

  useEffect(() => {
    const revision = ++appointmentRequestRevisionRef.current;
    if (!props.selectedPatientId) {
      setPatientAppointments([]);
      setAppointmentState("idle");
      return;
    }
    const from = new Date();
    from.setMonth(from.getMonth() - HISTORY_MONTHS);
    const to = new Date();
    to.setMonth(to.getMonth() + UPCOMING_MONTHS);
    setAppointmentState("loading");
    setAppointmentError("");

    // The current API has no per-patient history endpoint. Use its bounded receptionist queue,
    // then filter locally without changing the backend contract or exposing medical records.
    void request<Appointment[]>(
      `/appointments/queue?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`,
      props.token,
    ).then(items => {
      if (revision !== appointmentRequestRevisionRef.current) return;
      setPatientAppointments(items.filter(item => item.patientId === props.selectedPatientId));
      setAppointmentState("success");
    }).catch(cause => {
      if (revision !== appointmentRequestRevisionRef.current) return;
      setAppointmentError(toBookingIssue(cause).detail);
      setAppointmentState("error");
    });
  }, [appointmentRevision, props.selectedPatientId, props.token]);

  useEffect(() => {
    const refresh = () => setAppointmentRevision(value => value + 1);
    window.addEventListener("reception-appointments-changed", refresh);
    return () => window.removeEventListener("reception-appointments-changed", refresh);
  }, []);

  async function submitSearch(event: FormEvent) {
    event.preventDefault();
    await props.onSearch();
  }

  function handleResultKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const direction = event.key === "ArrowDown" ? 1 : -1;
    const next = (index + direction + props.searchResults.length) % props.searchResults.length;
    resultActionRefs.current[next]?.focus();
  }

  function refreshPatientDetail() {
    setDetailRevision(value => value + 1);
  }

  function handleAppointmentChanged() {
    setAppointmentRevision(value => value + 1);
    window.dispatchEvent(new Event("reception-appointments-changed"));
  }

  const showResults = props.searchAttempted || props.searchError || props.searchLoading;
  const hasSelection = Boolean(props.selectedPatientId);

  return (
    <section className="reception-patient-lookup" aria-labelledby="reception-patient-lookup-title">
      <header className="reception-patient-lookup-header">
        <div>
          <h2 id="reception-patient-lookup-title">Tra cứu bệnh nhân</h2>
          <p>Xác minh đúng người bằng họ tên, số điện thoại và ngày sinh trước khi hỗ trợ lịch khám.</p>
        </div>
        <button type="button" className="reception-button-secondary" onClick={() => props.onOpenHotline()}>
          <UserPlus aria-hidden="true" />
          Tạo hồ sơ qua điện thoại
        </button>
      </header>

      <form className="reception-patient-search" role="search" onSubmit={submitSearch}>
        <label htmlFor="reception-patient-search">Họ tên hoặc số điện thoại</label>
        <div className="reception-patient-search-control">
          <Search aria-hidden="true" />
          <input
            ref={searchInputRef}
            id="reception-patient-search"
            value={props.query}
            onChange={event => props.onQueryChange(event.target.value)}
            placeholder="Ví dụ: Nguyễn An hoặc 09xxxxxxxx"
            autoComplete="off"
            aria-describedby="reception-patient-search-help"
          />
          {props.query && (
            <button type="button" aria-label="Xóa nội dung tìm kiếm" onClick={() => {
              props.onClearSearch();
              window.setTimeout(() => searchInputRef.current?.focus(), 0);
            }}><X aria-hidden="true" /></button>
          )}
          <button type="submit" disabled={props.searchLoading || props.query.trim().length < 2}>
            {props.searchLoading ? "Đang tìm" : "Tìm bệnh nhân"}
          </button>
        </div>
        <small id="reception-patient-search-help">Hệ thống hiện hỗ trợ tìm theo họ tên hoặc số điện thoại, tối thiểu 2 ký tự.</small>
      </form>

      {!showResults && (
        <div className="reception-patient-idle">
          <ShieldCheck aria-hidden="true" />
          <div><strong>Bắt đầu bằng thông tin người bệnh cung cấp</strong><p>Không có danh sách ngẫu nhiên. Chỉ hồ sơ khớp truy vấn mới được hiển thị.</p></div>
        </div>
      )}

      {props.searchError && (
        <div className="reception-patient-local-error" role="alert">
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Chưa thể cập nhật kết quả tìm kiếm</strong>
            <p>{props.searchError}{props.searchResults.length ? " Kết quả gần nhất vẫn được giữ lại để đối chiếu." : ""}</p>
          </div>
          <button type="button" onClick={() => void props.onSearch()}><RefreshCw aria-hidden="true" />Thử lại</button>
        </div>
      )}

      {props.searchLoading && (
        <div className="reception-patient-loading" role="status" aria-live="polite">
          <span aria-hidden="true" />
          Đang tìm hồ sơ phù hợp...
        </div>
      )}

      {showResults && !props.searchLoading && !props.searchError && props.searchResults.length === 0 && (
        <div className="reception-patient-empty">
          <Search aria-hidden="true" />
          <div>
            <strong>Không có hồ sơ khớp “{props.lastSearchTerm}”</strong>
            <p>Kiểm tra lại cách viết họ tên hoặc thử số điện thoại. Kết quả này chưa đủ để khẳng định bệnh nhân chưa có hồ sơ.</p>
          </div>
          <div>
            <button type="button" className="reception-button-secondary" onClick={() => {
              props.onClearSearch();
              window.setTimeout(() => searchInputRef.current?.focus(), 0);
            }}>Xóa tìm kiếm</button>
            <button type="button" className="reception-button-primary" onClick={() => props.onOpenHotline()}><UserPlus aria-hidden="true" />Tạo hồ sơ qua điện thoại</button>
          </div>
        </div>
      )}

      {props.searchResults.length > 0 && (
        <div className={`reception-patient-workspace ${hasSelection ? "has-selection" : ""}`}>
          <section className="reception-patient-results-panel" aria-labelledby="reception-patient-results-title">
            <header>
              <div><h3 id="reception-patient-results-title">Kết quả tìm thấy</h3><p>{props.searchResults.length} hồ sơ theo truy vấn “{props.lastSearchTerm}”</p></div>
            </header>
            {duplicateIds.size > 0 && (
              <div className="reception-patient-duplicate" role="note">
                <AlertTriangle aria-hidden="true" />
                <p>Có hồ sơ trùng họ tên. Hãy đối chiếu số điện thoại và ngày sinh, không chọn theo thứ tự danh sách.</p>
              </div>
            )}
            <div className="reception-patient-result-list" role="list" aria-live="polite">
              {props.searchResults.map((patient, index) => {
                const nextAppointment = nextPatientAppointment(props.appointments, patient.id);
                const duplicate = duplicateIds.has(patient.id);
                return (
                  <article key={patient.id} className={`reception-patient-result ${patient.id === props.selectedPatientId ? "is-selected" : ""}`} role="listitem">
                    <div className="reception-patient-result-identity">
                      <span aria-hidden="true">{patient.fullName.slice(0, 1).toUpperCase()}</span>
                      <div>
                        <strong>{patient.fullName}</strong>
                        <small>Mã hồ sơ {patientRecordCode(patient.id)}</small>
                      </div>
                    </div>
                    <dl>
                      <div><dt>Số điện thoại</dt><dd>{maskPatientPhone(patient.phone)}</dd></div>
                      <div><dt>Ngày sinh</dt><dd>{formatDate(patient.dob)}</dd></div>
                    </dl>
                    <PatientStatusBadge patient={patient} />
                    {duplicate && <p className="reception-patient-duplicate-label"><AlertTriangle aria-hidden="true" />Trùng họ tên, cần xác minh thêm</p>}
                    <p className="reception-patient-next">
                      {nextAppointment
                        ? <>Lịch gần nhất: <time dateTime={nextAppointment.startAt}>{formatAppointmentDateTime(nextAppointment.startAt)}</time></>
                        : "Chưa có lịch sắp tới trong phạm vi điều phối"}
                    </p>
                    <button
                      ref={element => { resultActionRefs.current[index] = element; }}
                      type="button"
                      className="reception-patient-view"
                      aria-pressed={patient.id === props.selectedPatientId}
                      onKeyDown={event => handleResultKeyDown(event, index)}
                      onClick={() => props.onSelectPatient(patient.id)}
                    >
                      Xem thông tin
                    </button>
                  </article>
                );
              })}
            </div>
          </section>

          {hasSelection && (
            <section className="reception-patient-detail" aria-label="Thông tin bệnh nhân đã chọn">
              {detailState === "loading" && (
                <div className="reception-patient-detail-loading" role="status" aria-live="polite">
                  <span /><span /><span />
                  <p>Đang tải thông tin xác minh...</p>
                </div>
              )}
              {detailState === "error" && (
                <div className="reception-patient-detail-error" role="alert">
                  <AlertTriangle aria-hidden="true" />
                  <div><strong>Không thể tải thông tin bệnh nhân</strong><p>{detailError}</p></div>
                  <button type="button" onClick={refreshPatientDetail}><RefreshCw aria-hidden="true" />Thử lại</button>
                </div>
              )}
              {selectedPatient && detailState === "success" && (
                <>
                  <header className="reception-patient-identity-summary">
                    <span aria-hidden="true">{selectedPatient.fullName.slice(0, 1).toUpperCase()}</span>
                    <div>
                      <h3 id="reception-patient-detail-title">{selectedPatient.fullName}</h3>
                      <p>Mã hồ sơ {patientRecordCode(selectedPatient.id)}</p>
                      <PatientStatusBadge patient={selectedPatient} />
                    </div>
                    <div className="reception-patient-identity-actions">
                      <button type="button" className="reception-button-secondary" onClick={() => props.onSelectPatient("")}><UserRound aria-hidden="true" />Đổi bệnh nhân</button>
                      <button type="button" className="reception-button-primary" onClick={() => props.onOpenHotline(selectedPatient)}><CalendarPlus aria-hidden="true" />Tạo lịch mới</button>
                    </div>
                  </header>

                  <section className="reception-patient-administrative" aria-labelledby="reception-patient-administrative-title">
                    <div className="reception-patient-section-heading">
                      <div><h4 id="reception-patient-administrative-title">Thông tin hành chính</h4><p>Chỉ đọc. Lễ tân hiện không có quyền chỉnh sửa hồ sơ này.</p></div>
                      <button type="button" className="reception-patient-support" onClick={() => props.onOpenSupport(selectedPatient)}><Headphones aria-hidden="true" />Liên hệ hỗ trợ</button>
                    </div>
                    <dl>
                      <div><dt>Họ và tên</dt><dd>{selectedPatient.fullName}</dd></div>
                      <div><dt>Ngày sinh</dt><dd>{formatDate(selectedPatient.dob)}</dd></div>
                      <div><dt>Số điện thoại</dt><dd>{selectedPatient.phone || "Chưa khai báo"}</dd></div>
                      <div><dt>Trạng thái hồ sơ</dt><dd>{selectedPatient.accountLinked === true ? "Đã liên kết tài khoản" : selectedPatient.accountLinked === false ? "Tiếp nhận qua điện thoại" : "Chưa có dữ liệu"}</dd></div>
                    </dl>
                    <p className="reception-patient-privacy"><ShieldCheck aria-hidden="true" />Màn hình này không hiển thị chẩn đoán, ảnh da, đơn thuốc, tiền sử bệnh hoặc ghi chú chuyên môn.</p>
                  </section>

                  <div className="reception-patient-appointment-sections">
                    <section aria-labelledby="reception-patient-upcoming-title">
                      <div className="reception-patient-section-heading">
                        <div><h4 id="reception-patient-upcoming-title">Lịch đang hoạt động và sắp tới</h4><p>Ưu tiên các lịch chưa kết thúc quy trình tiếp nhận.</p></div>
                        <span>{upcoming.length} lịch</span>
                      </div>
                      {appointmentState === "loading" ? (
                        <div className="reception-patient-appointment-state" role="status">Đang tải lịch sắp tới...</div>
                      ) : appointmentState === "error" ? (
                        <div className="reception-patient-appointment-error" role="alert"><AlertTriangle aria-hidden="true" /><div><strong>Không thể tải lịch sắp tới</strong><p>{appointmentError}</p></div><button type="button" onClick={() => setAppointmentRevision(value => value + 1)}>Thử lại</button></div>
                      ) : upcoming.length ? (
                        <div className="reception-patient-appointment-list">
                          {upcoming.map(appointment => (
                            <AppointmentRow
                              key={appointment.id}
                              appointment={appointment}
                              patient={selectedPatient}
                              doctorName={props.doctorName(appointment)}
                              token={props.token}
                              onChanged={handleAppointmentChanged}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="reception-patient-appointment-empty"><CalendarPlus aria-hidden="true" /><p>Chưa có lịch đang hoạt động trong phạm vi tra cứu.</p><button type="button" onClick={() => props.onOpenHotline(selectedPatient)}>Tạo lịch mới</button></div>
                      )}
                    </section>

                    <section aria-labelledby="reception-patient-history-title">
                      <div className="reception-patient-section-heading">
                        <div><h4 id="reception-patient-history-title">Lịch sử lịch hẹn</h4><p>Gần nhất trước, gồm lịch hoàn tất, đã hủy hoặc vắng mặt.</p></div>
                        <span>{history.length} lịch</span>
                      </div>
                      {appointmentState === "loading" ? (
                        <div className="reception-patient-appointment-state" role="status">Đang tải lịch sử...</div>
                      ) : appointmentState === "error" ? (
                        <div className="reception-patient-appointment-error" role="alert"><AlertTriangle aria-hidden="true" /><div><strong>Không thể tải lịch sử</strong><p>{appointmentError}</p></div><button type="button" onClick={() => setAppointmentRevision(value => value + 1)}>Thử lại</button></div>
                      ) : history.length ? (
                        <div className="reception-patient-history-list">
                          {history.map(appointment => (
                            <article key={appointment.id}>
                              <div><time dateTime={appointment.startAt}>{formatAppointmentDateTime(appointment.startAt)}</time><strong>BS. {props.doctorName(appointment)}</strong>{appointment.reason && <p>{appointment.reason}</p>}</div>
                              <AppointmentStatusBadge status={appointment.status} />
                            </article>
                          ))}
                        </div>
                      ) : (
                        <div className="reception-patient-appointment-empty"><History aria-hidden="true" /><p>Chưa có lịch sử trong phạm vi dữ liệu đang tải.</p></div>
                      )}
                    </section>
                  </div>
                  <p className="reception-patient-range-note">Phạm vi hiển thị: {HISTORY_MONTHS} tháng gần đây và {UPCOMING_MONTHS} tháng tới.</p>
                </>
              )}
            </section>
          )}
        </div>
      )}
    </section>
  );
}
