import { useMemo } from "react";
import {
  AlertTriangle,
  CalendarClock,
  PhoneCall,
} from "lucide-react";
import type { RealtimeConnectionState } from "../../core/realtime";
import type { Appointment, Patient, ReminderAction, ReminderItem } from "../../core/types";
import { getAttentionAppointments } from "./receptionDashboardModel";
import ReceptionPatientLookup from "./ReceptionPatientLookup";
import ReceptionQueueBoard from "./ReceptionQueueBoard";

type Props = {
  token: string;
  appointments: Appointment[];
  reminders: ReminderItem[];
  searchResults: Patient[];
  selectedPatientId: string;
  query: string;
  lastSearchTerm: string;
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
  changedAppointmentIds: string[];
  actionErrorAppointmentId: string;
  patientName: (appointment: Appointment) => string;
  doctorName: (appointment: Appointment) => string;
  onQueryChange: (value: string) => void;
  onSearch: () => Promise<void>;
  onClearSearch: () => void;
  onSelectPatient: (patientId: string) => void;
  onOpenSupport: (patient: Patient) => void;
  onOpenHotline: (patient?: Patient) => void;
  onOpenRequests: () => void;
  onOpenAccepted: () => void;
  onConfirm: (appointmentId: string) => Promise<void>;
  onCheckIn: (appointmentId: string) => Promise<void>;
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

export default function ReceptionDashboard(props: Props) {
  const attentionAppointments = useMemo(
    () => getAttentionAppointments(props.appointments, props.reminders),
    [props.appointments, props.reminders],
  );
  const incomingAttentionCount = attentionAppointments.filter(item => ["PENDING", "ASSIGNED"].includes(item.status)).length;

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
          <button type="button" className="reception-button-primary" onClick={() => props.onOpenHotline()}>
            <PhoneCall />
            Đặt lịch hotline
          </button>
        </div>
      </section>

      {props.notice && <div className={`reception-notice ${props.noticeError ? "is-error" : ""}`} role={props.noticeError ? "alert" : "status"} aria-live={props.noticeError ? "assertive" : "polite"}>{props.notice}</div>}

      <ReceptionPatientLookup
        token={props.token}
        appointments={props.appointments}
        searchResults={props.searchResults}
        selectedPatientId={props.selectedPatientId}
        query={props.query}
        lastSearchTerm={props.lastSearchTerm}
        searchLoading={props.searchLoading}
        searchAttempted={props.searchAttempted}
        searchError={props.searchError}
        doctorName={props.doctorName}
        onQueryChange={props.onQueryChange}
        onSearch={props.onSearch}
        onClearSearch={props.onClearSearch}
        onSelectPatient={props.onSelectPatient}
        onOpenSupport={props.onOpenSupport}
        onOpenHotline={props.onOpenHotline}
      />

      <ReceptionQueueBoard
        appointments={props.appointments}
        reminders={props.reminders}
        queueLoading={props.queueLoading}
        queueError={props.queueError}
        actionError={props.noticeError ? props.notice : ""}
        actionErrorAppointmentId={props.actionErrorAppointmentId}
        busyAppointmentId={props.busyAppointmentId}
        realtimeState={props.realtimeState}
        lastSyncedAt={props.lastSyncedAt}
        liveRevision={props.liveRevision}
        changedAppointmentIds={props.changedAppointmentIds}
        patientName={props.patientName}
        doctorName={props.doctorName}
        onOpenRequests={props.onOpenRequests}
        onOpenAccepted={props.onOpenAccepted}
        onConfirm={props.onConfirm}
        onCheckIn={props.onCheckIn}
        onNoShow={props.onNoShow}
        onRetryQueue={props.onRetryQueue}
      />

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

    </div>
  );
}
