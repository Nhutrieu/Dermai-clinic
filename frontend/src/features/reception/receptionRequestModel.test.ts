import { describe, expect, it } from "vitest";
import type { Appointment, Patient } from "../../core/types";
import {
  countReceptionRequests,
  filterReceptionRequests,
} from "./receptionRequestModel";

const patients: Patient[] = [
  { id: "patient-1", identityId: "identity-1", fullName: "Nguyễn An", phone: "0352790904" },
  { id: "patient-2", identityId: "identity-2", fullName: "Trần Bình", phone: "0901000002" },
];

function appointment(id: string, patientId: string, status: string, createdAt: string): Appointment {
  return {
    id,
    patientId,
    startAt: "2026-08-08T01:00:00.000Z",
    endAt: "2026-08-08T01:30:00.000Z",
    status,
    reason: "Ngứa da",
    createdAt,
  };
}

const requests = [
  appointment("pending", "patient-1", "PENDING", "2026-08-02T03:00:00.000Z"),
  appointment("assigned", "patient-2", "ASSIGNED", "2026-08-01T03:00:00.000Z"),
  appointment("confirmed", "patient-1", "CONFIRMED", "2026-07-30T03:00:00.000Z"),
  appointment("cancelled", "patient-2", "CANCELLED", "2026-07-20T03:00:00.000Z"),
  appointment("completed", "patient-1", "COMPLETED", "2026-08-02T04:00:00.000Z"),
];

describe("reception request filters", () => {
  it("shows only actionable requests by default and sorts newest first", () => {
    const result = filterReceptionRequests(requests, patients, {
      query: "",
      status: "OPEN",
      sentDate: "ALL",
      sort: "NEWEST",
    }, new Date("2026-08-02T08:00:00.000Z"));
    expect(result.map(item => item.id)).toEqual(["pending", "assigned"]);
  });

  it("searches patient names without accents and phone numbers", () => {
    const byName = filterReceptionRequests(requests, patients, {
      query: "nguyen an",
      status: "ALL",
      sentDate: "ALL",
      sort: "NEWEST",
    });
    const byPhone = filterReceptionRequests(requests, patients, {
      query: "0901000002",
      status: "ALL",
      sentDate: "ALL",
      sort: "NEWEST",
    });
    expect(byName.map(item => item.id)).toEqual(["pending", "confirmed"]);
    expect(byPhone.map(item => item.id)).toEqual(["assigned", "cancelled"]);
  });

  it("uses the sent date filter and keeps technical statuses unchanged", () => {
    const result = filterReceptionRequests(requests, patients, {
      query: "",
      status: "PENDING",
      sentDate: "TODAY",
      sort: "NEWEST",
    }, new Date("2026-08-02T08:00:00.000Z"));
    expect(result.map(item => item.status)).toEqual(["PENDING"]);
    expect(countReceptionRequests(requests)).toEqual({ pending: 1, assigned: 1, confirmed: 1, cancelled: 1 });
  });
});
