import { describe, expect, it } from "vitest";
import type { Appointment, Patient } from "../../core/types";
import {
  duplicatePatientNameIds,
  maskPatientPhone,
  nextPatientAppointment,
  patientRecordCode,
  splitPatientAppointments,
} from "./receptionPatientModel";

const patients: Patient[] = [
  { id: "aaa11111-0000", identityId: "identity-1", fullName: "Nguyễn An", phone: "0352790904" },
  { id: "bbb22222-0000", identityId: "identity-2", fullName: " nguyễn an ", phone: "0901234567" },
  { id: "ccc33333-0000", identityId: "identity-3", fullName: "Trần Bình" },
];

function appointment(id: string, patientId: string, status: string, startAt: string): Appointment {
  const start = new Date(startAt);
  return {
    id,
    patientId,
    doctorId: "doctor-1",
    startAt,
    endAt: new Date(start.getTime() + 30 * 60_000).toISOString(),
    status,
    createdAt: startAt,
  };
}

describe("reception patient model", () => {
  it("masks list phone numbers while preserving useful identity hints", () => {
    expect(maskPatientPhone("0352790904")).toBe("035 *** 904");
    expect(maskPatientPhone()).toBe("Chưa có số điện thoại");
    expect(patientRecordCode("aaa11111-0000")).toBe("11110000");
  });

  it("detects duplicate Vietnamese names without selecting either record", () => {
    expect([...duplicatePatientNameIds(patients)].sort()).toEqual(["aaa11111-0000", "bbb22222-0000"]);
  });

  it("separates active appointments from final history and keeps each order honest", () => {
    const items = [
      appointment("cancelled", patients[0].id, "CANCELLED", "2026-07-01T02:00:00.000Z"),
      appointment("confirmed-later", patients[0].id, "CONFIRMED", "2026-09-02T02:00:00.000Z"),
      appointment("completed", patients[0].id, "COMPLETED", "2026-08-01T02:00:00.000Z"),
      appointment("confirmed-first", patients[0].id, "CONFIRMED", "2026-08-05T02:00:00.000Z"),
    ];
    const result = splitPatientAppointments(items);
    expect(result.upcoming.map(item => item.id)).toEqual(["confirmed-first", "confirmed-later"]);
    expect(result.history.map(item => item.id)).toEqual(["completed", "cancelled"]);
    expect(nextPatientAppointment(items, patients[0].id, new Date("2026-08-02T00:00:00.000Z"))?.id).toBe("confirmed-first");
  });
});
