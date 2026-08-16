import { useEffect, useId, useMemo, useState } from "react";
import {
  Bell,
  CalendarDays,
  ChevronDown,
  Clock3,
  MessageCircle,
  MoreHorizontal,
  Phone,
  RefreshCcw,
  Search,
  Stethoscope,
  X,
} from "lucide-react";
import type { RealtimeConnectionState } from "../../core/realtime";
import { isStaleInProgressAppointment } from "../../core/appointmentPolicy";
import type {
  Appointment,
  Doctor,
  Patient,
  ReminderAction,
  ReminderItem,
} from "../../core/types";
import {
  ReceptionCancelControl,
  ReceptionRescheduleControl,
} from "./ReceptionAppointmentActions";

type Props = {
  token: string;
  appointments: Appointment[];
  reminders: ReminderItem[];
  patients: Patient[];
  doctors: Doctor[];
  queueLoading: boolean;
  queueRefreshing: boolean;
  queueError: string;
  reminderLoading: boolean;
  reminderError: string;
  patientLoadWarning: string;
  actionMessage: string;
  actionMessageError: boolean;
  busyAppointmentId: string;
  realtimeState: RealtimeConnectionState;
  lastUpdatedAt: Date | null;
  onRetryQueue: () => Promise<void>;
  onRetryReminders: () => Promise<void>;
  onRemind: (appointmentId: string, action: ReminderAction["actionType"]) => Promise<void>;
  onReschedule: (appointmentId: string, startAt: string) => Promise<Appointment>;
  onCancel: (appointmentId: string, reason: string) => Promise<Appointment>;
  onCheckIn: (appointmentId: string) => Promise<void>;
  onNoShow: (appointmentId: string) => Promise<void>;
  onComplete: (appointmentId: string) => Promise<void>;
  onOpenSupport: (patient: Patient) => void;
  onOpenRequests: () => void;
};

type StatusMeta = { label: string; className: string };

const ACCEPTED_PAGE_SIZE = 5;

const ACCEPTED_STATUSES = new Set([
  "CONFIRMED",
  "CHECKED_IN",
  "IN_PROGRESS",
  "COMPLETED",
  "FOLLOW_UP_REQUIRED",
  "NO_SHOW",
]);

const STATUS_OPTIONS = [
  ["CONFIRMED", "Đã xác nhận"],
  ["CHECKED_IN", "Đã đến phòng khám"],
  ["IN_PROGRESS", "Đang khám"],
  ["COMPLETED", "Hoàn tất"],
  ["FOLLOW_UP_REQUIRED", "Cần tái khám"],
  ["NO_SHOW", "Vắng mặt"],
] as const;

function statusMeta(status: string): StatusMeta {
  switch (status) {
    case "CONFIRMED": return { label: "Đã xác nhận", className: "is-confirmed" };
    case "CHECKED_IN": return { label: "Đã đến phòng khám", className: "is-checked-in" };
    case "IN_PROGRESS": return { label: "Đang khám", className: "is-in-progress" };
    case "COMPLETED": return { label: "Hoàn tất", className: "is-completed" };
    case "FOLLOW_UP_REQUIRED": return { label: "Cần tái khám", className: "is-follow-up" };
    case "NO_SHOW": return { label: "Vắng mặt", className: "is-no-show" };
    default: return { label: status, className: "is-neutral" };
  }
}

function clinicDateKey(value: string | Date) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(typeof value === "string" ? new Date(value) : value);
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatUpdatedAt(value: Date | null) {
  if (!value) return "Chưa đồng bộ";
  return `Cập nhật lúc ${new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(value)}`;
}

function ReminderSkeleton() {
  return (
    <div className="accepted-reminder-skeleton" role="status" aria-live="polite">
      <span className="accepted-skeleton-block" />
      <div><span className="accepted-skeleton-line is-wide" /><span className="accepted-skeleton-line" /></div>
      <span className="sr-only">Đang tải lịch cần nhắc</span>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="accepted-list-skeleton" role="status" aria-live="polite">
      {[0, 1, 2].map(index => (
        <div key={index} className="accepted-appointment-skeleton">
          <span className="accepted-skeleton-block" />
          <div><span className="accepted-skeleton-line is-wide" /><span className="accepted-skeleton-line" /></div>
          <span className="accepted-skeleton-line" />
        </div>
      ))}
      <span className="sr-only">Đang tải danh sách lịch đã nhận</span>
    </div>
  );
}

export default function ReceptionAcceptedAppointments(props: Props) {
  const searchId = useId();
  const statusId = useId();
  const dateId = useId();
  const doctorId = useId();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [dateFilter, setDateFilter] = useState("ALL");
  const [doctorFilter, setDoctorFilter] = useState("ALL");
  const [expandedId, setExpandedId] = useState("");
  const [visibleCount, setVisibleCount] = useState(ACCEPTED_PAGE_SIZE);

  const patientFor = (appointment: Appointment) => props.patients.find(patient => patient.id === appointment.patientId);
  const doctorFor = (appointment: Appointment) => props.doctors.find(doctor => doctor.id === appointment.doctorId);
  const patientName = (appointment: Appointment) => patientFor(appointment)?.fullName || "Chưa tải được tên bệnh nhân";
  const doctorName = (appointment: Appointment) => doctorFor(appointment)?.fullName || appointment.doctorName || "Bác sĩ đã chọn";

  // Preserve the accepted-list scope that existed before this visual polish.
  const accepted = useMemo(
    () => props.appointments.filter(appointment => ACCEPTED_STATUSES.has(appointment.status)),
    [props.appointments],
  );

  const acceptedDoctors = useMemo(() => {
    const ids = new Set(accepted.map(appointment => appointment.doctorId).filter(Boolean));
    return props.doctors.filter(doctor => ids.has(doctor.id));
  }, [accepted, props.doctors]);

  const filtered = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase("vi-VN");
    const today = clinicDateKey(new Date());
    const now = Date.now();
    return accepted.filter(appointment => {
      const matchesKeyword = !keyword
        || patientName(appointment).toLocaleLowerCase("vi-VN").includes(keyword)
        || doctorName(appointment).toLocaleLowerCase("vi-VN").includes(keyword)
        || (appointment.reason || "").toLocaleLowerCase("vi-VN").includes(keyword);
      if (!matchesKeyword) return false;
      if (statusFilter !== "ALL" && appointment.status !== statusFilter) return false;
      if (doctorFilter !== "ALL" && appointment.doctorId !== doctorFilter) return false;
      if (dateFilter === "TODAY" && clinicDateKey(appointment.startAt) !== today) return false;
      if (dateFilter === "UPCOMING" && new Date(appointment.startAt).getTime() < now) return false;
      return true;
    }).sort((left, right) => {
      const leftTime = new Date(left.startAt).getTime();
      const rightTime = new Date(right.startAt).getTime();
      const leftIsUpcoming = leftTime >= now;
      const rightIsUpcoming = rightTime >= now;

      // Reception sees the nearest upcoming visits first, then the latest past visits.
      if (leftIsUpcoming !== rightIsUpcoming) return leftIsUpcoming ? -1 : 1;
      return leftIsUpcoming ? leftTime - rightTime : rightTime - leftTime;
    });
  }, [accepted, dateFilter, doctorFilter, search, statusFilter, props.patients, props.doctors]);

  const filtersActive = Boolean(search.trim())
    || statusFilter !== "ALL"
    || dateFilter !== "ALL"
    || doctorFilter !== "ALL";

  // Keep long operational history compact; a new filter always starts at the first page.
  useEffect(() => {
    setVisibleCount(ACCEPTED_PAGE_SIZE);
    setExpandedId("");
  }, [search, statusFilter, dateFilter, doctorFilter, accepted.length]);

  const visibleAppointments = filtered.slice(0, visibleCount);
  const remainingAppointments = Math.max(0, filtered.length - visibleAppointments.length);

  function clearFilters() {
    setSearch("");
    setStatusFilter("ALL");
    setDateFilter("ALL");
    setDoctorFilter("ALL");
  }

  const realtimeCopy = props.realtimeState === "connected"
    ? "Đang cập nhật trực tiếp"
    : props.realtimeState === "connecting"
      ? "Đang kết nối, vẫn đồng bộ định kỳ"
      : props.realtimeState === "reconnecting"
        ? "Đang kết nối lại, vẫn đồng bộ định kỳ"
        : "Mất kết nối trực tiếp, vẫn đồng bộ định kỳ";

  return (
    <div className="reception-accepted-screen">
      <section className="accepted-reminder-section" aria-labelledby="accepted-reminder-title">
        <header className="accepted-section-header">
          <div>
            <div className="accepted-section-title-line">
              <Bell aria-hidden="true" />
              <h2 id="accepted-reminder-title">Lịch cần nhắc</h2>
              {props.reminders.length > 0 && <span className="accepted-count-badge">{props.reminders.length}</span>}
            </div>
            <p>Các lịch đã xác nhận trong hôm nay và ngày mai cần lễ tân theo dõi.</p>
          </div>
          <span className="accepted-updated-time">{formatUpdatedAt(props.lastUpdatedAt)}</span>
        </header>

        {props.reminderError && props.reminders.length > 0 && (
          <div className="accepted-inline-alert is-error" role="alert">
            <span>Không thể cập nhật lịch cần nhắc. Dữ liệu gần nhất vẫn được giữ lại.</span>
            <button type="button" onClick={() => void props.onRetryReminders()}>
              <RefreshCcw aria-hidden="true" /> Thử lại
            </button>
          </div>
        )}

        {props.reminderLoading && props.reminders.length === 0 ? <ReminderSkeleton /> : props.reminderError && props.reminders.length === 0 ? (
          <div className="accepted-reminder-empty is-error-state" role="alert">
            <RefreshCcw aria-hidden="true" />
            <div>
              <strong>Chưa thể tải lịch cần nhắc</strong>
              <p>Kiểm tra kết nối và thử lại. Các khu vực khác vẫn có thể sử dụng bình thường.</p>
              <button type="button" onClick={() => void props.onRetryReminders()}>Thử lại</button>
            </div>
          </div>
        ) : props.reminders.length === 0 ? (
          <div className="accepted-reminder-empty">
            <Bell aria-hidden="true" />
            <div>
              <strong>Không có lịch cần nhắc</strong>
              <p>Các lịch sắp diễn ra hoặc cần lễ tân liên hệ sẽ xuất hiện tại đây.</p>
            </div>
          </div>
        ) : (
          <ol className="accepted-reminder-list">
            {props.reminders.map(item => {
              const appointment = item.appointment;
              const patient = patientFor(appointment);
              const latestLabel = item.latestAction?.actionType === "CALLED"
                ? "Đã gọi xác nhận"
                : item.latestAction?.actionType === "RESENT"
                  ? "Đã gửi nhắc lại"
                  : item.latestAction?.actionType === "UNREACHABLE"
                    ? "Không liên lạc được"
                    : "Chưa liên hệ";
              const busy = props.busyAppointmentId === appointment.id;
              return (
                <li key={appointment.id}>
                  <article className="accepted-reminder-item">
                    <time dateTime={appointment.startAt} className="accepted-reminder-time">
                      <strong>{formatTime(appointment.startAt)}</strong>
                      <span>{formatDate(appointment.startAt)}</span>
                    </time>
                    <div className="accepted-reminder-person">
                      <strong>{patientName(appointment)}</strong>
                      <span>BS. {doctorName(appointment)}</span>
                      <a className="accepted-phone-link" href={patient?.phone ? `tel:${patient.phone}` : undefined} aria-disabled={!patient?.phone}>
                        <Phone aria-hidden="true" />
                        {patient?.phone || "Chưa có số điện thoại"}
                      </a>
                    </div>
                    <div className="accepted-reminder-reason">
                      <span>Lý do khám</span>
                      <p>{appointment.reason || "Chưa ghi nhận lý do khám"}</p>
                    </div>
                    <div className="accepted-reminder-state">
                      <span className="accepted-status-badge is-confirmed">Đã xác nhận</span>
                      <small>{latestLabel}{item.latestAction ? ` lúc ${formatTime(item.latestAction.createdAt)}` : ""}</small>
                    </div>
                    <div className="accepted-row-actions">
                      {patient && (
                        <button type="button" className="accepted-primary-action" onClick={() => props.onOpenSupport(patient)}>
                          <MessageCircle aria-hidden="true" /> Liên hệ
                        </button>
                      )}
                      <details className="accepted-action-menu">
                        <summary aria-label={`Mở thao tác nhắc lịch của ${patientName(appointment)}`}>
                          <MoreHorizontal aria-hidden="true" />
                          <span>Thao tác</span>
                          <ChevronDown aria-hidden="true" />
                        </summary>
                        <div className="accepted-action-popover">
                          <button type="button" disabled={busy} onClick={() => void props.onRemind(appointment.id, "CALLED")}>Đã gọi xác nhận</button>
                          <button type="button" disabled={busy} onClick={() => void props.onRemind(appointment.id, "RESENT")}>Gửi nhắc lại</button>
                          <button type="button" disabled={busy} onClick={() => void props.onRemind(appointment.id, "UNREACHABLE")}>Không liên lạc được</button>
                        </div>
                      </details>
                    </div>
                  </article>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      <section className="accepted-list-section" aria-labelledby="accepted-list-title">
        <header className="accepted-section-header accepted-list-header">
          <div>
            <h2 id="accepted-list-title">Lịch đã được tiếp nhận</h2>
            <p>Tìm và xử lý các lịch đã được lễ tân xác nhận.</p>
          </div>
          <div className="accepted-sync-state" aria-live="polite">
            <RefreshCcw aria-hidden="true" />
            <span>{realtimeCopy}</span>
          </div>
        </header>

        {props.actionMessage && (
          <div className={`accepted-inline-alert ${props.actionMessageError ? "is-error" : "is-success"}`} role={props.actionMessageError ? "alert" : "status"}>
            {props.actionMessage}
          </div>
        )}
        {props.patientLoadWarning && <div className="accepted-inline-alert is-warning" role="status">{props.patientLoadWarning}</div>}
        {props.queueError && accepted.length > 0 && (
          <div className="accepted-inline-alert is-error" role="alert">
            <span>Không thể cập nhật danh sách. Dữ liệu gần nhất vẫn được giữ lại.</span>
            <button type="button" onClick={() => void props.onRetryQueue()}>
              <RefreshCcw aria-hidden="true" /> Thử lại
            </button>
          </div>
        )}

        {accepted.length > 0 && (
          <div className={`accepted-toolbar ${props.queueRefreshing ? "is-refreshing" : ""}`}>
            <label className="accepted-search-field" htmlFor={searchId}>
              <span>Tìm lịch</span>
              <div>
                <Search aria-hidden="true" />
                <input
                  id={searchId}
                  type="search"
                  value={search}
                  placeholder="Tìm bệnh nhân, bác sĩ hoặc lý do"
                  onChange={event => setSearch(event.target.value)}
                />
                {search && (
                  <button type="button" aria-label="Xóa nội dung tìm kiếm" onClick={() => setSearch("")}>
                    <X aria-hidden="true" />
                  </button>
                )}
              </div>
            </label>
            <label htmlFor={statusId}>
              <span>Trạng thái</span>
              <select id={statusId} value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
                <option value="ALL">Tất cả trạng thái</option>
                {STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label htmlFor={dateId}>
              <span>Thời gian</span>
              <select id={dateId} value={dateFilter} onChange={event => setDateFilter(event.target.value)}>
                <option value="ALL">Tất cả ngày</option>
                <option value="TODAY">Hôm nay</option>
                <option value="UPCOMING">Sắp tới</option>
              </select>
            </label>
            {acceptedDoctors.length > 1 && (
              <label htmlFor={doctorId}>
                <span>Bác sĩ</span>
                <select id={doctorId} value={doctorFilter} onChange={event => setDoctorFilter(event.target.value)}>
                  <option value="ALL">Tất cả bác sĩ</option>
                  {acceptedDoctors.map(doctor => <option key={doctor.id} value={doctor.id}>BS. {doctor.fullName}</option>)}
                </select>
              </label>
            )}
            <div className="accepted-toolbar-summary">
              <span aria-live="polite">Hiển thị <strong>{visibleAppointments.length}</strong> trong {filtered.length} lịch phù hợp</span>
              {filtersActive && <button type="button" onClick={clearFilters}>Xóa bộ lọc</button>}
            </div>
          </div>
        )}

        {props.queueLoading && accepted.length === 0 ? <ListSkeleton /> : props.queueError && accepted.length === 0 ? (
          <div className="accepted-list-empty is-error-state" role="alert">
            <RefreshCcw aria-hidden="true" />
            <strong>Chưa thể tải lịch đã nhận</strong>
            <p>Kiểm tra kết nối và thử lại. Dữ liệu khác trên màn hình không bị ảnh hưởng.</p>
            <button type="button" onClick={() => void props.onRetryQueue()}>Thử lại</button>
          </div>
        ) : accepted.length === 0 ? (
          <div className="accepted-list-empty">
            <CalendarDays aria-hidden="true" />
            <strong>Chưa có lịch được tiếp nhận</strong>
            <p>Các lịch đã xác nhận sẽ xuất hiện tại đây để lễ tân theo dõi.</p>
            <button type="button" onClick={props.onOpenRequests}>Xem yêu cầu đặt lịch</button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="accepted-list-empty is-filtered">
            <Search aria-hidden="true" />
            <strong>Không tìm thấy lịch phù hợp</strong>
            <p>Không có lịch khớp với từ khóa và bộ lọc đang dùng.</p>
            <button type="button" onClick={clearFilters}>Xóa bộ lọc</button>
          </div>
        ) : (
          <>
          <ol className="accepted-appointment-list">
            {visibleAppointments.map(appointment => {
              const patient = patientFor(appointment);
              const needsCompletion = isStaleInProgressAppointment(appointment);
              const status = needsCompletion
                ? { label: "Cần hoàn tất", className: "is-needs-completion" }
                : statusMeta(appointment.status);
              const expanded = expandedId === appointment.id;
              const canManage = appointment.status === "CONFIRMED";
              const canCheckIn = canManage && clinicDateKey(appointment.startAt) === clinicDateKey(new Date());
              const canMarkNoShow = canManage && Date.now() >= new Date(appointment.startAt).getTime() + 30 * 60_000;
              return (
                <li key={appointment.id}>
                  <article className="accepted-appointment-item">
                    <time dateTime={appointment.startAt} className="accepted-appointment-time">
                      <strong>{formatTime(appointment.startAt)}</strong>
                      <span>{formatDate(appointment.startAt)}</span>
                    </time>
                    <div className="accepted-appointment-patient">
                      <span className="accepted-item-label">Bệnh nhân</span>
                      <strong>{patientName(appointment)}</strong>
                      <span>{patient?.phone || "Chưa có số điện thoại"}</span>
                    </div>
                    <div className="accepted-appointment-doctor">
                      <span className="accepted-item-label">Bác sĩ</span>
                      <strong><Stethoscope aria-hidden="true" /> BS. {doctorName(appointment)}</strong>
                    </div>
                    <div className="accepted-appointment-reason">
                      <span className="accepted-item-label">Lý do khám</span>
                      <p>{appointment.reason || "Chưa ghi nhận lý do khám"}</p>
                    </div>
                    <div className="accepted-appointment-state">
                      <span className={`accepted-status-badge ${status.className}`}>{status.label}</span>
                    </div>
                    <div className="accepted-row-actions">
                      <button
                        type="button"
                        className="accepted-primary-action"
                        aria-expanded={expanded}
                        aria-controls={`accepted-detail-${appointment.id}`}
                        onClick={() => setExpandedId(expanded ? "" : appointment.id)}
                      >
                        {expanded ? "Thu gọn" : "Xem chi tiết"}
                      </button>
                      {(patient || canManage || needsCompletion) && (
                        <details className="accepted-action-menu">
                          <summary aria-label={`Mở thao tác cho lịch của ${patientName(appointment)}`}>
                            <MoreHorizontal aria-hidden="true" />
                            <span>Thao tác khác</span>
                            <ChevronDown aria-hidden="true" />
                          </summary>
                          <div className="accepted-action-popover">
                            {patient && (
                              <button type="button" onClick={() => props.onOpenSupport(patient)}>
                                <MessageCircle aria-hidden="true" /> Liên hệ bệnh nhân
                              </button>
                            )}
                            {canCheckIn && (
                              <button
                                type="button"
                                disabled={props.busyAppointmentId === appointment.id}
                                onClick={() => void props.onCheckIn(appointment.id).catch(() => undefined)}
                              >
                                <Clock3 aria-hidden="true" /> Xác nhận đã đến
                              </button>
                            )}
                            {canManage && (
                              <ReceptionRescheduleControl
                                token={props.token}
                                appointment={appointment}
                                patientName={patientName(appointment)}
                                doctorName={doctorName(appointment)}
                                submit={startAt => props.onReschedule(appointment.id, startAt)}
                              />
                            )}
                            {canManage && (
                              <ReceptionCancelControl
                                appointment={appointment}
                                patientName={patientName(appointment)}
                                doctorName={doctorName(appointment)}
                                submit={reason => props.onCancel(appointment.id, reason)}
                              />
                            )}
                            {canMarkNoShow && (
                              <button
                                type="button"
                                disabled={props.busyAppointmentId === appointment.id}
                                onClick={() => void props.onNoShow(appointment.id)}
                              >
                                <Clock3 aria-hidden="true" /> Ghi nhận vắng mặt
                              </button>
                            )}
                            {needsCompletion && (
                              <button
                                type="button"
                                disabled={props.busyAppointmentId === appointment.id}
                                onClick={() => void props.onComplete(appointment.id)}
                              >
                                <Clock3 aria-hidden="true" /> Hoàn tất lượt khám
                              </button>
                            )}
                          </div>
                        </details>
                      )}
                    </div>
                    {expanded && (
                      <div id={`accepted-detail-${appointment.id}`} className="accepted-appointment-detail" role="region" aria-label={`Chi tiết lịch của ${patientName(appointment)}`}>
                        <div><span>Bắt đầu</span><strong>{formatTime(appointment.startAt)}, {formatDate(appointment.startAt)}</strong></div>
                        <div><span>Kết thúc</span><strong>{formatTime(appointment.endAt)}</strong></div>
                        <div><span>Liên hệ</span><strong>{patient?.phone || "Chưa có số điện thoại"}</strong></div>
                        <div className="is-wide"><span>Lý do khám</span><strong>{appointment.reason || "Chưa ghi nhận lý do khám"}</strong></div>
                      </div>
                    )}
                  </article>
                </li>
              );
            })}
          </ol>
          {filtered.length > ACCEPTED_PAGE_SIZE && (
            <footer className="accepted-list-pagination">
              <span aria-live="polite">Đang hiển thị {visibleAppointments.length} trên {filtered.length} lịch</span>
              <button
                type="button"
                onClick={() => setVisibleCount(current => remainingAppointments > 0
                  ? Math.min(current + ACCEPTED_PAGE_SIZE, filtered.length)
                  : ACCEPTED_PAGE_SIZE)}
              >
                {remainingAppointments > 0
                  ? `Xem thêm ${Math.min(ACCEPTED_PAGE_SIZE, remainingAppointments)} lịch`
                  : "Thu gọn danh sách"}
                <ChevronDown className={remainingAppointments > 0 ? "" : "is-up"} aria-hidden="true" />
              </button>
            </footer>
          )}
          </>
        )}
      </section>
    </div>
  );
}
