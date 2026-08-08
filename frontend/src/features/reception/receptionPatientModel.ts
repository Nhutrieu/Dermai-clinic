import type { Appointment, Patient } from "../../core/types";

const ACTIVE_APPOINTMENT_STATUSES = new Set([
  "PENDING",
  "ASSIGNED",
  "PROPOSED",
  "CONFIRMED",
  "CHECKED_IN",
  "IN_PROGRESS",
]);

export function patientRecordCode(patientId: string) {
  const compact = patientId.replace(/[^a-zA-Z0-9]/g, "");
  return compact.slice(-8).toUpperCase();
}

export function maskPatientPhone(phone?: string) {
  if (!phone) return "Chưa có số điện thoại";
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 7) return phone;
  return `${digits.slice(0, 3)} *** ${digits.slice(-3)}`;
}

export function duplicatePatientNameIds(patients: Patient[]) {
  const counts = new Map<string, number>();
  patients.forEach(patient => {
    const key = patient.fullName.trim().toLocaleLowerCase("vi-VN");
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return new Set(
    patients
      .filter(patient => counts.get(patient.fullName.trim().toLocaleLowerCase("vi-VN"))! > 1)
      .map(patient => patient.id),
  );
}

export function splitPatientAppointments(appointments: Appointment[]) {
  const upcoming = appointments
    .filter(appointment => ACTIVE_APPOINTMENT_STATUSES.has(appointment.status))
    .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime());
  const history = appointments
    .filter(appointment => !ACTIVE_APPOINTMENT_STATUSES.has(appointment.status))
    .sort((left, right) => new Date(right.startAt).getTime() - new Date(left.startAt).getTime());
  return { upcoming, history };
}

export function nextPatientAppointment(appointments: Appointment[], patientId: string, now = new Date()) {
  return appointments
    .filter(appointment => appointment.patientId === patientId)
    .filter(appointment => ACTIVE_APPOINTMENT_STATUSES.has(appointment.status))
    .filter(appointment => new Date(appointment.endAt).getTime() >= now.getTime())
    .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime())[0];
}
