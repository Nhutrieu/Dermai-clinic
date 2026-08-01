import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Headphones,
  PhoneCall,
  RefreshCcw,
  Search,
  UserRound,
  X,
} from "lucide-react";
import type { RealtimeConnectionState } from "../../core/realtime";
import type { Appointment, Patient, ReminderAction, ReminderItem } from "../../core/types";
import {
  buildReceptionSummary,
  getAttentionAppointments,
  getOperationalAppointments,
  getReceptionStatus,
  isOverdueForNoShow,
} from "./receptionDashboardModel";

type ScheduleFilter = "ALL" | "ATTENTION" | "CONFIRMED" | "IN_PROGRESS" | "COMPLETED";

type Props = {
  appointments: Appointment[];
  reminders: ReminderItem[];
  searchResults: Patient[];
  selectedPatientId: string;
  query: string;
  queueLoading: boolean;
  queueError: string;
  reminderLoading: boolean;
  reminderError: string;
  searchLoading: boolean;
  searchAttempted: boolean;
  searchError: string;
  notice: string;
  noticeError: boolean;
  busyAppointmentId: string;
  realtimeState: RealtimeConnectionState;
  lastSyncedAt: Date | null;
  liveRevision: number;
  patientName: (appointment: Appointment) => string;
  doctorName: (appointment: Appointment) => string;
  onQueryChange: (value: string) => void;
  onSearch: () => Promise<void>;
  onClearSearch: () => void;
  onSelectPatient: (patientId: string) => void;
  onOpenSupport: (patient: Patient) => void;
  onOpenHotline: () => void;
  onOpenRequests: () => void;
  onOpenAccepted: () => void;
  onConfirm: (appointmentId: string) => Promise<void>;
  onNoShow: (appointmentId: string) => Promise<void>;
  onRemind: (appointmentId: string, action: ReminderAction["actionType"]) => Promise<void>;
  onRetryQueue: () => Promise<void>;
  onRetryReminders: () => Promise<void>;
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}

function formatLongDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}

function ReceptionStatusBadge({ status }: { status: string }) {
  const presentation = getReceptionStatus(status);
  return <span className={`reception-status reception-status-${presentation.tone}`}>{presentation.label}</span>;
}

function ReceptionConfirmDialog({
  appointment,
  patient,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  appointment: Appointment;
  patient: string;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    confirmRef.current?.focus();
    return () => returnFocusRef.current?.focus();
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(
      dialogRef.current.querySelectorAll<HTMLElement>("button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex='-1'])"),
    );
    if (!focusable.length) return;
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

  return createPortal(
    <div className="reception-dialog-backdrop" onMouseDown={event => {
      if (event.target === event.currentTarget && !busy) onClose();
    }}>
      <div
        ref={dialogRef}
        className="reception-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reception-no-show-title"
        aria-describedby="reception-no-show-description"
        onKeyDown={handleKeyDown}
      >
        <header>
          <div>
            <h2 id="reception-no-show-title">Ghi nhận bệnh nhân vắng mặt?</h2>
            <p id="reception-no-show-description">
              Thao tác áp dụng cho {patient}, lịch {formatTime(appointment.startAt)} ngày {formatShortDate(appointment.startAt)}.
            </p>
          </div>
          <button type="button" aria-label="Đóng hộp xác nhận" disabled={busy} onClick={onClose}><X /></button>
        </header>
        <div className="reception-dialog-note">
          Chỉ xác nhận sau khi đã kiểm tra bệnh nhân chưa đến và lịch đã quá giờ ít nhất 30 phút.
        </div>
        {error && <div className="reception-dialog-error" role="alert">{error}</div>}
        <footer>
          <button type="button" className="reception-button-secondary" disabled={busy} onClick={onClose}>Quay lại</button>
          <button
            ref={confirmRef}
            type="button"
            className="reception-button-danger"
            disabled={busy}
            onClick={() => void onConfirm().then(onClose).catch(() => undefined)}
          >
            {busy ? "Đang cập nhật" : "Xác nhận vắng mặt"}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}

function ReceptionAppointmentRow({
  appointment,
  patient,
  doctor,
  busy,
  onOpenRequests,
  onConfirm,
  onAskNoShow,
}: {
  appointment: Appointment;
  patient: string;
  doctor: string;
  busy: boolean;
  onOpenRequests: () => void;
  onConfirm: () => Promise<void>;
  onAskNoShow: () => void;
}) {
  const overdue = isOverdueForNoShow(appointment);
  let action: React.ReactNode = null;
  if (appointment.status === "PENDING") {
    action = <button type="button" className="reception-row-action" onClick={onOpenRequests}>Xử lý yêu cầu</button>;
  } else if (appointment.status === "ASSIGNED") {
    action = <button type="button" className="reception-row-action" disabled={busy} onClick={() => void onConfirm()}>{busy ? "Đang xác nhận" : "Xác nhận lịch"}</button>;
  } else if (overdue) {
    action = <button type="button" className="reception-row-action reception-row-action-warning" disabled={busy} onClick={onAskNoShow}>Ghi nhận vắng</button>;
  }

  return (
    <article className="reception-appointment-row" role="listitem" aria-label={`${formatTime(appointment.startAt)}, ${patient}, ${doctor}`}>
      <time dateTime={appointment.startAt} className="reception-appointment-time">
        <strong>{formatTime(appointment.startAt)}</strong>
        <span>{formatShortDate(appointment.startAt)}</span>
      </time>
      <div className="reception-appointment-patient">
        <strong>{patient}</strong>
        <span>{appointment.reason || "Chưa ghi lý do khám"}</span>
      </div>
      <div className="reception-appointment-doctor">
        <span>Bác sĩ phụ trách</span>
        <strong>{doctor}</strong>
      </div>
      <ReceptionStatusBadge status={appointment.status} />
      <div className="reception-appointment-action">{action}</div>
    </article>
  );
}

export default function ReceptionDashboard(props: Props) {
  const [scheduleFilter, setScheduleFilter] = useState<ScheduleFilter>("ALL");
  const [noShowAppointment, setNoShowAppointment] = useState<Appointment | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const summary = useMemo(() => buildReceptionSummary(props.appointments), [props.appointments]);
  const todayAppointments = useMemo(() => getOperationalAppointments(props.appointments), [props.appointments]);
  const attentionAppointments = useMemo(
    () => getAttentionAppointments(props.appointments, props.reminders),
    [props.appointments, props.reminders],
  );
  const attentionIds = useMemo(() => new Set(attentionAppointments.map(item => item.id)), [attentionAppointments]);
  const incomingAttentionCount = attentionAppointments.filter(item => ["PENDING", "ASSIGNED"].includes(item.status)).length;
  const selectedPatient = props.searchResults.find(patient => patient.id === props.selectedPatientId);
  const selectedAppointments = selectedPatient
    ? props.appointments
      .filter(item => item.patientId === selectedPatient.id)
      .sort((left, right) => new Date(right.startAt).getTime() - new Date(left.startAt).getTime())
    : [];
  const flowAppointments = todayAppointments
    .filter(item => ["CONFIRMED", "IN_PROGRESS", "COMPLETED", "FOLLOW_UP_REQUIRED", "NO_SHOW"].includes(item.status))
    .slice(0, 6);

  const filteredToday = todayAppointments.filter(item => {
    if (scheduleFilter === "ALL") return true;
    if (scheduleFilter === "ATTENTION") return attentionIds.has(item.id);
    if (scheduleFilter === "COMPLETED") return ["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(item.status);
    return item.status === scheduleFilter;
  });

  const filterOptions: { value: ScheduleFilter; label: string; count: number }[] = [
    { value: "ALL", label: "Tất cả", count: todayAppointments.length },
    { value: "ATTENTION", label: "Cần xử lý", count: todayAppointments.filter(item => attentionIds.has(item.id)).length },
    { value: "CONFIRMED", label: "Đã xác nhận", count: summary.confirmed },
    { value: "IN_PROGRESS", label: "Đang khám", count: summary.inProgress },
    { value: "COMPLETED", label: "Hoàn tất", count: summary.completed },
  ];

  async function submitSearch(event: FormEvent) {
    event.preventDefault();
    await props.onSearch();
  }

  const connectionCopy = props.realtimeState === "connected"
    ? "Dữ liệu đang cập nhật trực tiếp"
    : "Đang nối lại realtime. Hệ thống vẫn tự đồng bộ định kỳ.";

  return (
    <div className="reception-dashboard">
      <section className="reception-command" aria-labelledby="reception-command-title">
        <div className="reception-command-copy">
          <h2 id="reception-command-title">Điều phối hôm nay</h2>
          <p>Ưu tiên lịch sắp đến, yêu cầu chưa xác nhận và các trường hợp cần liên hệ.</p>
        </div>
        <div className="reception-command-actions" aria-label="Hành động nhanh">
          <button type="button" className="reception-button-secondary" onClick={props.onOpenRequests}>
            <CalendarClock />
            <span>Yêu cầu mới</span>
            {incomingAttentionCount > 0 && (
              <b aria-label={`${incomingAttentionCount} yêu cầu mới`}>
                {incomingAttentionCount}
              </b>
            )}
          </button>
          <button type="button" className="reception-button-primary" onClick={props.onOpenHotline}>
            <PhoneCall />
            Đặt lịch hotline
          </button>
        </div>
        <form className="reception-search" role="search" onSubmit={submitSearch}>
          <label htmlFor="reception-patient-search">Tìm bệnh nhân</label>
          <div>
            <Search aria-hidden="true" />
            <input
              ref={searchInputRef}
              id="reception-patient-search"
              value={props.query}
              onChange={event => props.onQueryChange(event.target.value)}
              placeholder="Nhập họ tên hoặc số điện thoại"
              autoComplete="off"
              aria-describedby="reception-search-help"
            />
            {props.query && (
              <button type="button" className="reception-search-clear" aria-label="Xóa nội dung tìm kiếm" onClick={props.onClearSearch}><X /></button>
            )}
            <button type="submit" disabled={props.searchLoading || props.query.trim().length < 2}>
              {props.searchLoading ? "Đang tìm" : "Tìm bệnh nhân"}
            </button>
          </div>
          <small id="reception-search-help">Tìm theo dữ liệu hệ thống đang hỗ trợ: họ tên hoặc số điện thoại.</small>
        </form>
      </section>

      <div className={`reception-sync reception-sync-${props.realtimeState}`} role="status" aria-live="polite">
        <span>{connectionCopy}</span>
        {props.lastSyncedAt && <small>Lần đồng bộ gần nhất: {formatTime(props.lastSyncedAt.toISOString())}</small>}
      </div>

      {props.notice && <div className={`reception-notice ${props.noticeError ? "is-error" : ""}`} role={props.noticeError ? "alert" : "status"} aria-live={props.noticeError ? "assertive" : "polite"}>{props.notice}</div>}

      {(props.searchAttempted || props.searchError) && (
        <section className="reception-search-results" aria-labelledby="reception-search-results-title">
          <header>
            <div>
              <h2 id="reception-search-results-title">Kết quả tra cứu</h2>
              <p>Chỉ hiển thị thông tin cần thiết để xác minh và hỗ trợ lịch khám.</p>
            </div>
            <button type="button" aria-label="Đóng kết quả tra cứu" onClick={props.onClearSearch}><X /></button>
          </header>
          {props.searchError ? (
            <div className="reception-inline-error" role="alert">
              <AlertTriangle />
              <div><strong>Không thể tìm bệnh nhân</strong><p>{props.searchError}</p></div>
              <button type="button" onClick={() => void props.onSearch()}>Thử lại</button>
            </div>
          ) : props.searchLoading ? (
            <div className="reception-search-loading" role="status">Đang tìm trong danh sách bệnh nhân...</div>
          ) : props.searchResults.length === 0 ? (
            <div className="reception-empty reception-empty-compact">
              <Search />
              <div><strong>Không tìm thấy bệnh nhân phù hợp</strong><p>Kiểm tra lại họ tên, số điện thoại hoặc tạo hồ sơ trong luồng hotline.</p></div>
              <button type="button" className="reception-button-secondary" onClick={props.onOpenHotline}>Mở đặt lịch hotline</button>
            </div>
          ) : (
            <div className="reception-patient-search-layout">
              <div className="reception-patient-results" aria-label="Danh sách bệnh nhân tìm thấy">
                {props.searchResults.map(patient => (
                  <button
                    type="button"
                    key={patient.id}
                    className={patient.id === props.selectedPatientId ? "is-selected" : ""}
                    aria-pressed={patient.id === props.selectedPatientId}
                    onClick={() => props.onSelectPatient(patient.id)}
                  >
                    <span>{patient.fullName.slice(0, 1).toUpperCase()}</span>
                    <div><strong>{patient.fullName}</strong><small>{patient.phone || "Chưa có số điện thoại"}</small></div>
                    <ChevronRight />
                  </button>
                ))}
              </div>
              {selectedPatient ? (
                <article className="reception-patient-summary">
                  <header>
                    <div><h3>{selectedPatient.fullName}</h3><p>{selectedPatient.phone || "Chưa có số điện thoại"}</p></div>
                    <UserRound />
                  </header>
                  <dl>
                    <div><dt>Ngày sinh</dt><dd>{selectedPatient.dob ? new Date(selectedPatient.dob).toLocaleDateString("vi-VN") : "Chưa khai báo"}</dd></div>
                    <div><dt>Lịch trong phạm vi điều phối</dt><dd>{selectedAppointments.length}</dd></div>
                  </dl>
                  <div className="reception-patient-appointments">
                    <strong>Lịch gần nhất</strong>
                    {selectedAppointments.length ? selectedAppointments.slice(0, 2).map(item => (
                      <p key={item.id}><time dateTime={item.startAt}>{formatTime(item.startAt)} ngày {formatShortDate(item.startAt)}</time><ReceptionStatusBadge status={item.status} /></p>
                    )) : <p>Chưa có lịch trong phạm vi đang tải.</p>}
                  </div>
                  <div className="reception-patient-actions">
                    <button type="button" className="reception-button-secondary" onClick={() => props.onOpenSupport(selectedPatient)}><Headphones />Mở hỗ trợ</button>
                    <button type="button" className="reception-button-primary" onClick={props.onOpenHotline}><PhoneCall />Đặt lịch hộ</button>
                  </div>
                </article>
              ) : (
                <div className="reception-patient-placeholder">Chọn một bệnh nhân để xem lịch gần nhất và mở hỗ trợ.</div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="reception-summary" aria-labelledby="reception-summary-title">
        <header><h2 id="reception-summary-title">Tình hình hôm nay</h2><span>{formatLongDate(new Date().toISOString())}</span></header>
        <dl>
          <div><dt>Tổng lịch</dt><dd>{summary.total}</dd></div>
          <div><dt>Chờ xử lý</dt><dd>{summary.pending}</dd></div>
          <div><dt>Đã xác nhận</dt><dd>{summary.confirmed}</dd></div>
          <div><dt>Đang khám</dt><dd>{summary.inProgress}</dd></div>
          <div><dt>Hoàn tất</dt><dd>{summary.completed}</dd></div>
          <div><dt>Hủy hoặc vắng</dt><dd>{summary.closed}</dd></div>
        </dl>
      </section>

      <div className="reception-dashboard-grid">
        <section className={`reception-schedule ${props.liveRevision ? "has-live-update" : ""}`} aria-labelledby="reception-schedule-title">
          <header className="reception-section-heading">
            <div><h2 id="reception-schedule-title">Lịch hẹn hôm nay</h2><p>{todayAppointments.length ? `${todayAppointments.length} lịch trong ngày` : "Chưa có lịch trong ngày"}</p></div>
            <button type="button" className="reception-text-action" onClick={props.onOpenAccepted}>Xem toàn bộ lịch <ChevronRight /></button>
          </header>
          <div className="reception-schedule-filters" aria-label="Lọc lịch hẹn hôm nay">
            {filterOptions.map(option => (
              <button
                type="button"
                key={option.value}
                className={scheduleFilter === option.value ? "is-active" : ""}
                aria-pressed={scheduleFilter === option.value}
                onClick={() => setScheduleFilter(option.value)}
              >
                {option.label}<span>{option.count}</span>
              </button>
            ))}
          </div>
          {props.queueError && !props.appointments.length ? (
            <div className="reception-inline-error" role="alert">
              <AlertTriangle />
              <div><strong>Không thể tải lịch hôm nay</strong><p>{props.queueError}</p></div>
              <button type="button" onClick={() => void props.onRetryQueue()}><RefreshCcw />Tải lại</button>
            </div>
          ) : props.queueLoading && !props.appointments.length ? (
            <div className="reception-skeleton-list" role="status" aria-label="Đang tải lịch hôm nay">
              {[0, 1, 2].map(item => <span key={item} aria-hidden="true" />)}
            </div>
          ) : filteredToday.length === 0 ? (
            <div className="reception-empty">
              <CalendarClock />
              <div><strong>{todayAppointments.length ? "Không có lịch ở trạng thái này" : "Hôm nay chưa có lịch hẹn"}</strong><p>{todayAppointments.length ? "Chọn bộ lọc khác để xem các lịch còn lại." : "Lịch mới sẽ tự xuất hiện khi hệ thống ghi nhận."}</p></div>
            </div>
          ) : (
            <div className="reception-appointment-list" role="list" aria-live="polite">
              {filteredToday.map(item => (
                <ReceptionAppointmentRow
                  key={item.id}
                  appointment={item}
                  patient={props.patientName(item)}
                  doctor={props.doctorName(item)}
                  busy={props.busyAppointmentId === item.id}
                  onOpenRequests={props.onOpenRequests}
                  onConfirm={() => props.onConfirm(item.id)}
                  onAskNoShow={() => setNoShowAppointment(item)}
                />
              ))}
            </div>
          )}
          {props.queueError && props.appointments.length > 0 && (
            <div className="reception-stale-warning" role="status">
              <AlertTriangle />
              <span>Không thể làm mới dữ liệu. Danh sách gần nhất vẫn được giữ lại.</span>
              <button type="button" onClick={() => void props.onRetryQueue()}>Thử lại</button>
            </div>
          )}
        </section>

        <aside className="reception-operations" aria-label="Việc cần xử lý và tiến trình khám">
          {attentionAppointments.length > 0 && (
            <section className="reception-attention" aria-labelledby="reception-attention-title">
              <header><div><h2 id="reception-attention-title">Cần xử lý</h2><p>{attentionAppointments.length} lịch cần lễ tân kiểm tra</p></div><AlertTriangle /></header>
              <div>
                {attentionAppointments.slice(0, 5).map(item => {
                  const isUnreachable = props.reminders.some(reminder => reminder.appointment.id === item.id && reminder.latestAction?.actionType === "UNREACHABLE");
                  const copy = item.status === "PENDING"
                    ? "Chưa phân công bác sĩ"
                    : item.status === "ASSIGNED"
                      ? "Chờ lễ tân xác nhận"
                      : isUnreachable
                        ? "Cần liên hệ lại bệnh nhân"
                        : "Đã quá giờ khám 30 phút";
                  return (
                    <article key={item.id}>
                      <time dateTime={item.startAt}>{formatTime(item.startAt)}<span>{formatShortDate(item.startAt)}</span></time>
                      <div><strong>{props.patientName(item)}</strong><p>{copy}</p></div>
                      {item.status === "PENDING" ? (
                        <button type="button" aria-label={`Xử lý yêu cầu của ${props.patientName(item)}`} onClick={props.onOpenRequests}><ChevronRight /></button>
                      ) : item.status === "ASSIGNED" ? (
                        <button type="button" aria-label={`Xác nhận lịch của ${props.patientName(item)}`} disabled={props.busyAppointmentId === item.id} onClick={() => void props.onConfirm(item.id)}><CheckCircle2 /></button>
                      ) : isOverdueForNoShow(item) ? (
                        <button type="button" aria-label={`Ghi nhận ${props.patientName(item)} vắng mặt`} onClick={() => setNoShowAppointment(item)}><ChevronRight /></button>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          <section className="reception-flow" aria-labelledby="reception-flow-title">
            <header><div><h2 id="reception-flow-title">Tiến trình khám</h2><p>Trạng thái lịch thật trong hôm nay</p></div><Clock3 /></header>
            {flowAppointments.length ? (
              <ol>
                {flowAppointments.map(item => (
                  <li key={item.id}>
                    <time dateTime={item.startAt}>{formatTime(item.startAt)}</time>
                    <div><strong>{props.patientName(item)}</strong><span>{props.doctorName(item)}</span></div>
                    <ReceptionStatusBadge status={item.status} />
                  </li>
                ))}
              </ol>
            ) : <p className="reception-flow-empty">Chưa có lịch đã xác nhận hoặc đang khám hôm nay.</p>}
          </section>
        </aside>
      </div>

      {(props.reminderLoading || props.reminderError || props.reminders.length > 0) && (
        <section className="reception-reminders" aria-labelledby="reception-reminders-title">
          <header className="reception-section-heading">
            <div><h2 id="reception-reminders-title">Nhắc lịch sắp tới</h2><p>Lịch đã xác nhận trong hôm nay và ngày mai</p></div>
            <span>{props.reminders.length} lịch</span>
          </header>
          {props.reminderError ? (
            <div className="reception-inline-error" role="alert">
              <AlertTriangle />
              <div><strong>Không thể tải danh sách nhắc lịch</strong><p>{props.reminderError}</p></div>
              <button type="button" onClick={() => void props.onRetryReminders()}>Thử lại</button>
            </div>
          ) : props.reminderLoading ? (
            <div className="reception-search-loading" role="status">Đang tải lịch cần nhắc...</div>
          ) : (
            <div className="reception-reminder-list">
              {props.reminders.map(reminder => {
                const item = reminder.appointment;
                const action = reminder.latestAction?.actionType;
                const actionLabel = action === "CALLED" ? "Đã gọi" : action === "RESENT" ? "Đã gửi nhắc" : action === "UNREACHABLE" ? "Không liên lạc được" : "Chưa nhắc";
                return (
                  <article key={item.id}>
                    <time dateTime={item.startAt}><strong>{formatTime(item.startAt)}</strong><span>{formatShortDate(item.startAt)}</span></time>
                    <div className="reception-reminder-person"><strong>{props.patientName(item)}</strong><span>{props.doctorName(item)}</span></div>
                    <span className="reception-reminder-state">{actionLabel}</span>
                    <div className="reception-reminder-actions">
                      <button type="button" disabled={props.busyAppointmentId === item.id} onClick={() => void props.onRemind(item.id, "RESENT")}>Gửi nhắc</button>
                      <button type="button" disabled={props.busyAppointmentId === item.id} onClick={() => void props.onRemind(item.id, "CALLED")}>Đã gọi</button>
                      <button type="button" disabled={props.busyAppointmentId === item.id} onClick={() => void props.onRemind(item.id, "UNREACHABLE")}>Không liên lạc được</button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}

      {noShowAppointment && (
        <ReceptionConfirmDialog
          appointment={noShowAppointment}
          patient={props.patientName(noShowAppointment)}
          busy={props.busyAppointmentId === noShowAppointment.id}
          error={props.noticeError ? props.notice : ""}
          onClose={() => setNoShowAppointment(null)}
          onConfirm={() => props.onNoShow(noShowAppointment.id)}
        />
      )}
    </div>
  );
}
