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
  consultationFee: number;
};

export type WorkSchedule = { id: string; weekday: number; startTime: string; endTime: string; slotMinutes: number };
export type LeavePeriod = { id: string; startAt: string; endAt: string; reason?: string };
export type Appointment = { id: string; patientId: string; doctorId?: string; doctorIdentityId?: string; doctorName?: string; startAt: string; endAt: string; status: string; reason?: string; followUpReason?: string; followUpNotBefore?: string; holdExpiresAt?: string; checkedInAt?: string; consultationFeeSnapshot?: number; createdAt: string; updatedAt?: string };
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
export type StaffAccount = { identityId: string; displayName?: string; email: string; role: "RECEPTIONIST" | "DOCTOR" | "ADMIN"; status: "ACTIVE" | "LOCKED"; createdAt: string; hasAvatar?: boolean };
export type AccountProfile = { identityId: string; displayName?: string; email: string; role: "PATIENT" | "RECEPTIONIST" | "DOCTOR" | "ADMIN"; status: "PENDING" | "ACTIVE" | "LOCKED" | "DISABLED"; createdAt: string; hasAvatar?: boolean };
export type StaffAccountEvent = { id: string; staffIdentityId: string; actorIdentityId: string; actionType: string; createdAt: string };
export type AppointmentActionLog = { id: string; appointmentId: string; actorIdentityId: string; actorRole: string; actionType: string; createdAt: string };
export type SupportMessage = { id: string; patientIdentityId: string; senderIdentityId: string; senderRole: string; body: string; sentAt: string; readAt?: string };
export type SupportConversation = { patientIdentityId: string; assignedReceptionistIdentityId?: string | null; assignedAt?: string | null; updatedAt: string };
export type StaffDirectoryEntry = { identityId: string; displayName?: string | null; status: "ACTIVE" | "LOCKED" };
export type AiRankedPrediction = { label: string; probability: number };
export type AiCitation = { source: string; page: number };
export type AiDiseaseGuidance = { title: string; answer: string; citations: AiCitation[]; has_evidence: boolean };
export type AiPrediction = { disease: string; confidence: number; top3: AiRankedPrediction[]; gradcam_image: string; model_version: string; uncertain: boolean; disclaimer: string; guidance?: AiDiseaseGuidance };
export type AiAssessment = { id: string; patientId: string; predictedLabel: string; confidence: number; top3: AiRankedPrediction[]; uncertain: boolean; modelVersion: string; sharedWithDoctor: boolean; appointmentId?: string | null; imageAvailable: boolean; createdAt: string };
