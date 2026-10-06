import { describe, expect, it } from "vitest";
import type { Appointment } from "../../core/types";
import {
  buildDoctorTodaySummary,
  getNextPatient,
  getStaleConsultationTasks,
  getWaitingQueue,
  isStaleConsultation,
} from "./doctorDashboardModel";

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

describe("doctor waiting queue", () => {
  const now = new Date("2026-08-09T02:00:00.000Z");

  it("orders waiting patients by appointment time, regardless of check-in status", () => {
    const laterButArrived = appointment({
      id: "later-arrived",
      status: "CHECKED_IN",
      startAt: "2026-08-09T03:00:00.000Z",
      endAt: "2026-08-09T03:30:00.000Z",
    });
    const earlierConfirmed = appointment({
      id: "earlier-confirmed",
      status: "CONFIRMED",
      startAt: "2026-08-09T02:30:00.000Z",
      endAt: "2026-08-09T03:00:00.000Z",
    });

    expect(getWaitingQueue([laterButArrived, earlierConfirmed], now).map(item => item.id)).toEqual([
      "earlier-confirmed",
      "later-arrived",
    ]);
    expect(getNextPatient([laterButArrived, earlierConfirmed], now)?.id).toBe("earlier-confirmed");
  });

  it("uses booking creation time as a stable tie-breaker and excludes non-waiting visits", () => {
    const bookedLater = appointment({
      id: "booked-later",
      status: "CHECKED_IN",
      startAt: "2026-08-09T03:00:00.000Z",
      endAt: "2026-08-09T03:30:00.000Z",
      createdAt: "2026-08-02T01:00:00.000Z",
    });
    const bookedEarlier = appointment({
      id: "booked-earlier",
      status: "CONFIRMED",
      startAt: "2026-08-09T03:00:00.000Z",
      endAt: "2026-08-09T03:30:00.000Z",
      createdAt: "2026-08-01T01:00:00.000Z",
    });
    const inProgress = appointment({ id: "in-progress" });

    expect(getWaitingQueue([bookedLater, inProgress, bookedEarlier], now).map(item => item.id)).toEqual([
      "booked-earlier",
      "booked-later",
    ]);
  });
});
