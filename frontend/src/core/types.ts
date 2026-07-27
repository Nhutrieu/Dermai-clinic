export type Tokens = {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  role: "PATIENT" | "DOCTOR" | "RECEPTIONIST" | "ADMIN";
};

export type Patient = {
  id: string;
  identityId: string;
  fullName: string;
  dob?: string;
  phone?: string;
  medicalHistory?: string;
  allergies?: string;
  accountLinked?: boolean;
};

export type Doctor = {
  id: string;
  identityId: string;
  fullName: string;
  specialtyCode: string;
  experienceYears: number;
  certificateNo?: string;
  avatarUrl?: string;
  bio?: string;
};

export type WorkSchedule = { id: string; weekday: number; startTime: string; endTime: string; slotMinutes: number };
export type LeavePeriod = { id: string; startAt: string; endAt: string; reason?: string };
export type Appointment = { id: string; patientId: string; doctorId?: string; doctorIdentityId?: string; doctorName?: string; startAt: string; endAt: string; status: string; reason?: string; followUpReason?: string; followUpNotBefore?: string; holdExpiresAt?: string; createdAt: string };
export type MedicalRecord = { id: string; appointmentId: string; patientId: string; finalDiagnosis: string; clinicalNotes?: string; treatmentPlan?: string; severity: string; followUpAt?: string; signedAt: string };
export type PrescriptionItem = { drugName: string; dosage?: string; frequency?: string; duration?: string; instructions?: string };
export type Prescription = { id: string; recordId: string; patientId: string; instructions?: string; signedAt: string; items: PrescriptionItem[] };
export type Recommendation = { doctorId: string; doctorIdentityId: string; doctorName: string; specialtyCode: string; startAt: string; endAt: string; score: number; reasons: string[] };
export type AvailabilitySlot = { doctorId: string; doctorIdentityId: string; doctorName: string; specialtyCode: string; startAt: string; endAt: string; status: "AVAILABLE" | "BOOKED" | "ON_LEAVE" | "HELD_BY_YOU" | "HELD_BY_OTHER"; holdId?: string; holdExpiresAt?: string };
export type PatientNotification = { id: string; appointmentId?: string; notificationType: string; title: string; body: string; createdAt: string; readAt?: string };
export type ClinicClosure = { id: string; closureDate: string; reason: string };
export type ReminderAction = { id: string; appointmentId: string; actionType: "CALLED" | "RESENT" | "UNREACHABLE"; createdAt: string };
export type ReminderItem = { appointment: Appointment; latestAction?: ReminderAction };
export type RecommendationResult = { items: Recommendation[]; algorithmVersion: string; timezone: string };
export type ClinicReview = { id: string; appointmentId: string; displayName: string; rating: number; comment: string; status: "PENDING" | "APPROVED" | "HIDDEN"; createdAt: string };
export type SupportMessage = { id: string; patientIdentityId: string; senderIdentityId: string; senderRole: string; body: string; sentAt: string; readAt?: string };
