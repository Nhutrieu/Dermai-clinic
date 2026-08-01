// Patients may self-manage only while reception has not confirmed the appointment.
export const PATIENT_APPOINTMENT_SELF_SERVICE_WINDOW_MS = 30 * 60_000;
const PATIENT_SELF_SERVICE_STATUSES = new Set(["PENDING", "ASSIGNED"]);

export function patientAppointmentSelfServiceClosesAt(createdAt: string) {
    const createdAtMs = new Date(createdAt).getTime();
    return Number.isFinite(createdAtMs)
        ? createdAtMs + PATIENT_APPOINTMENT_SELF_SERVICE_WINDOW_MS
        : Number.NaN;
}

export function canPatientSelfManageAppointment(status: string, createdAt: string, now = Date.now()) {
    if (!PATIENT_SELF_SERVICE_STATUSES.has(status)) return false;
    const closesAt = patientAppointmentSelfServiceClosesAt(createdAt);
    return Number.isFinite(closesAt) && now <= closesAt;
}
