import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../core/api";
import {
  subscribeRealtime,
  type RealtimeConnectionState,
} from "../../core/realtime";
import type {
  Appointment,
  Doctor,
  Patient,
  ReminderAction,
  ReminderItem,
} from "../../core/types";
import ReceptionDashboard from "./ReceptionDashboard";
import ReceptionPanel from "./ReceptionPanel";
import {
  APPOINTMENT_ALREADY_HANDLED_MESSAGE,
  isAppointmentAlreadyHandledError,
  toBookingIssue,
} from "./receptionBookingModel";

type PatientPage = { content: Patient[]; totalElements: number };
type ReceptionTab = "profile" | "appointments" | "records";

function appointmentSnapshot(appointment: Appointment) {
  return [
    appointment.status,
    appointment.startAt,
    appointment.endAt,
    appointment.doctorId || "",
    appointment.reason || "",
    appointment.updatedAt || "",
  ].join("|");
}

export default function ReceptionWorkspace({
  token,
  tab,
  onNavigate,
}: {
  token: string;
  tab: string;
  onNavigate: (tab: ReceptionTab) => void;
}) {
  useEffect(() => {
    const navigate = (event: Event) => {
      const target = (event as CustomEvent<ReceptionTab>).detail;
      if (["profile", "appointments", "records"].includes(target)) onNavigate(target);
    };
    window.addEventListener("reception-navigate", navigate);
    return () => window.removeEventListener("reception-navigate", navigate);
  }, [onNavigate]);

  if (tab !== "profile") return <ReceptionPanel token={token} tab={tab} />;
  return <ReceptionDashboardContainer token={token} onNavigate={onNavigate} />;
}

function ReceptionDashboardContainer({
  token,
  onNavigate,
}: {
  token: string;
  onNavigate: (tab: ReceptionTab) => void;
}) {
  const [query, setQuery] = useState("");
  const [lastSearchTerm, setLastSearchTerm] = useState("");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchResults, setSearchResults] = useState<Patient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [searchAttempted, setSearchAttempted] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [reminderLoading, setReminderLoading] = useState(true);
  const [reminderError, setReminderError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionErrorAppointmentId, setActionErrorAppointmentId] = useState("");
  const [busyAppointmentId, setBusyAppointmentId] = useState("");
  const [realtimeState, setRealtimeState] = useState<RealtimeConnectionState>("connecting");
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);
  const [liveRevision, setLiveRevision] = useState(0);
  const [changedAppointmentIds, setChangedAppointmentIds] = useState<string[]>([]);
  const realtimeRefreshTimer = useRef<number | null>(null);
  const liveHighlightTimer = useRef<number | null>(null);
  const appointmentSnapshotsRef = useRef<Map<string, string>>(new Map());

  const loadQueue = useCallback(async (showLoading = false) => {
    if (showLoading) setQueueLoading(true);
    try {
      setQueueError("");
      const from = new Date();
      from.setDate(from.getDate() - 1);
      const to = new Date();
      to.setDate(to.getDate() + 60);
      const items = await request<Appointment[]>(
        `/appointments/queue?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`,
        token,
      );
      const previousSnapshots = appointmentSnapshotsRef.current;
      const nextSnapshots = new Map(items.map(item => [item.id, appointmentSnapshot(item)]));
      const changedIds = previousSnapshots.size
        ? items.filter(item => previousSnapshots.get(item.id) !== nextSnapshots.get(item.id)).map(item => item.id)
        : [];
      const removedCount = previousSnapshots.size
        ? [...previousSnapshots.keys()].filter(id => !nextSnapshots.has(id)).length
        : 0;
      appointmentSnapshotsRef.current = nextSnapshots;
      setAppointments(items);
      setLastSyncedAt(new Date());

      // Highlight only rows whose persisted appointment data actually changed.
      if (changedIds.length || removedCount) {
        if (liveHighlightTimer.current !== null) window.clearTimeout(liveHighlightTimer.current);
        setChangedAppointmentIds(changedIds);
        setLiveRevision(Date.now());
        liveHighlightTimer.current = window.setTimeout(() => {
          setChangedAppointmentIds([]);
          setLiveRevision(0);
        }, 900);
      }

      // A missing patient profile must not prevent the operational schedule from rendering.
      const patientIds = [...new Set(items.map(item => item.patientId))];
      const loaded = await Promise.allSettled(patientIds.map(id => request<Patient>(`/patients/${id}`, token)));
      const available = loaded
        .filter((result): result is PromiseFulfilledResult<Patient> => result.status === "fulfilled")
        .map(result => result.value);
      setPatients(current => [...new Map([...current, ...available].map(item => [item.id, item])).values()]);
    } catch (cause) {
      setQueueError((cause as Error).message);
    } finally {
      setQueueLoading(false);
    }
  }, [token]);

  const loadReminders = useCallback(async () => {
    setReminderLoading(true);
    try {
      setReminderError("");
      setReminders(await request<ReminderItem[]>("/appointments/reminders", token));
    } catch (cause) {
      setReminderError((cause as Error).message);
    } finally {
      setReminderLoading(false);
    }
  }, [token]);

  const loadDoctors = useCallback(async () => {
    try {
      setDoctors(await request<Doctor[]>("/doctors", token));
    } catch {
      // Appointment rows keep their server-provided doctor label or a neutral fallback.
    }
  }, [token]);

  useEffect(() => {
    void loadDoctors();
    void loadQueue(true);
    void loadReminders();
  }, [loadDoctors, loadQueue, loadReminders]);

  useEffect(() => {
    const refresh = () => { void loadDoctors(); };
    window.addEventListener("doctor-profiles-changed", refresh);
    return () => window.removeEventListener("doctor-profiles-changed", refresh);
  }, [loadDoctors]);

  useEffect(() => {
    const refresh = () => {
      void loadQueue();
      void loadReminders();
    };
    window.addEventListener("reception-appointments-changed", refresh);
    return () => window.removeEventListener("reception-appointments-changed", refresh);
  }, [loadQueue, loadReminders]);

  useEffect(() => {
    const refresh = async () => {
      await Promise.all([loadQueue(), loadReminders()]);
    };
    const scheduleRefresh = () => {
      if (realtimeRefreshTimer.current !== null) window.clearTimeout(realtimeRefreshTimer.current);
      realtimeRefreshTimer.current = window.setTimeout(() => {
        realtimeRefreshTimer.current = null;
        void refresh();
      }, 150);
    };
    const unsubscribe = subscribeRealtime(event => {
      if (event.type === "SLOTS_CHANGED") scheduleRefresh();
    }, { onConnectionChange: setRealtimeState });

    // Polling is retained as the fallback when WebSocket reconnects after sleep or network changes.
    const fallback = window.setInterval(() => { void refresh(); }, 5_000);
    window.addEventListener("focus", scheduleRefresh);
    return () => {
      unsubscribe();
      window.clearInterval(fallback);
      window.removeEventListener("focus", scheduleRefresh);
      if (realtimeRefreshTimer.current !== null) window.clearTimeout(realtimeRefreshTimer.current);
      if (liveHighlightTimer.current !== null) window.clearTimeout(liveHighlightTimer.current);
    };
  }, [loadQueue, loadReminders]);

  async function search() {
    const searchTerm = query.trim();
    setSearchAttempted(true);
    if (searchTerm.length < 2) {
      setSearchError("Nhập ít nhất 2 ký tự để tìm bệnh nhân.");
      return;
    }
    setSearchLoading(true);
    try {
      setSearchError("");
      const page = await request<PatientPage>(`/patients?query=${encodeURIComponent(searchTerm)}`, token);
      const results = page.content || [];
      setSearchResults(results);
      setLastSearchTerm(searchTerm);
      setSelectedPatientId("");
      setPatients(current => [...new Map([...current, ...results].map(item => [item.id, item])).values()]);
    } catch (cause) {
      // Keep the last successful result set visible when the network is interrupted.
      setSearchError(toBookingIssue(cause).detail);
    } finally {
      setSearchLoading(false);
    }
  }

  function clearSearch() {
    setQuery("");
    setLastSearchTerm("");
    setSearchResults([]);
    setSelectedPatientId("");
    setSearchAttempted(false);
    setSearchError("");
  }

  function openSupport(patient: Patient) {
    sessionStorage.setItem("reception-support-patient", patient.identityId);
    window.dispatchEvent(new CustomEvent("open-support-chat", { detail: { patientIdentityId: patient.identityId } }));
  }

  async function runAppointmentAction(
    id: string,
    action: () => Promise<unknown>,
    successMessage: string,
    refreshWhenAlreadyHandled = false,
  ) {
    setBusyAppointmentId(id);
    setNotice("");
    setActionError("");
    setActionErrorAppointmentId("");
    try {
      await action();
      setNotice(successMessage);
      await Promise.all([loadQueue(), loadReminders()]);
    } catch (cause) {
      if (refreshWhenAlreadyHandled && isAppointmentAlreadyHandledError(cause)) {
        setNotice(APPOINTMENT_ALREADY_HANDLED_MESSAGE);
        await Promise.all([loadQueue(), loadReminders()]);
        return;
      }
      setActionError((cause as Error).message);
      setActionErrorAppointmentId(id);
      throw cause;
    } finally {
      setBusyAppointmentId("");
    }
  }

  async function confirmAppointment(id: string) {
    return runAppointmentAction(
      id,
      () => request(`/appointments/${id}/confirm`, token, { method: "POST" }),
      "Đã xác nhận lịch và cập nhật danh sách vận hành.",
      true,
    );
  }

  async function noShow(id: string) {
    return runAppointmentAction(
      id,
      () => request(`/appointments/${id}/no-show`, token, { method: "POST" }),
      "Đã ghi nhận bệnh nhân vắng mặt.",
    );
  }

  async function checkIn(id: string) {
    return runAppointmentAction(
      id,
      () => request(`/appointments/${id}/check-in`, token, { method: "POST" }),
      "Đã xác nhận bệnh nhân có mặt và chuyển sang chờ khám.",
    );
  }

  async function remind(id: string, action: ReminderAction["actionType"]) {
    const successMessage = action === "CALLED"
      ? "Đã lưu trạng thái gọi xác nhận."
      : action === "RESENT"
        ? "Đã gửi thông báo nhắc lại cho bệnh nhân."
        : "Đã lưu trạng thái không liên lạc được.";
    return runAppointmentAction(
      id,
      () => request(`/appointments/${id}/reminder-actions`, token, {
        method: "POST",
        body: JSON.stringify({ action }),
      }),
      successMessage,
    );
  }

  const patientName = (appointment: Appointment) => patients.find(patient => patient.id === appointment.patientId)?.fullName || "Chưa tải được tên bệnh nhân";
  const doctorName = (appointment: Appointment) => appointment.doctorId
    ? doctors.find(doctor => doctor.id === appointment.doctorId)?.fullName || appointment.doctorName || "Bác sĩ đã chọn"
    : "Chưa phân công";

  return <ReceptionDashboard
    token={token}
    appointments={appointments}
    reminders={reminders}
    searchResults={searchResults}
    selectedPatientId={selectedPatientId}
    query={query}
    lastSearchTerm={lastSearchTerm}
    queueLoading={queueLoading}
    queueError={queueError}
    reminderLoading={reminderLoading}
    reminderError={reminderError}
    searchLoading={searchLoading}
    searchAttempted={searchAttempted}
    searchError={searchError}
    notice={actionError || notice}
    noticeError={Boolean(actionError)}
    busyAppointmentId={busyAppointmentId}
    realtimeState={realtimeState}
    lastSyncedAt={lastSyncedAt}
    liveRevision={liveRevision}
    changedAppointmentIds={changedAppointmentIds}
    actionErrorAppointmentId={actionErrorAppointmentId}
    patientName={patientName}
    doctorName={doctorName}
    onQueryChange={setQuery}
    onSearch={search}
    onClearSearch={clearSearch}
    onSelectPatient={setSelectedPatientId}
    onOpenSupport={openSupport}
    onOpenHotline={patient => window.dispatchEvent(new CustomEvent<Patient | undefined>("open-hotline-booking", { detail: patient }))}
    onOpenRequests={() => onNavigate("appointments")}
    onOpenAccepted={() => onNavigate("records")}
    onConfirm={confirmAppointment}
    onCheckIn={checkIn}
    onNoShow={noShow}
    onRemind={remind}
    onRetryQueue={() => loadQueue(true)}
    onRetryReminders={loadReminders}
  />;
}
