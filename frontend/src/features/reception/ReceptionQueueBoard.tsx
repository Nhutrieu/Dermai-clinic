import { useEffect, useId, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  CircleSlash2,
  Clock3,
  RefreshCcw,
  Search,
  Stethoscope,
  UserX,
  Wifi,
  WifiOff,
} from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import type { RealtimeConnectionState } from "../../core/realtime";
import type { Appointment, ReminderItem } from "../../core/types";
import {
  buildReceptionQueueSummary,
  getAttentionAppointments,
  getOperationalAppointments,
  getReceptionQueueState,
  getReceptionStatus,
  isOverdueForNoShow,
  type ReceptionQueuePhase,
} from "./receptionDashboardModel";

type QueueFilter = "ALL" | "ATTENTION" | ReceptionQueuePhase;
type QueueSort = "TIME_ASC" | "TIME_DESC" | "STATUS";

type Props = {
  appointments: Appointment[];
  reminders: ReminderItem[];
  queueLoading: boolean;
  queueError: string;
  actionError: string;
  actionErrorAppointmentId: string;
  busyAppointmentId: string;
  realtimeState: RealtimeConnectionState;
  lastSyncedAt: Date | null;
  liveRevision: number;
  changedAppointmentIds: string[];
  patientName: (appointment: Appointment) => string;
  doctorName: (appointment: Appointment) => string;
  onOpenRequests: () => void;
  onOpenAccepted: () => void;
  onConfirm: (appointmentId: string) => Promise<void>;
  onNoShow: (appointmentId: string) => Promise<void>;
  onRetryQueue: () => Promise<void>;
};

const STATUS_ORDER: ReceptionQueuePhase[] = [
  "attention",
  "overdue",
  "in_progress",
  "upcoming",
  "completed",
  "no_show",
  "closed",
];

function formatTime(value: string | Date) {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(date);
}

function formatLongDate(value: Date) {
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(value);
}

function durationCopy(minutes: number) {
  if (minutes <= 0) return "chưa đầy 1 phút";
  if (minutes < 60) return `${minutes} phút`;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return remaining ? `${hours} giờ ${remaining} phút` : `${hours} giờ`;
}

function operationalTiming(appointment: Appointment, now: Date, needsContact: boolean) {
  const state = getReceptionQueueState(appointment, now);
  if (needsContact) return "Cần liên hệ lại bệnh nhân";
  if (state.phase === "upcoming") {
    const minutes = Math.ceil((new Date(appointment.startAt).getTime() - now.getTime()) / 60_000);
    return `Còn ${durationCopy(minutes)}`;
  }
  if (state.phase === "overdue") return `Qua giờ hẹn ${durationCopy(state.minutesFromStart)}`;
  if (appointment.updatedAt) return `Cập nhật lúc ${formatTime(appointment.updatedAt)}`;
  if (state.phase === "attention") return "Cần lễ tân xử lý";
  return `Theo lịch lúc ${formatTime(appointment.startAt)}`;
}

function QueueStateIcon({ phase }: { phase: ReceptionQueuePhase }) {
  if (phase === "overdue" || phase === "attention") return <AlertTriangle aria-hidden="true" />;
  if (phase === "in_progress") return <Stethoscope aria-hidden="true" />;
  if (phase === "completed") return <CheckCircle2 aria-hidden="true" />;
  if (phase === "no_show") return <UserX aria-hidden="true" />;
  if (phase === "closed") return <CircleSlash2 aria-hidden="true" />;
  return <Clock3 aria-hidden="true" />;
}

function NoShowDialog({
  appointment,
  patient,
  doctor,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  appointment: Appointment;
  patient: string;
  doctor: string;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const titleId = useId();
  const descriptionId = useId();

  return (
    <AccessibleDialog
      title="Ghi nhận bệnh nhân vắng mặt?"
      titleId={titleId}
      descriptionId={descriptionId}
      role="alertdialog"
      tone="warning"
      className="reception-queue-dialog"
      closeLabel="Đóng xác nhận vắng mặt"
      closeDisabled={busy}
      onClose={onClose}
      footer={(
        <>
          <button
            type="button"
            className="reception-button-secondary"
            data-dialog-initial-focus
            disabled={busy}
            onClick={onClose}
          >
            Giữ trạng thái hiện tại
          </button>
          <button
            type="button"
            className="reception-button-danger"
            disabled={busy}
            onClick={() => void onConfirm().then(onClose).catch(() => undefined)}
          >
            {busy ? "Đang cập nhật" : "Xác nhận vắng mặt"}
          </button>
        </>
      )}
    >
      <p>
        Chỉ xác nhận sau khi đã kiểm tra bệnh nhân chưa đến và lịch đã quá giờ ít nhất 30 phút.
      </p>
      <dl className="reception-queue-dialog-details">
        <div><dt>Bệnh nhân</dt><dd>{patient}</dd></div>
        <div><dt>Bác sĩ</dt><dd>{doctor}</dd></div>
        <div><dt>Giờ hẹn</dt><dd>{formatTime(appointment.startAt)}</dd></div>
        <div><dt>Trạng thái hiện tại</dt><dd>{getReceptionStatus(appointment.status).label}</dd></div>
        <div><dt>Trạng thái sau cập nhật</dt><dd>Vắng mặt</dd></div>
      </dl>
      <p className="reception-queue-dialog-consequence">
        Lịch sẽ được đóng với trạng thái vắng mặt và không còn nằm trong nhóm chờ khám.
      </p>
      {error && <div className="reception-queue-action-error" role="alert">{error}</div>}
    </AccessibleDialog>
  );
}

function RealtimeState({ state }: { state: RealtimeConnectionState }) {
  const copy = state === "connected"
    ? "Đã kết nối trực tiếp"
    : state === "connecting"
      ? "Đang kết nối, vẫn đồng bộ định kỳ"
      : state === "reconnecting"
        ? "Đang đồng bộ lại, vẫn có cập nhật dự phòng"
        : "Mất kết nối trực tiếp, dữ liệu có thể đã cũ, cập nhật định kỳ vẫn hoạt động";
  const Icon = state === "connected" ? Wifi : state === "closed" ? WifiOff : RefreshCcw;
  return (
    <span className={`reception-queue-realtime is-${state}`}>
      <Icon aria-hidden="true" />
      {copy}
    </span>
  );
}

export default function ReceptionQueueBoard(props: Props) {
  const [query, setQuery] = useState("");
  const [doctorFilter, setDoctorFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState<QueueFilter>("ALL");
  const [sort, setSort] = useState<QueueSort>("TIME_ASC");
  const [now, setNow] = useState(() => new Date());
  const [noShowAppointment, setNoShowAppointment] = useState<Appointment | null>(null);

  // One shared minute clock keeps time-based labels current without per-row timers.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const todayAppointments = useMemo(
    () => getOperationalAppointments(props.appointments, now),
    [props.appointments, now],
  );
  const attentionIds = useMemo(
    () => new Set(getAttentionAppointments(props.appointments, props.reminders, now).map(item => item.id)),
    [props.appointments, props.reminders, now],
  );
  const summary = useMemo(
    () => buildReceptionQueueSummary(props.appointments, props.reminders, now),
    [props.appointments, props.reminders, now],
  );
  const changedIds = useMemo(() => new Set(props.changedAppointmentIds), [props.changedAppointmentIds]);
  const unreachableIds = useMemo(
    () => new Set(props.reminders
      .filter(item => item.latestAction?.actionType === "UNREACHABLE")
      .map(item => item.appointment.id)),
    [props.reminders],
  );
  const doctorOptions = useMemo(() => {
    const options = new Map<string, string>();
    todayAppointments.forEach(item => options.set(item.doctorId || "UNASSIGNED", props.doctorName(item)));
    return [...options.entries()].sort((left, right) => left[1].localeCompare(right[1], "vi"));
  }, [todayAppointments, props.doctorName]);

  const filteredAppointments = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("vi");
    const filtered = todayAppointments.filter(item => {
      const phase = getReceptionQueueState(item, now).phase;
      const matchesQuery = !normalizedQuery
        || props.patientName(item).toLocaleLowerCase("vi").includes(normalizedQuery);
      const matchesDoctor = doctorFilter === "ALL"
        || (doctorFilter === "UNASSIGNED" ? !item.doctorId : item.doctorId === doctorFilter);
      const matchesStatus = statusFilter === "ALL"
        || (statusFilter === "ATTENTION" ? attentionIds.has(item.id) : phase === statusFilter);
      return matchesQuery && matchesDoctor && matchesStatus;
    });
    return [...filtered].sort((left, right) => {
      if (sort === "STATUS") {
        const phaseDelta = STATUS_ORDER.indexOf(getReceptionQueueState(left, now).phase)
          - STATUS_ORDER.indexOf(getReceptionQueueState(right, now).phase);
        if (phaseDelta) return phaseDelta;
      }
      const timeDelta = new Date(left.startAt).getTime() - new Date(right.startAt).getTime();
      return (sort === "TIME_DESC" ? -timeDelta : timeDelta) || left.id.localeCompare(right.id);
    });
  }, [attentionIds, doctorFilter, now, props.doctorName, props.patientName, query, sort, statusFilter, todayAppointments]);

  const hasFilters = Boolean(query || doctorFilter !== "ALL" || statusFilter !== "ALL" || sort !== "TIME_ASC");
  const summaryItems: { key: QueueFilter; label: string; value: number }[] = [
    { key: "upcoming", label: "Sắp đến", value: summary.upcoming },
    { key: "overdue", label: "Qua giờ hẹn", value: summary.overdue },
    { key: "in_progress", label: "Đang khám", value: summary.inProgress },
    { key: "completed", label: "Hoàn tất", value: summary.completed },
    { key: "no_show", label: "Vắng mặt", value: summary.noShow },
    { key: "ATTENTION", label: "Cần xử lý", value: summary.attention },
  ];

  function resetFilters() {
    setQuery("");
    setDoctorFilter("ALL");
    setStatusFilter("ALL");
    setSort("TIME_ASC");
  }

  return (
    <section className="reception-queue" aria-labelledby="reception-queue-title">
      <header className="reception-queue-header">
        <div>
          <h2 id="reception-queue-title">Hàng đợi hôm nay</h2>
          <p>{formatLongDate(now)} · {todayAppointments.length} lịch trong ngày</p>
        </div>
        <div className="reception-queue-sync">
          <span role="status" aria-live="polite"><RealtimeState state={props.realtimeState} /></span>
          <span>
            {props.lastSyncedAt ? `Cập nhật lúc ${formatTime(props.lastSyncedAt)}` : "Chưa có lần đồng bộ"}
          </span>
          <button
            type="button"
            className="reception-queue-refresh"
            aria-label="Làm mới hàng đợi"
            disabled={props.queueLoading}
            onClick={() => void props.onRetryQueue()}
          >
            <RefreshCcw aria-hidden="true" />
            <span>{props.queueLoading ? "Đang tải" : "Làm mới"}</span>
          </button>
        </div>
      </header>

      <div className="reception-queue-limit" role="note">
        <AlertTriangle aria-hidden="true" />
        <span>Hệ thống chưa ghi nhận bước tiếp nhận tại quầy, nên chưa có thời gian chờ hoặc vị trí hàng đợi.</span>
      </div>

      <div className="reception-queue-summary" aria-label="Tóm tắt vận hành hôm nay">
        {summaryItems.map(item => (
          <button
            type="button"
            key={item.key}
            className={statusFilter === item.key ? "is-active" : ""}
            aria-pressed={statusFilter === item.key}
            onClick={() => setStatusFilter(current => current === item.key ? "ALL" : item.key)}
          >
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </button>
        ))}
      </div>

      <div className="reception-queue-toolbar" aria-label="Bộ lọc hàng đợi">
        <label className="reception-queue-search">
          <span>Tìm bệnh nhân</span>
          <div><Search aria-hidden="true" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Nhập tên bệnh nhân" /></div>
        </label>
        <label>
          <span>Bác sĩ</span>
          <select value={doctorFilter} onChange={event => setDoctorFilter(event.target.value)}>
            <option value="ALL">Tất cả bác sĩ</option>
            {doctorOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>Trạng thái</span>
          <select value={statusFilter} onChange={event => setStatusFilter(event.target.value as QueueFilter)}>
            <option value="ALL">Tất cả trạng thái</option>
            <option value="ATTENTION">Cần xử lý</option>
            <option value="upcoming">Sắp đến</option>
            <option value="overdue">Qua giờ hẹn</option>
            <option value="in_progress">Đang khám</option>
            <option value="completed">Hoàn tất</option>
            <option value="no_show">Vắng mặt</option>
            <option value="closed">Đã hủy</option>
          </select>
        </label>
        <label>
          <span>Sắp xếp</span>
          <select value={sort} onChange={event => setSort(event.target.value as QueueSort)}>
            <option value="TIME_ASC">Giờ hẹn sớm nhất</option>
            <option value="TIME_DESC">Giờ hẹn muộn nhất</option>
            <option value="STATUS">Ưu tiên trạng thái</option>
          </select>
        </label>
      </div>

      {props.queueError && !props.appointments.length ? (
        <div className="reception-queue-state reception-queue-state-error" role="alert">
          <AlertTriangle aria-hidden="true" />
          <div><strong>Không thể tải hàng đợi</strong><p>{props.queueError}</p></div>
          <button type="button" onClick={() => void props.onRetryQueue()}><RefreshCcw aria-hidden="true" />Tải lại</button>
        </div>
      ) : props.queueLoading && !props.appointments.length ? (
        <div className="reception-queue-loading" role="status" aria-label="Đang tải hàng đợi hôm nay">
          {[0, 1, 2, 3].map(item => <span key={item} aria-hidden="true" />)}
        </div>
      ) : filteredAppointments.length === 0 ? (
        <div className="reception-queue-state">
          <CalendarClock aria-hidden="true" />
          <div>
            <strong>{todayAppointments.length ? "Không có lịch phù hợp bộ lọc" : "Hôm nay chưa có lịch hẹn"}</strong>
            <p>{todayAppointments.length ? "Xóa bộ lọc để xem lại toàn bộ hàng đợi." : "Lịch mới sẽ tự xuất hiện khi hệ thống ghi nhận."}</p>
          </div>
          {hasFilters && <button type="button" onClick={resetFilters}>Xóa bộ lọc</button>}
        </div>
      ) : (
        <div className="reception-queue-table-wrap">
          <div className="reception-queue-table-head" aria-hidden="true">
            <span>Giờ hẹn</span><span>Bệnh nhân</span><span>Bác sĩ</span><span>Tiến trình</span><span>Thao tác</span>
          </div>
          <div className="reception-queue-list" role="list" aria-live="polite">
            {filteredAppointments.map(item => {
              const state = getReceptionQueueState(item, now);
              const patient = props.patientName(item);
              const doctor = props.doctorName(item);
              const busy = props.busyAppointmentId === item.id;
              const rowError = props.actionErrorAppointmentId === item.id ? props.actionError : "";
              let action: ReactNode = <span className="reception-queue-no-action">Không cần thao tác</span>;
              if (item.status === "PENDING") {
                action = <button type="button" className="reception-row-action" onClick={props.onOpenRequests}>Mở yêu cầu<ChevronRight aria-hidden="true" /></button>;
              } else if (item.status === "ASSIGNED") {
                action = <button type="button" className="reception-row-action" disabled={busy} onClick={() => void props.onConfirm(item.id).catch(() => undefined)}>{busy ? "Đang xác nhận" : "Xác nhận lịch"}</button>;
              } else if (isOverdueForNoShow(item, now)) {
                action = <button type="button" className="reception-row-action reception-row-action-warning" disabled={busy} onClick={() => setNoShowAppointment(item)}>Ghi nhận vắng</button>;
              }
              return (
                <article
                  key={item.id}
                  className={`reception-queue-row ${changedIds.has(item.id) ? "has-live-update" : ""}`}
                  role="listitem"
                  aria-label={`${formatTime(item.startAt)}, ${patient}, ${doctor}, ${state.label}`}
                >
                  <time dateTime={item.startAt} className="reception-queue-time" data-label="Giờ hẹn">
                    <strong>{formatTime(item.startAt)}</strong>
                    <span>{formatTime(item.startAt)} đến {formatTime(item.endAt)}</span>
                  </time>
                  <div className="reception-queue-person" data-label="Bệnh nhân">
                    <strong>{patient}</strong>
                    <span>{item.reason || "Chưa ghi lý do khám"}</span>
                  </div>
                  <div className="reception-queue-doctor" data-label="Bác sĩ"><strong>{doctor}</strong></div>
                  <div className="reception-queue-progress" data-label="Tiến trình">
                    <span className={`reception-queue-status reception-queue-status-${state.tone}`}><QueueStateIcon phase={state.phase} />{state.label}</span>
                    <small>{operationalTiming(item, now, unreachableIds.has(item.id))}</small>
                  </div>
                  <div className="reception-queue-action" data-label="Thao tác">{action}</div>
                  {rowError && <div className="reception-queue-action-error" role="alert">{rowError}</div>}
                </article>
              );
            })}
          </div>
        </div>
      )}

      <footer className="reception-queue-footer">
        <span>Đang hiển thị {filteredAppointments.length} trong {todayAppointments.length} lịch</span>
        <button type="button" className="reception-text-action" onClick={props.onOpenAccepted}>Xem toàn bộ lịch <ChevronRight aria-hidden="true" /></button>
      </footer>

      {props.queueError && props.appointments.length > 0 && (
        <div className="reception-queue-stale" role="status">
          <AlertTriangle aria-hidden="true" />
          <span>Chưa thể làm mới. Danh sách gần nhất vẫn được giữ lại và đồng bộ định kỳ dự phòng vẫn hoạt động.</span>
          <button type="button" onClick={() => void props.onRetryQueue()}>Thử lại</button>
        </div>
      )}

      <span className="reception-queue-live-announcement" aria-live="polite">
        {props.liveRevision ? "Hàng đợi vừa được cập nhật." : ""}
      </span>

      {noShowAppointment && (
        <NoShowDialog
          appointment={noShowAppointment}
          patient={props.patientName(noShowAppointment)}
          doctor={props.doctorName(noShowAppointment)}
          busy={props.busyAppointmentId === noShowAppointment.id}
          error={props.actionErrorAppointmentId === noShowAppointment.id ? props.actionError : ""}
          onClose={() => setNoShowAppointment(null)}
          onConfirm={() => props.onNoShow(noShowAppointment.id)}
        />
      )}
    </section>
  );
}
