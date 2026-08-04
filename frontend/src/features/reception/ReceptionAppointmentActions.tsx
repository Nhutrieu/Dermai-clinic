import { useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, Info, Trash2 } from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import { request } from "../../core/api";
import type { Appointment, Recommendation, RecommendationResult } from "../../core/types";
import {
  type BookingIssue,
  formatReceptionDateTime,
  toBookingIssue,
} from "./receptionBookingModel";

type AppointmentContext = {
  appointment: Appointment;
  patientName: string;
  doctorName: string;
};

function appointmentDurationMinutes(appointment: Appointment) {
  return Math.max(1, Math.round(
    (new Date(appointment.endAt).getTime() - new Date(appointment.startAt).getTime()) / 60_000,
  ));
}

function localDateTimeInput(value: string) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function appointmentStatusLabel(status: string) {
  switch (status) {
    case "PENDING": return "Chờ xử lý";
    case "ASSIGNED": return "Đã phân công";
    case "CONFIRMED": return "Đã xác nhận";
    case "CANCELLED": return "Đã hủy";
    default: return status;
  }
}

function AppointmentContextSummary({ appointment, patientName, doctorName }: AppointmentContext) {
  return (
    <dl className="reception-action-context">
      <div><dt>Bệnh nhân</dt><dd>{patientName}</dd></div>
      <div><dt>Bác sĩ</dt><dd>{doctorName.startsWith("Chưa") ? doctorName : `BS. ${doctorName}`}</dd></div>
      <div><dt>Thời gian hiện tại</dt><dd>{formatReceptionDateTime(appointment.startAt)}</dd></div>
      <div><dt>Trạng thái</dt><dd>{appointmentStatusLabel(appointment.status)}</dd></div>
    </dl>
  );
}

export function NotificationDeliveryStatus() {
  return (
    <div className="reception-notification-status" role="status">
      <Info aria-hidden="true" />
      <span>Lịch đã cập nhật. Hệ thống chưa trả trạng thái gửi email hoặc SMS cho thao tác này.</span>
    </div>
  );
}

export function BookingConflictDialog({
  issue,
  onClose,
  onChooseAnother,
  primaryLabel = "Chọn giờ khác",
}: {
  issue: BookingIssue;
  onClose: () => void;
  onChooseAnother: () => void;
  primaryLabel?: string;
}) {
  return (
    <AccessibleDialog
      title={issue.title}
      titleId="reception-booking-conflict-title"
      descriptionId="reception-booking-conflict-description"
      role="alertdialog"
      tone="danger"
      icon={<AlertTriangle />}
      onClose={onClose}
      footer={(
        <>
          <button type="button" onClick={onClose}>Đóng</button>
          <button
            type="button"
            className="booking-dialog-primary"
            data-dialog-initial-focus
            onClick={onChooseAnother}
          >
            {primaryLabel}
          </button>
        </>
      )}
    >
      <p>{issue.detail}</p>
      <p><strong>Hướng xử lý:</strong> {issue.action}</p>
      <p className="booking-dialog-note">Các thông tin bệnh nhân và lý do khám vẫn được giữ nguyên.</p>
    </AccessibleDialog>
  );
}

export function ReceptionRescheduleControl({
  token,
  appointment,
  patientName,
  doctorName,
  submit,
  onSuccess,
}: AppointmentContext & {
  token: string;
  submit: (value: string) => Promise<Appointment>;
  onSuccess?: (appointment: Appointment) => void;
}) {
  const [open, setOpen] = useState(false);
  const [preferredAt, setPreferredAt] = useState(() => localDateTimeInput(appointment.startAt));
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState<BookingIssue | null>(null);
  const [success, setSuccess] = useState<Appointment | null>(null);

  async function findSlots() {
    if (!preferredAt || !appointment.doctorId) return;
    setSearching(true);
    setError("");
    setSelected(null);
    setRecommendations([]);
    try {
      const result = await request<RecommendationResult>("/appointments/recommendations", token, {
        method: "POST",
        body: JSON.stringify({
          patientId: appointment.patientId,
          preferredDoctorId: appointment.doctorId,
          preferredStart: new Date(preferredAt).toISOString(),
          durationMinutes: appointmentDurationMinutes(appointment),
          limit: 5,
        }),
      });
      setRecommendations(result.items);
      if (!result.items.length) {
        setError("Không tìm thấy giờ phù hợp trong 7 ngày từ thời gian mong muốn.");
      }
    } catch (cause) {
      const issue = toBookingIssue(cause);
      setError(issue.detail);
    } finally {
      setSearching(false);
    }
  }

  async function confirmReschedule() {
    if (!selected || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const updated = await submit(selected.startAt);
      setSuccess(updated);
    } catch (cause) {
      const issue = toBookingIssue(cause);
      if (issue.conflict) setConflict(issue);
      else setError(issue.detail);
    } finally {
      setSubmitting(false);
    }
  }

  function close() {
    if (submitting) return;
    const completed = success;
    setOpen(false);
    setSuccess(null);
    setConflict(null);
    setError("");
    setSelected(null);
    setRecommendations([]);
    if (completed) onSuccess?.(completed);
  }

  return (
    <>
      <button type="button" className="reception-row-action" onClick={() => setOpen(true)}>
        <CalendarClock aria-hidden="true" />
        Đổi lịch
      </button>
      {open && (
        <AccessibleDialog
          title={success ? "Đổi lịch thành công" : "Đổi lịch khám"}
          titleId={`reception-reschedule-title-${appointment.id}`}
          descriptionId={`reception-reschedule-description-${appointment.id}`}
          tone={success ? "success" : "neutral"}
          icon={success ? <CheckCircle2 /> : <CalendarClock />}
          className="reception-action-dialog"
          closeOnBackdrop={!submitting}
          onClose={close}
          footer={success ? (
            <button type="button" className="booking-dialog-primary" onClick={close}>Đóng</button>
          ) : (
            <>
              <button type="button" data-dialog-initial-focus onClick={close}>Giữ lịch hiện tại</button>
              <button
                type="button"
                className="booking-dialog-primary"
                disabled={!selected || submitting}
                onClick={() => void confirmReschedule()}
              >
                {submitting ? "Đang đổi lịch..." : "Xác nhận đổi lịch"}
              </button>
            </>
          )}
        >
          {success ? (
            <div className="reception-action-success" aria-live="polite">
              <p>Lịch mới đã được hệ thống xác nhận. Lịch cũ đã được cập nhật theo quy trình hiện có.</p>
              <dl>
                <div><dt>Bệnh nhân</dt><dd>{patientName}</dd></div>
                <div><dt>Bác sĩ</dt><dd>BS. {doctorName}</dd></div>
                <div><dt>Thời gian mới</dt><dd>{formatReceptionDateTime(success.startAt)}</dd></div>
              </dl>
              <NotificationDeliveryStatus />
            </div>
          ) : (
            <>
              <AppointmentContextSummary
                appointment={appointment}
                patientName={patientName}
                doctorName={doctorName}
              />
              <p className="reception-action-safety">
                Lịch hiện tại chỉ thay đổi sau khi hệ thống xác nhận lịch mới. Lý do khám ban đầu được giữ nguyên.
              </p>
              <div className="reception-action-field">
                <label htmlFor={`reschedule-preferred-${appointment.id}`}>Ngày và giờ mong muốn</label>
                <div>
                  <input
                    id={`reschedule-preferred-${appointment.id}`}
                    type="datetime-local"
                    required
                    min={localDateTimeInput(new Date().toISOString())}
                    value={preferredAt}
                    onChange={event => {
                      setPreferredAt(event.target.value);
                      setRecommendations([]);
                      setSelected(null);
                    }}
                  />
                  <button type="button" disabled={!preferredAt || searching} onClick={() => void findSlots()}>
                    {searching ? "Đang kiểm tra..." : "Tìm giờ phù hợp"}
                  </button>
                </div>
                <small>Hệ thống giữ nguyên bác sĩ hiện tại và kiểm tra lịch làm việc, nghỉ phép cùng xung đột.</small>
              </div>
              {recommendations.length > 0 && (
                <div className="reception-recommendation-list" aria-label="Các giờ có thể đổi">
                  {recommendations.map(slot => (
                    <button
                      key={`${slot.doctorId}-${slot.startAt}`}
                      type="button"
                      className={selected?.startAt === slot.startAt ? "is-selected" : ""}
                      aria-pressed={selected?.startAt === slot.startAt}
                      onClick={() => {
                        setSelected(slot);
                      }}
                    >
                      <strong>{formatReceptionDateTime(slot.startAt)}</strong>
                      <span>{selected?.startAt === slot.startAt ? "Đã chọn" : "Có thể đổi"}</span>
                    </button>
                  ))}
                </div>
              )}
              {selected && (
                <div className="reception-change-preview" role="status">
                  <span>Thời gian mới</span>
                  <strong>{formatReceptionDateTime(selected.startAt)}</strong>
                </div>
              )}
              {error && <div className="reception-action-error" role="alert">{error}</div>}
            </>
          )}
        </AccessibleDialog>
      )}
      {conflict && (
        <BookingConflictDialog
          issue={conflict}
          onClose={() => setConflict(null)}
          onChooseAnother={() => {
            setConflict(null);
            setSelected(null);
            setRecommendations([]);
          }}
        />
      )}
    </>
  );
}

export function ReceptionCancelControl({
  appointment,
  patientName,
  doctorName,
  submit,
  onSuccess,
}: AppointmentContext & {
  submit: (reason: string) => Promise<Appointment>;
  onSuccess?: (appointment: Appointment) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<Appointment | null>(null);

  async function confirmCancel() {
    if (!reason.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const updated = await submit(reason.trim());
      setSuccess(updated);
    } catch (cause) {
      setError(toBookingIssue(cause).detail);
    } finally {
      setSubmitting(false);
    }
  }

  function close() {
    if (submitting) return;
    const completed = success;
    setOpen(false);
    setReason("");
    setError("");
    setSuccess(null);
    if (completed) onSuccess?.(completed);
  }

  return (
    <>
      <button type="button" className="reception-row-action reception-row-action-danger" onClick={() => setOpen(true)}>
        <Trash2 aria-hidden="true" />
        Hủy lịch
      </button>
      {open && (
        <AccessibleDialog
          title={success ? "Đã hủy lịch" : "Xác nhận hủy lịch"}
          titleId={`reception-cancel-title-${appointment.id}`}
          descriptionId={`reception-cancel-description-${appointment.id}`}
          role="alertdialog"
          tone={success ? "success" : "danger"}
          icon={success ? <CheckCircle2 /> : <Trash2 />}
          className="reception-action-dialog reception-cancel-dialog"
          closeOnBackdrop={false}
          onClose={close}
          footer={success ? (
            <button type="button" className="booking-dialog-primary" onClick={close}>Đóng</button>
          ) : (
            <>
              <button type="button" data-dialog-initial-focus onClick={close}>Giữ lịch</button>
              <button
                type="button"
                className="reception-danger-button"
                disabled={!reason.trim() || submitting}
                onClick={() => void confirmCancel()}
              >
                {submitting ? "Đang hủy lịch..." : "Xác nhận hủy lịch"}
              </button>
            </>
          )}
        >
          {success ? (
            <div className="reception-action-success" aria-live="polite">
              <p>Lịch đã được hệ thống xác nhận hủy. Khung giờ được trả lại theo quy trình lịch hẹn hiện có.</p>
              <NotificationDeliveryStatus />
            </div>
          ) : (
            <>
              <AppointmentContextSummary
                appointment={appointment}
                patientName={patientName}
                doctorName={doctorName}
              />
              <p className="reception-action-safety reception-action-safety-danger">
                Sau khi hệ thống xác nhận, lịch này không thể khôi phục bằng thao tác hiện tại.
              </p>
              <div className="reception-action-field">
                <label htmlFor={`cancel-reason-${appointment.id}`}>Lý do hủy <span aria-hidden="true">*</span></label>
                <textarea
                  id={`cancel-reason-${appointment.id}`}
                  required
                  maxLength={500}
                  aria-describedby={`cancel-reason-help-${appointment.id}`}
                  value={reason}
                  onChange={event => setReason(event.target.value)}
                  placeholder="Ví dụ: bệnh nhân yêu cầu hủy qua điện thoại"
                />
                <small id={`cancel-reason-help-${appointment.id}`}>Lý do được lưu cùng thao tác hủy lịch.</small>
              </div>
              {error && <div className="reception-action-error" role="alert">{error}</div>}
            </>
          )}
        </AccessibleDialog>
      )}
    </>
  );
}
