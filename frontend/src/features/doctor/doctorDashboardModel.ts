import type { Appointment, MedicalRecord, WorkSchedule } from "../../core/types";

export const CLINIC_TIME_ZONE = "Asia/Ho_Chi_Minh";

export type DoctorStatusTone = "confirmed" | "arrived" | "progress" | "completed" | "followup" | "attention" | "neutral";

export type DoctorStatus = {
  label: string;
  tone: DoctorStatusTone;
};

export type DoctorTodaySummary = {
  total: number;
  waiting: number;
  inProgress: number;
  completed: number;
  notStarted: number;
  needsAttention: number;
};

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

export function getDoctorStatus(status: string, startAt?: string, now = new Date()): DoctorStatus {
  if (status === "CONFIRMED" && startAt && new Date(startAt).getTime() < now.getTime()) {
    return { label: "Đã qua giờ hẹn", tone: "attention" };
  }
  switch (status) {
    case "CONFIRMED":
      return { label: "Chờ bắt đầu", tone: "confirmed" };
    case "CHECKED_IN":
      return { label: "Bệnh nhân đã đến", tone: "arrived" };
    case "IN_PROGRESS":
      return { label: "Đang khám", tone: "progress" };
    case "COMPLETED":
      return { label: "Hoàn tất", tone: "completed" };
    case "FOLLOW_UP_REQUIRED":
      return { label: "Cần tái khám", tone: "followup" };
    default:
      return { label: "Chưa xác định", tone: "neutral" };
  }
}

export function getTodayAppointments(appointments: Appointment[], now = new Date()): Appointment[] {
  return appointments
    .filter(item => isClinicToday(item, now))
    .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime());
}

export function getNextPatient(appointments: Appointment[], now = new Date()): Appointment | undefined {
  const today = getTodayAppointments(appointments, now);
  // Patients checked in at reception take priority over merely confirmed visits.
  const arrived = today.filter(item => item.status === "CHECKED_IN");
  if (arrived.length) return arrived[0];
  const confirmed = today.filter(item => item.status === "CONFIRMED");
  return confirmed.find(item => new Date(item.startAt).getTime() >= now.getTime()) ?? confirmed[0];
}

export function getActiveConsultations(appointments: Appointment[]): Appointment[] {
  return appointments
    .filter(item => item.status === "IN_PROGRESS")
    .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime());
}

export function buildDoctorTodaySummary(
  appointments: Appointment[],
  records: MedicalRecord[],
  now = new Date(),
): DoctorTodaySummary {
  const today = getTodayAppointments(appointments, now);
  const recordAppointments = new Set(records.map(item => item.appointmentId));
  const overdue = today.filter(item => item.status === "CONFIRMED" && new Date(item.startAt).getTime() < now.getTime()).length;
  const incomplete = today.filter(item => item.status === "IN_PROGRESS" && !recordAppointments.has(item.id)).length;
  return {
    total: today.length,
    waiting: today.filter(item => ["CONFIRMED", "CHECKED_IN"].includes(item.status)).length,
    inProgress: today.filter(item => item.status === "IN_PROGRESS").length,
    completed: today.filter(item => ["COMPLETED", "FOLLOW_UP_REQUIRED"].includes(item.status)).length,
    notStarted: today.filter(item => item.status === "CONFIRMED" && new Date(item.startAt).getTime() >= now.getTime()).length,
    needsAttention: overdue + incomplete,
  };
}

export function getIncompleteClinicalTasks(
  appointments: Appointment[],
  records: MedicalRecord[],
): { appointment: Appointment; label: string }[] {
  const recordAppointments = new Set(records.map(item => item.appointmentId));
  return getActiveConsultations(appointments).map(appointment => ({
    appointment,
    label: recordAppointments.has(appointment.id) ? "Hoàn tất ca khám" : "Hoàn tất hồ sơ khám",
  }));
}

export function getTodayShift(work: WorkSchedule[], now = new Date()): WorkSchedule | undefined {
  const weekday = Number(new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
  }).format(now) === "Sun" ? 7 : new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
  }).format(now) === "Mon" ? 1 : new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
  }).format(now) === "Tue" ? 2 : new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
  }).format(now) === "Wed" ? 3 : new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
  }).format(now) === "Thu" ? 4 : new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
  }).format(now) === "Fri" ? 5 : 6);
  return work.find(item => item.weekday === weekday);
}

export function formatClinicTime(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: CLINIC_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function formatDurationFrom(startAt: string, now = new Date()): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(startAt).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} phút`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} giờ ${remainder} phút` : `${hours} giờ`;
}
