import { describe, expect, it } from "vitest";
import type { Appointment, ReminderItem } from "../../core/types";
import {
  buildReceptionSummary,
  buildReceptionQueueSummary,
  getAttentionAppointments,
  getOperationalAppointments,
  getReceptionStatus,
  getReceptionQueueState,
  isOverdueForNoShow,
} from "./receptionDashboardModel";

const now = new Date("2026-08-01T03:00:00.000Z");

function appointment(id: string, status: string, startAt: string): Appointment {
  return {
    id,
    patientId: `patient-${id}`,
    startAt,
    endAt: new Date(new Date(startAt).getTime() + 30 * 60_000).toISOString(),
    status,
    reason: "Khám da",
    createdAt: "2026-07-30T00:00:00.000Z",
  };
}

describe("reception dashboard presentation", () => {
  it("maps technical statuses to clear Vietnamese labels", () => {
    expect(getReceptionStatus("NO_SHOW")).toEqual({ label: "Vắng mặt", tone: "cancelled" });
    expect(getReceptionStatus("UNKNOWN")).toEqual({ label: "Chưa xác định", tone: "neutral" });
  });

  it("summarises only appointments on the clinic's current day", () => {
    const items = [
      appointment("1", "ASSIGNED", "2026-08-01T01:00:00.000Z"),
      appointment("2", "CONFIRMED", "2026-08-01T02:00:00.000Z"),
      appointment("3", "IN_PROGRESS", "2026-08-01T02:30:00.000Z"),
      appointment("4", "COMPLETED", "2026-08-01T00:00:00.000Z"),
      appointment("5", "NO_SHOW", "2026-08-01T00:30:00.000Z"),
      appointment("6", "PENDING", "2026-08-02T01:00:00.000Z"),
    ];
    expect(buildReceptionSummary(items, now)).toEqual({
      total: 5,
      pending: 1,
      confirmed: 1,
      inProgress: 1,
      completed: 1,
      closed: 1,
    });
  });

  it("flags only actionable requests, overdue visits and unreachable reminders", () => {
    const assigned = appointment("assigned", "ASSIGNED", "2026-08-02T01:00:00.000Z");
    const overdue = appointment("overdue", "CONFIRMED", "2026-08-01T01:00:00.000Z");
    const upcoming = appointment("upcoming", "CONFIRMED", "2026-08-01T04:00:00.000Z");
    const unreachable = appointment("unreachable", "CONFIRMED", "2026-08-02T04:00:00.000Z");
    const reminders: ReminderItem[] = [{
      appointment: unreachable,
      latestAction: {
        id: "reminder-1",
        appointmentId: unreachable.id,
        actionType: "UNREACHABLE",
        createdAt: now.toISOString(),
      },
    }];
    expect(isOverdueForNoShow(overdue, now)).toBe(true);
    expect(getAttentionAppointments([assigned, overdue, upcoming, unreachable], reminders, now).map(item => item.id))
      .toEqual(["overdue", "assigned", "unreachable"]);
  });

  it("orders today's operational list by appointment time", () => {
    const late = appointment("late", "CONFIRMED", "2026-08-01T05:00:00.000Z");
    const early = appointment("early", "CONFIRMED", "2026-08-01T01:00:00.000Z");
    expect(getOperationalAppointments([late, early], now).map(item => item.id)).toEqual(["early", "late"]);
  });

  it("derives honest time-based queue phases without inventing patient arrival", () => {
    const upcoming = appointment("upcoming", "CONFIRMED", "2026-08-01T04:00:00.000Z");
    const overdue = appointment("overdue", "CONFIRMED", "2026-08-01T02:00:00.000Z");
    const inProgress = appointment("progress", "IN_PROGRESS", "2026-08-01T01:30:00.000Z");
    expect(getReceptionQueueState(upcoming, now).phase).toBe("upcoming");
    expect(getReceptionQueueState(overdue, now)).toMatchObject({ phase: "overdue", label: "Quá giờ hẹn" });
    expect(getReceptionQueueState(inProgress, now).phase).toBe("in_progress");
  });

  it("summarises only states backed by appointment and reminder data", () => {
    const items = [
      appointment("upcoming", "CONFIRMED", "2026-08-01T04:00:00.000Z"),
      appointment("overdue", "CONFIRMED", "2026-08-01T02:00:00.000Z"),
      appointment("progress", "IN_PROGRESS", "2026-08-01T01:30:00.000Z"),
      appointment("complete", "COMPLETED", "2026-08-01T01:00:00.000Z"),
      appointment("absent", "NO_SHOW", "2026-08-01T00:30:00.000Z"),
      appointment("assigned", "ASSIGNED", "2026-08-01T04:30:00.000Z"),
    ];
    expect(buildReceptionQueueSummary(items, [], now)).toEqual({
      upcoming: 1,
      overdue: 1,
      inProgress: 1,
      completed: 1,
      noShow: 1,
      attention: 2,
    });
  });
});
