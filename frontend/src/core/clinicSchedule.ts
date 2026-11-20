import type { WorkSchedule } from "./types";

export type ClinicDay = { weekday: number; open: boolean; startTime: string; endTime: string };
export type ClinicSchedule = { days: ClinicDay[]; configured: boolean };

export function effectiveDoctorSchedules(clinic: ClinicSchedule, legacy: WorkSchedule[]): WorkSchedule[] {
  if (!clinic.configured) return legacy;
  return clinic.days.filter(day => day.open).map(day => ({
    id: `clinic-${day.weekday}`,
    weekday: day.weekday,
    startTime: day.startTime,
    endTime: day.endTime,
    slotMinutes: 30,
  }));
}
