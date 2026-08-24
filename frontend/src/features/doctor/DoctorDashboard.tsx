import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
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
  getNextPatient,
  getTodayAppointments,
  getTodayShift,
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
  onComplete: (appointmentId: string) => Promise<void>;
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
  onComplete,
  onContinue,
}: {
  appointment: Appointment;
  busy: boolean;
  onStart: (appointmentId: string) => void;
  onComplete: (appointmentId: string) => void;
  onContinue: (appointment: Appointment) => void;
}) {
  if (["CONFIRMED", "CHECKED_IN"].includes(appointment.status)) {
    return <button type="button" className="doctor-button doctor-button-primary" disabled={busy} onClick={() => onStart(appointment.id)}>{busy ? "Đang mở..." : "Bắt đầu khám"}</button>;
  }
  if (appointment.status === "IN_PROGRESS") {
    return (
      <div className="doctor-completion-actions">
        <button type="button" className="doctor-button doctor-button-secondary" onClick={() => onContinue(appointment)}>Mở chi tiết</button>
        <button type="button" className="doctor-button doctor-button-primary" disabled={busy} onClick={() => onComplete(appointment.id)}>
          {busy ? "Đang hoàn tất..." : "Hoàn tất lượt khám"}
        </button>
      </div>
    );
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
  onComplete,
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
  const nextPatient = useMemo(() => getNextPatient(appointments, now), [appointments, now]);
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

  async function completeAppointment(appointmentId: string) {
    setBusyAppointmentId(appointmentId);
    setRowError("");
    try {
      await onComplete(appointmentId);
    } catch (cause) {
      setRowError((cause as Error).message || "Không thể hoàn tất lượt khám.");
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
              ? `Ca làm ${todayShift.startTime.slice(0, 5)} đến ${todayShift.endTime.slice(0, 5)}, mỗi lịch ${todayShift.slotMinutes} phút.`
              : "Hôm nay chưa có ca làm việc được cấu hình."}
          </p>
        </div>
        <div className="doctor-dashboard-header-actions">
          <RealtimeStatus state={realtimeState} lastUpdated={lastUpdated} />
          <a className="doctor-button doctor-button-secondary" href="#doctor-today-schedule">Xem lịch hôm nay <ChevronRight aria-hidden="true" /></a>
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
              <AppointmentAction appointment={firstActive} busy={busyAppointmentId === firstActive.id} onStart={startAppointment} onComplete={completeAppointment} onContinue={onContinue} />
            </section>
          )}

          {nextPatient ? (
            <section className="doctor-focus-panel" aria-labelledby="doctor-next-title">
              <div className="doctor-focus-icon"><CalendarClock aria-hidden="true" /></div>
              <div className="doctor-focus-copy">
                <span className={`doctor-status is-${getDoctorStatus(nextPatient.status, nextPatient.startAt, now).tone}`}>{getDoctorStatus(nextPatient.status, nextPatient.startAt, now).label}</span>
                <h3 id="doctor-next-title">Bệnh nhân tiếp theo: {patientName(nextPatient.patientId, patients)}</h3>
                <p>{compactReason(nextPatient.reason)}</p>
                <dl>
                  <div><dt>Giờ hẹn</dt><dd>{formatClinicTime(nextPatient.startAt)}</dd></div>
                  <div><dt>Ảnh AI</dt><dd>{assessments[nextPatient.id] ? "Có đính kèm" : "Không có"}</dd></div>
                  <div><dt>Tiếp nhận</dt><dd>{nextPatient.status === "CHECKED_IN" ? `Đã đến${nextPatient.checkedInAt ? ` lúc ${formatClinicTime(nextPatient.checkedInAt)}` : ""}` : "Chưa xác nhận có mặt"}</dd></div>
                </dl>
              </div>
              <AppointmentAction appointment={nextPatient} busy={busyAppointmentId === nextPatient.id} onStart={startAppointment} onComplete={completeAppointment} onContinue={onContinue} />
            </section>
          ) : !resources.appointments.loading && (
            <section className="doctor-compact-empty" aria-labelledby="doctor-next-empty-title">
              <CheckCircle2 aria-hidden="true" />
              <div><h3 id="doctor-next-empty-title">Chưa có bệnh nhân tiếp theo</h3><p>Không còn lịch đã xác nhận cần bắt đầu trong hôm nay.</p></div>
            </section>
          )}

          {rowError && <p className="doctor-row-error" role="alert">{rowError}</p>}

          <section className="doctor-schedule-section" id="doctor-today-schedule" aria-labelledby="doctor-schedule-title">
            <header>
              <div><h3 id="doctor-schedule-title">Danh sách lịch hôm nay</h3><p>Hiển thị theo thứ tự giờ hẹn; bệnh nhân đã được lễ tân tiếp nhận sẽ có trạng thái riêng.</p></div>
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
                        <AppointmentAction appointment={appointment} busy={busyAppointmentId === appointment.id} onStart={startAppointment} onComplete={completeAppointment} onContinue={onContinue} />
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
                    <button type="button" disabled={busyAppointmentId === task.appointment.id} aria-label={`${task.label} cho ${patientName(task.appointment.patientId, patients)}`} onClick={() => void completeAppointment(task.appointment.id)}><ChevronRight aria-hidden="true" /></button>
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
