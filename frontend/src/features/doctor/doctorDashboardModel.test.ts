import { describe, expect, it } from "vitest";
import type { Appointment } from "../../core/types";
import { buildDoctorTodaySummary, getStaleConsultationTasks, isStaleConsultation } from "./doctorDashboardModel";

function appointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: "appointment-1",
    patientId: "patient-1",
    startAt: "2026-08-09T01:00:00.000Z",
    endAt: "2026-08-09T01:30:00.000Z",
    status: "IN_PROGRESS",
    createdAt: "2026-08-01T01:00:00.000Z",
    ...overrides,
  };
}

describe("doctor dashboard stale consultations", () => {
  it("waits for the full one-hour grace period", () => {
    const visit = appointment();
    expect(isStaleConsultation(visit, new Date("2026-08-09T02:29:59.000Z"))).toBe(false);
    expect(isStaleConsultation(visit, new Date("2026-08-09T02:30:00.000Z"))).toBe(true);
  });

  it("counts and exposes only stale in-progress visits for completion", () => {
    const now = new Date("2026-08-09T03:00:00.000Z");
    const stale = appointment();
    const stillRunning = appointment({ id: "appointment-2", endAt: "2026-08-09T02:30:00.000Z" });
    const summary = buildDoctorTodaySummary([stale, stillRunning], [], now);

    expect(summary.needsAttention).toBe(1);
    expect(getStaleConsultationTasks([stale, stillRunning], now).map(item => item.appointment.id)).toEqual([stale.id]);
  });
});
