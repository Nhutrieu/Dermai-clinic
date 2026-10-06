import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  ListOrdered,
  RefreshCw,
  Search,
  Stethoscope,
  Wifi,
  WifiOff,
} from "lucide-react";
import "../../styles/doctor-dashboard.css";
import { request } from "../../core/api";
import type {
  AiAssessment,
  Appointment,
  Doctor,
  MedicalRecord,
  Patient,
  WorkSchedule,
} from "../../core/types";
import type { RealtimeConnectionState } from "../../core/realtime";
import DoctorAiPreviewButton from "./DoctorAiPreviewButton";
import { patientAiLabel } from "../patient/patientAiPresentation";
import {
  buildDoctorTodaySummary,
  formatClinicTime,
  formatDurationFrom,
  getActiveConsultations,
  getDoctorStatus,
  getStaleConsultationTasks,
  getTodayAppointments,
  getTodayShift,
  getWaitingQueue,
  isStaleConsultation,
} from "./doctorDashboardModel";

export type DoctorDashboardResources = {
  appointments: { loading: boolean; error: string };
  records: { loading: boolean; error: string };
  patients: { loading: boolean; error: string };
  schedule: { loading: boolean; error: string };
};

type Props = {
  token: string;
  doctor: Doctor;
  appointments: Appointment[];
  records: MedicalRecord[];
  patients: Record<string, Patient>;
  work: WorkSchedule[];
  resources: DoctorDashboardResources;
  realtimeState: RealtimeConnectionState;
  lastUpdated?: Date;
  onRetry: () => void;
  onStart: (appointmentId: string) => Promise<void>;
  onContinue: (appointment: Appointment) => void;
};

type StatusFilter = "ALL" | "CONFIRMED" | "CHECKED_IN" | "IN_PROGRESS" | "COMPLETED";

const statusOptions: { value: StatusFilter; label: string }[] = [
  { value: "ALL", label: "Tất cả trạng thái" },
  { value: "CONFIRMED", label: "Chờ bắt đầu" },
  { value: "CHECKED_IN", label: "Bệnh nhân đã đến" },
  { value: "IN_PROGRESS", label: "Đang khám" },
  { value: "COMPLETED", label: "Đã hoàn tất" },
];

function patientName(patientId: string, patients: Record<string, Patient>) {
  return patients[patientId]?.fullName || "Chưa tải được tên bệnh nhân";
}

function compactReason(reason?: string) {
  return reason?.trim() || "Không có lý do khám";
}

function formatUpdatedAt(value?: Date) {
  if (!value) return "Chưa đồng bộ";
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(value);
}

function RealtimeStatus({ state, lastUpdated }: { state: RealtimeConnectionState; lastUpdated?: Date }) {
  const connected = state === "connected";
  const label = connected
    ? "Đã kết nối"
    : state === "connecting"
      ? "Đang đồng bộ"
      : "Đang dùng polling dự phòng";
  return (
    <div className={`doctor-realtime is-${state}`} aria-live="polite" aria-atomic="true">
      {connected ? <Wifi aria-hidden="true" /> : <WifiOff aria-hidden="true" />}
      <span><b>{label}</b><small>Cập nhật lúc {formatUpdatedAt(lastUpdated)}</small></span>
    </div>
  );
}

function SectionError({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="doctor-section-error" role="alert">
      <AlertTriangle aria-hidden="true" />
      <span><b>Chưa thể cập nhật khu vực này</b><small>{message}</small></span>
      <button type="button" onClick={retry}><RefreshCw aria-hidden="true" /> Thử lại</button>
    </div>
  );
}

function AppointmentAction({
  appointment,
  busy,
  onStart,
  onContinue,
}: {
  appointment: Appointment;
  busy: boolean;
  onStart: (appointmentId: string) => void;
  onContinue: (appointment: Appointment) => void;
}) {
  if (["CONFIRMED", "CHECKED_IN"].includes(appointment.status)) {
    return <button type="button" className="doctor-button doctor-button-primary" disabled={busy} onClick={() => onStart(appointment.id)}>{busy ? "Đang mở..." : "Bắt đầu khám"}</button>;
  }
  if (appointment.status === "IN_PROGRESS") {
    return <button type="button" className="doctor-button doctor-button-primary" onClick={() => onContinue(appointment)}>Tiếp tục khám &amp; hoàn tất</button>;
  }
  return null;
}

export default function DoctorDashboard({
  token,
  doctor,
  appointments,
  records,
  patients,
  work,
  resources,
  realtimeState,
  lastUpdated,
  onRetry,
  onStart,
  onContinue,
}: Props) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [onlyWithAi, setOnlyWithAi] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const [busyAppointmentId, setBusyAppointmentId] = useState("");
  const [rowError, setRowError] = useState("");
  const [assessments, setAssessments] = useState<Record<string, AiAssessment | null>>({});
  const [aiLoading, setAiLoading] = useState(true);
  const [aiError, setAiError] = useState("");

  const today = useMemo(() => getTodayAppointments(appointments, now), [appointments, now]);
  const active = useMemo(() => getActiveConsultations(appointments), [appointments]);
  const waitingQueue = useMemo(() => getWaitingQueue(appointments, now), [appointments, now]);
  const summary = useMemo(() => buildDoctorTodaySummary(appointments, records, now), [appointments, records, now]);
  const tasks = useMemo(() => getStaleConsultationTasks(appointments, now), [appointments, now]);
  const todayShift = useMemo(() => getTodayShift(work, now), [work, now]);
  const recordAppointmentIds = useMemo(() => new Set(records.map(item => item.appointmentId)), [records]);
  const aiCandidateIds = useMemo(
    () => [...new Set(today.filter(item => ["CONFIRMED", "CHECKED_IN", "IN_PROGRESS"].includes(item.status)).map(item => item.id))],
    [today],
  );

  const loadAssessments = useCallback(async () => {
    if (!aiCandidateIds.length) {
      setAssessments({});
      setAiError("");
      setAiLoading(false);
      return;
    }
    setAiLoading(true);
    const results = await Promise.allSettled(aiCandidateIds.map(async appointmentId => ({
      appointmentId,
      assessment: await request<AiAssessment | undefined>(`/patients/appointments/${appointmentId}/shared-ai-assessment`, token),
    })));
    const next: Record<string, AiAssessment | null> = {};
    let failures = 0;
    results.forEach((result, index) => {
      const appointmentId = aiCandidateIds[index];
      if (result.status === "fulfilled") next[appointmentId] = result.value.assessment ?? null;
      else failures += 1;
    });
    setAssessments(current => failures ? { ...current, ...next } : next);
    setAiError(failures ? `Không thể tải ${failures} kết quả đính kèm.` : "");
    setAiLoading(false);
  }, [aiCandidateIds.join("|"), token]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void loadAssessments();
    // Polling nhẹ giữ danh sách AI được chia sẻ mới mà không cần thay đổi backend.
    const fallback = window.setInterval(() => { void loadAssessments(); }, 30_000);
    return () => window.clearInterval(fallback);
  }, [loadAssessments]);

  const pendingAi = today
    .filter(item => assessments[item.id] && !recordAppointmentIds.has(item.id))
    .map(appointment => ({ appointment, assessment: assessments[appointment.id]! }));
  const normalizedQuery = query.trim().toLocaleLowerCase("vi");
  const visibleAppointments = today.filter(item => {
    const matchesQuery = !normalizedQuery || `${patientName(item.patientId, patients)} ${item.reason || ""}`.toLocaleLowerCase("vi").includes(normalizedQuery);
    const matchesStatus = statusFilter === "ALL"
      || (statusFilter === "COMPLETED" ? ["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(item.status) : item.status === statusFilter);
    return matchesQuery && matchesStatus && (!onlyWithAi || Boolean(assessments[item.id]));
  });

  async function startAppointment(appointmentId: string) {
    setBusyAppointmentId(appointmentId);
    setRowError("");
    try {
      await onStart(appointmentId);
    } catch (cause) {
      setRowError((cause as Error).message || "Không thể bắt đầu ca khám.");
    } finally {
      setBusyAppointmentId("");
    }
  }

  function clearFilters() {
    setQuery("");
    setStatusFilter("ALL");
    setOnlyWithAi(false);
  }

  const hasFilters = Boolean(query || statusFilter !== "ALL" || onlyWithAi);
  const firstActive = active[0];
  const firstActiveNeedsCompletion = firstActive ? isStaleConsultation(firstActive, now) : false;

  return (
    <div className="doctor-dashboard">
      <section className="doctor-dashboard-header" aria-labelledby="doctor-dashboard-title">
        <div>
          <h2 id="doctor-dashboard-title">Lịch khám hôm nay</h2>
          <p>
            {todayShift
              ? `Ca làm ${todayShift.startTime.slice(0, 5)} đến ${todayShift.endTime.slice(0, 5)}, mỗi lịch 30 phút.`
              : "Hôm nay chưa có ca làm việc được cấu hình."}
          </p>
        </div>
        <div className="doctor-dashboard-header-actions">
          <RealtimeStatus state={realtimeState} lastUpdated={lastUpdated} />
          <a className="doctor-button doctor-button-secondary" href="#doctor-waiting-queue">Xem hàng chờ <ChevronRight aria-hidden="true" /></a>
        </div>
      </section>

      <section className="doctor-today-summary" aria-labelledby="doctor-summary-title">
        <h3 id="doctor-summary-title" className="visually-hidden">Tóm tắt lịch hôm nay</h3>
        <dl>
          <div className="is-total"><dt>Tổng lịch</dt><dd>{summary.total}</dd></div>
          <div><dt>Đang chờ</dt><dd>{summary.waiting}</dd></div>
          <div><dt>Đang khám</dt><dd>{summary.inProgress}</dd></div>
          <div><dt>Đã hoàn tất</dt><dd>{summary.completed}</dd></div>
          <div><dt>Chưa bắt đầu</dt><dd>{summary.notStarted}</dd></div>
          <div className={summary.needsAttention ? "is-attention" : ""}><dt>Cần xử lý</dt><dd>{summary.needsAttention}</dd></div>
        </dl>
      </section>

      {resources.appointments.error && <SectionError message={resources.appointments.error} retry={onRetry} />}
      {resources.patients.error && <SectionError message="Một số tên bệnh nhân chưa tải được. Dữ liệu lịch vẫn được giữ nguyên." retry={onRetry} />}

      <div className="doctor-dashboard-layout">
        <div className="doctor-dashboard-primary">
          {firstActive && (
            <section className={`doctor-focus-panel is-active${firstActiveNeedsCompletion ? " is-stale" : ""}`} aria-labelledby="doctor-active-title">
              <div className="doctor-focus-icon"><Stethoscope aria-hidden="true" /></div>
              <div className="doctor-focus-copy">
                <span className={`doctor-status ${firstActiveNeedsCompletion ? "is-attention" : "is-progress"}`}>
                  {firstActiveNeedsCompletion ? "Cần hoàn tất" : "Đang khám"}
                </span>
                <h3 id="doctor-active-title">{patientName(firstActive.patientId, patients)}</h3>
                <p>{compactReason(firstActive.reason)}</p>
                <dl>
                  <div><dt>Giờ hẹn</dt><dd>{formatClinicTime(firstActive.startAt)}</dd></div>
                  <div><dt>Thời gian từ giờ hẹn</dt><dd>{formatDurationFrom(firstActive.startAt, now)}</dd></div>
                  <div><dt>Kết quả khám</dt><dd>{recordAppointmentIds.has(firstActive.id) ? "Đã lưu" : "Không bắt buộc"}</dd></div>
                </dl>
              </div>
              <AppointmentAction appointment={firstActive} busy={busyAppointmentId === firstActive.id} onStart={startAppointment} onContinue={onContinue} />
            </section>
          )}

          <section className="doctor-queue-section" id="doctor-waiting-queue" aria-labelledby="doctor-queue-title">
            <header>
              <div className="doctor-queue-heading">
                <span className="doctor-queue-heading-icon"><ListOrdered aria-hidden="true" /></span>
                <div>
                  <h3 id="doctor-queue-title">Hàng chờ khám</h3>
                  <p>Xếp theo giờ hẹn từ sớm đến muộn. Nếu trùng giờ, người đặt lịch trước sẽ đứng trước.</p>
                </div>
              </div>
              <span>{waitingQueue.length} người chờ</span>
            </header>

            {resources.appointments.loading ? (
              <div className="doctor-list-loading" role="status" aria-live="polite"><span /><span /><span /></div>
            ) : waitingQueue.length ? (
              <ol className="doctor-queue-list" aria-live="polite">
                {waitingQueue.map((appointment, index) => {
                  const status = getDoctorStatus(appointment.status, appointment.startAt, now);
                  return (
                    <li className={`doctor-queue-row${index === 0 ? " is-next" : ""}`} key={appointment.id}>
                      <div className="doctor-queue-position" aria-label={`Số thứ tự ${index + 1}`}>
                        <span>STT</span>
                        <b>{String(index + 1).padStart(2, "0")}</b>
                      </div>
                      <time dateTime={appointment.startAt}>{formatClinicTime(appointment.startAt)}</time>
                      <div className="doctor-appointment-patient">
                        <b>{patientName(appointment.patientId, patients)}</b>
                        <span>{compactReason(appointment.reason)}</span>
                      </div>
                      <div className="doctor-appointment-signals">
                        {index === 0 && <span className="doctor-next-marker">Tiếp theo</span>}
                        {assessments[appointment.id] && <span className="doctor-ai-marker"><BrainCircuit aria-hidden="true" /> AI đính kèm</span>}
                        <span className={`doctor-status is-${status.tone}`}>{status.label}</span>
                      </div>
                      <div className="doctor-appointment-actions">
                        <DoctorAiPreviewButton token={token} appointmentId={appointment.id} available={Boolean(assessments[appointment.id])} />
                        <AppointmentAction appointment={appointment} busy={busyAppointmentId === appointment.id} onStart={startAppointment} onContinue={onContinue} />
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <div className="doctor-compact-empty doctor-queue-empty">
                <CheckCircle2 aria-hidden="true" />
                <div><h3>Hàng chờ đang trống</h3><p>Không còn lịch đã xác nhận cần bắt đầu trong hôm nay.</p></div>
              </div>
            )}
          </section>

          {rowError && <p className="doctor-row-error" role="alert">{rowError}</p>}

          <section className="doctor-schedule-section" id="doctor-today-schedule" aria-labelledby="doctor-schedule-title">
            <header>
              <div><h3 id="doctor-schedule-title">Toàn bộ lịch hôm nay</h3><p>Tra cứu tất cả lượt khám, gồm hàng chờ, đang khám và đã hoàn tất.</p></div>
              <span>{visibleAppointments.length} lịch</span>
            </header>

            <div className="doctor-schedule-filters" role="search">
              <label><span>Tìm bệnh nhân</span><span className="doctor-search-control"><Search aria-hidden="true" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tên hoặc lý do khám" /></span></label>
              <label><span>Trạng thái</span><select value={statusFilter} onChange={event => setStatusFilter(event.target.value as StatusFilter)}>{statusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <label className="doctor-filter-check"><input type="checkbox" checked={onlyWithAi} onChange={event => setOnlyWithAi(event.target.checked)} /> Có ảnh AI đính kèm</label>
              {hasFilters && <button type="button" className="doctor-clear-filter" onClick={clearFilters}><RefreshCw aria-hidden="true" /> Xóa bộ lọc</button>}
            </div>

            {resources.appointments.loading ? (
              <div className="doctor-list-loading" role="status" aria-live="polite"><span /><span /><span /><span /></div>
            ) : !today.length ? (
              <div className="doctor-compact-empty"><CalendarClock aria-hidden="true" /><div><h4>Hôm nay chưa có lịch khám</h4><p>Lịch mới sẽ xuất hiện tại đây sau khi được hệ thống xác nhận.</p></div></div>
            ) : !visibleAppointments.length ? (
              <div className="doctor-compact-empty"><Search aria-hidden="true" /><div><h4>Không tìm thấy lịch phù hợp</h4><p>Thử đổi trạng thái, từ khóa hoặc bỏ lọc ảnh AI.</p></div></div>
            ) : (
              <div className="doctor-appointment-list" aria-live="polite">
                {visibleAppointments.map(appointment => {
                  const status = isStaleConsultation(appointment, now)
                    ? { label: "Cần hoàn tất", tone: "attention" as const }
                    : getDoctorStatus(appointment.status, appointment.startAt, now);
                  return (
                    <article className="doctor-appointment-row" key={appointment.id}>
                      <time dateTime={appointment.startAt}>{formatClinicTime(appointment.startAt)}</time>
                      <div className="doctor-appointment-patient">
                        <b>{patientName(appointment.patientId, patients)}</b>
                        <span>{compactReason(appointment.reason)}</span>
                      </div>
                      <div className="doctor-appointment-signals">
                        {assessments[appointment.id] && <span className="doctor-ai-marker"><BrainCircuit aria-hidden="true" /> AI đính kèm</span>}
                        <span className={`doctor-status is-${status.tone}`}>{status.label}</span>
                      </div>
                      <div className="doctor-appointment-actions">
                        <DoctorAiPreviewButton token={token} appointmentId={appointment.id} available={Boolean(assessments[appointment.id])} />
                        <AppointmentAction appointment={appointment} busy={busyAppointmentId === appointment.id} onStart={startAppointment} onContinue={onContinue} />
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        <aside className="doctor-dashboard-secondary" aria-label="Việc cần xử lý">
          <section className="doctor-side-section" aria-labelledby="doctor-ai-title">
            <header><div><BrainCircuit aria-hidden="true" /><h3 id="doctor-ai-title">Phân tích AI đính kèm</h3></div><span>{pendingAi.length}</span></header>
            <p className="doctor-section-description">Kết quả đang chờ bác sĩ đối chiếu trong quá trình khám.</p>
            {aiError && <SectionError message={aiError} retry={() => { void loadAssessments(); }} />}
            {aiLoading && !Object.keys(assessments).length ? (
              <div className="doctor-mini-loading" role="status">Đang kiểm tra kết quả được chia sẻ...</div>
            ) : !pendingAi.length ? (
              <p className="doctor-side-empty">Không có kết quả AI cần xem trong lịch hôm nay.</p>
            ) : (
              <div className="doctor-side-list">
                {pendingAi.slice(0, 4).map(({ appointment, assessment }) => (
                  <article key={assessment.id}>
                    <div><b>{patientName(appointment.patientId, patients)}</b><small>Gửi {new Date(assessment.createdAt).toLocaleString("vi-VN")}</small></div>
                    <p><span>Mẫu hình ảnh</span><b>{patientAiLabel(assessment.predictedLabel)}</b></p>
                    <p><span>Mức độ phù hợp</span><b>{(assessment.confidence * 100).toFixed(1)}%</b></p>
                    <span className="doctor-ai-review-state">Chờ bác sĩ đối chiếu</span>
                    <DoctorAiPreviewButton token={token} appointmentId={appointment.id} available />
                  </article>
                ))}
              </div>
            )}
          </section>

          {tasks.length > 0 && (
            <section className="doctor-side-section" aria-labelledby="doctor-tasks-title">
              <header><div><ClipboardCheck aria-hidden="true" /><h3 id="doctor-tasks-title">Lượt khám cần hoàn tất</h3></div><span>{tasks.length}</span></header>
              {resources.records.error && <SectionError message={resources.records.error} retry={onRetry} />}
              <div className="doctor-task-list">
                {tasks.map(task => (
                  <article key={task.appointment.id}>
                    <Clock3 aria-hidden="true" />
                    <div><b>{task.label}</b><span>{patientName(task.appointment.patientId, patients)} · {formatClinicTime(task.appointment.startAt)}</span></div>
                    <button type="button" aria-label={`${task.label} cho ${patientName(task.appointment.patientId, patients)}`} onClick={() => onContinue(task.appointment)}><ChevronRight aria-hidden="true" /></button>
                  </article>
                ))}
              </div>
            </section>
          )}

          {summary.needsAttention > 0 && (
            <section className="doctor-side-section is-attention" aria-labelledby="doctor-attention-title">
              <header><div><AlertTriangle aria-hidden="true" /><h3 id="doctor-attention-title">Cần chú ý</h3></div><span>{summary.needsAttention}</span></header>
              <p className="doctor-section-description">Lịch đã qua giờ hẹn hoặc lượt khám đã quá giờ kết thúc trên 60 phút. Hệ thống không tự động hoàn tất ca.</p>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
