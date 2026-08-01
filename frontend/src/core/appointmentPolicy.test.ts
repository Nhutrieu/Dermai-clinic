import { describe, expect, it } from "vitest";
import {
    canPatientSelfManageAppointment,
    PATIENT_APPOINTMENT_SELF_SERVICE_WINDOW_MS,
} from "./appointmentPolicy";

describe("patient appointment self-service policy", () => {
    const createdAt = "2026-08-01T01:00:00.000Z";
    const createdAtMs = new Date(createdAt).getTime();

    it("allows a pending appointment during the first 30 minutes", () => {
        expect(canPatientSelfManageAppointment(
            "PENDING",
            createdAt,
            createdAtMs + PATIENT_APPOINTMENT_SELF_SERVICE_WINDOW_MS,
        )).toBe(true);
    });

    it("allows an assigned appointment before reception confirms it", () => {
        expect(canPatientSelfManageAppointment("ASSIGNED", createdAt, createdAtMs + 5 * 60_000)).toBe(true);
    });

    it("requires support immediately after reception confirms it", () => {
        expect(canPatientSelfManageAppointment("CONFIRMED", createdAt, createdAtMs + 5 * 60_000)).toBe(false);
    });

    it("requires receptionist support after 30 minutes", () => {
        expect(canPatientSelfManageAppointment(
            "PENDING",
            createdAt,
            createdAtMs + PATIENT_APPOINTMENT_SELF_SERVICE_WINDOW_MS + 1,
        )).toBe(false);
    });

    it("fails closed when the server date is invalid", () => {
        expect(canPatientSelfManageAppointment("PENDING", "invalid-date", createdAtMs)).toBe(false);
    });
});
