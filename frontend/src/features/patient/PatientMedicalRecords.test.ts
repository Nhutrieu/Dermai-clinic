import { describe, expect, it } from "vitest";
import type { Appointment, MedicalRecord, Prescription } from "../../core/types";
import { buildPatientRecordEntries, isAiSupportedReason, isPatientRecordComplete } from "./PatientMedicalRecords";

const record = (id: string, appointmentId: string, signedAt: string): MedicalRecord => ({
    id,
    appointmentId,
    patientId: "patient-1",
    finalDiagnosis: `Chẩn đoán ${id}`,
    severity: "MILD",
    signedAt,
});

const appointment = (id: string, startAt: string): Appointment => ({
    id,
    patientId: "patient-1",
    startAt,
    endAt: new Date(new Date(startAt).getTime() + 30 * 60_000).toISOString(),
    status: "COMPLETED",
    createdAt: startAt,
});

const prescription = (id: string, recordId: string): Prescription => ({
    id,
    recordId,
    patientId: "patient-1",
    signedAt: "2026-08-01T04:00:00.000Z",
    items: [{ drugName: "Thuốc A", dosage: "Theo đơn" }],
});

describe("patient medical record presentation", () => {
    it("links appointments and prescriptions, then sorts visits newest first", () => {
        const entries = buildPatientRecordEntries(
            [
                record("record-old", "appointment-old", "2026-06-01T03:00:00.000Z"),
                record("record-new", "appointment-new", "2026-07-01T03:00:00.000Z"),
            ],
            [
                appointment("appointment-old", "2026-06-01T02:00:00.000Z"),
                appointment("appointment-new", "2026-07-01T02:00:00.000Z"),
            ],
            [prescription("rx-new", "record-new")],
        );

        expect(entries.map(entry => entry.record.id)).toEqual(["record-new", "record-old"]);
        expect(entries[0].appointment?.id).toBe("appointment-new");
        expect(entries[0].prescription?.id).toBe("rx-new");
        expect(entries[1].prescription).toBeUndefined();
    });

    it("keeps AI support text separate from patient symptom text", () => {
        expect(isAiSupportedReason("Kết quả kiểm tra da bằng AI (tham khảo): Acne 80%")).toBe(true);
        expect(isAiSupportedReason("Ngứa da trong ba ngày")).toBe(false);
    });

    it("marks an in-progress visit as updating even after the doctor signs the record", () => {
        const updatingAppointment = { ...appointment("appointment-1", "2026-08-01T02:00:00.000Z"), status: "IN_PROGRESS" };
        const completedAppointment = { ...updatingAppointment, status: "COMPLETED" };
        const signedRecord = record("record-1", "appointment-1", "2026-08-01T03:00:00.000Z");

        expect(isPatientRecordComplete({ record: signedRecord, appointment: updatingAppointment })).toBe(false);
        expect(isPatientRecordComplete({ record: signedRecord, appointment: completedAppointment })).toBe(true);
    });
});
