import type { Appointment, ReminderItem } from "../../core/types";

export const CLINIC_TIME_ZONE = "Asia/Ho_Chi_Minh";

export type ReceptionStatusTone =
  | "pending"
  | "assigned"
  | "confirmed"
  | "arrived"
  | "progress"
  | "completed"
  | "followup"
  | "overdue"
  | "cancelled"
  | "neutral";

export type ReceptionStatus = {
  label: string;
  tone: ReceptionStatusTone;
};

export type ReceptionSummary = {
  total: number;
  pending: number;
  confirmed: number;
  inProgress: number;
  completed: number;
  closed: number;
};

export type ReceptionQueuePhase =
  | "attention"
  | "upcoming"
  | "overdue"
  | "checked_in"
  | "in_progress"
  | "completed"
  | "no_show"
  | "closed";

export type ReceptionQueueState = ReceptionStatus & {
  phase: ReceptionQueuePhase;
  minutesFromStart: number;
};

export type ReceptionQueueSummary = {
  upcoming: number;
  overdue: number;
  checkedIn: number;
  inProgress: number;
  completed: number;
  noShow: number;
  closed: number;
  attention: number;
};

export function getReceptionStatus(status: string): ReceptionStatus {
  switch (status) {
    case "PENDING":
      return { label: "Chờ tiếp nhận", tone: "pending" };
    case "ASSIGNED":
      return { label: "Đã xếp bác sĩ", tone: "assigned" };
    case "CONFIRMED":
      return { label: "Đã xác nhận", tone: "confirmed" };
    case "CHECKED_IN":
      return { label: "Đã đến phòng khám", tone: "arrived" };
    case "IN_PROGRESS":
      return { label: "Đang khám", tone: "progress" };
    case "COMPLETED":
      return { label: "Hoàn tất", tone: "completed" };
    case "FOLLOW_UP_REQUIRED":
      return { label: "Cần tái khám", tone: "followup" };
    case "NO_SHOW":
      return { label: "Vắng mặt", tone: "cancelled" };
    case "CANCELLED":
      return { label: "Đã hủy", tone: "cancelled" };
    case "PROPOSED":
      return { label: "Chờ bệnh nhân xác nhận", tone: "pending" };
    default:
      return { label: "Chưa xác định", tone: "neutral" };
  }
}

export function clinicDateKey(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CLINIC_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function isClinicToday(appointment: Appointment, now = new Date()): boolean {
  return clinicDateKey(appointment.startAt) === clinicDateKey(now);
}

export function isOverdueForNoShow(appointment: Appointment, now = new Date()): boolean {
  if (appointment.status !== "CONFIRMED") return false;
  return new Date(appointment.startAt).getTime() + 30 * 60_000 <= now.getTime();
}

/**
 * Derives the queue phase from persisted status and time. Patient arrival is
 * never inferred from the doctor's action; it is backed by CHECKED_IN.
 */
export function getReceptionQueueState(
  appointment: Appointment,
  now = new Date(),
): ReceptionQueueState {
  const minutesFromStart = Math.max(
    0,
    Math.floor((now.getTime() - new Date(appointment.startAt).getTime()) / 60_000),
  );

  if (["PENDING", "ASSIGNED", "PROPOSED"].includes(appointment.status)) {
    const status = getReceptionStatus(appointment.status);
    return { ...status, phase: "attention", minutesFromStart };
  }
  if (appointment.status === "CONFIRMED") {
    const hasStarted = new Date(appointment.startAt).getTime() <= now.getTime();
    return hasStarted
      ? {
          label: minutesFromStart >= 30 ? "Quá giờ hẹn" : "Đã qua giờ hẹn",
          tone: "overdue",
          phase: "overdue",
          minutesFromStart,
        }
      : {
          label: "Sắp đến",
          tone: "confirmed",
          phase: "upcoming",
          minutesFromStart: 0,
        };
  }
  if (appointment.status === "CHECKED_IN") {
    return { label: "Đã đến phòng khám", tone: "arrived", phase: "checked_in", minutesFromStart };
  }
  if (appointment.status === "IN_PROGRESS") {
    return { label: "Đang khám", tone: "progress", phase: "in_progress", minutesFromStart };
  }
  if (["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(appointment.status)) {
    const status = getReceptionStatus(appointment.status);
    return { ...status, phase: "completed", minutesFromStart };
  }
  if (appointment.status === "NO_SHOW") {
    return { label: "Vắng mặt", tone: "cancelled", phase: "no_show", minutesFromStart };
  }
  const status = getReceptionStatus(appointment.status);
  return { ...status, phase: "closed", minutesFromStart };
}

export function buildReceptionQueueSummary(
  appointments: Appointment[],
  reminders: ReminderItem[],
  now = new Date(),
): ReceptionQueueSummary {
  const today = getOperationalAppointments(appointments, now);
  const states = today.map(item => getReceptionQueueState(item, now));
  const attentionIds = new Set(getAttentionAppointments(appointments, reminders, now).map(item => item.id));
  return {
    upcoming: states.filter(item => item.phase === "upcoming").length,
    overdue: states.filter(item => item.phase === "overdue").length,
    checkedIn: states.filter(item => item.phase === "checked_in").length,
    inProgress: states.filter(item => item.phase === "in_progress").length,
    completed: states.filter(item => item.phase === "completed").length,
    noShow: states.filter(item => item.phase === "no_show").length,
    closed: states.filter(item => item.phase === "closed").length,
    attention: today.filter(item => attentionIds.has(item.id)).length,
  };
}

export function buildReceptionSummary(appointments: Appointment[], now = new Date()): ReceptionSummary {
  const today = appointments.filter(item => isClinicToday(item, now));
  return {
    total: today.length,
    pending: today.filter(item => ["PENDING", "ASSIGNED"].includes(item.status)).length,
    confirmed: today.filter(item => ["CONFIRMED", "CHECKED_IN"].includes(item.status)).length,
    inProgress: today.filter(item => item.status === "IN_PROGRESS").length,
    completed: today.filter(item => ["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(item.status)).length,
    closed: today.filter(item => ["CANCELLED", "NO_SHOW"].includes(item.status)).length,
  };
}

export function getAttentionAppointments(
  appointments: Appointment[],
  reminders: ReminderItem[],
  now = new Date(),
): Appointment[] {
  const unreachableIds = new Set(
    reminders.filter(item => item.latestAction?.actionType === "UNREACHABLE").map(item => item.appointment.id),
  );
  return appointments
    .filter(item =>
      ["PENDING", "ASSIGNED"].includes(item.status)
      || (isClinicToday(item, now) && isOverdueForNoShow(item, now))
      || unreachableIds.has(item.id),
    )
    .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime());
}

export function getOperationalAppointments(appointments: Appointment[], now = new Date()): Appointment[] {
  return appointments
    .filter(item => isClinicToday(item, now))
    .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime());
}
