import type { Appointment, ReminderItem } from "../../core/types";

export const CLINIC_TIME_ZONE = "Asia/Ho_Chi_Minh";

export type ReceptionStatusTone =
  | "pending"
  | "assigned"
  | "confirmed"
  | "progress"
  | "completed"
  | "followup"
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

export function getReceptionStatus(status: string): ReceptionStatus {
  switch (status) {
    case "PENDING":
      return { label: "Chờ tiếp nhận", tone: "pending" };
    case "ASSIGNED":
      return { label: "Đã xếp bác sĩ", tone: "assigned" };
    case "CONFIRMED":
      return { label: "Đã xác nhận", tone: "confirmed" };
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

export function buildReceptionSummary(appointments: Appointment[], now = new Date()): ReceptionSummary {
  const today = appointments.filter(item => isClinicToday(item, now));
  return {
    total: today.length,
    pending: today.filter(item => ["PENDING", "ASSIGNED"].includes(item.status)).length,
    confirmed: today.filter(item => item.status === "CONFIRMED").length,
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
