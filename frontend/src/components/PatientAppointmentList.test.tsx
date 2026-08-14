import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Appointment } from "../core/types";
import PatientAppointmentList, { canHideAppointmentFromHistory } from "./PatientAppointmentList";

function appointment(id: string, status: string): Appointment {
    return {
        id,
        patientId: "patient-1",
        doctorId: "doctor-1",
        startAt: "2026-08-10T08:30:00.000Z",
        endAt: "2026-08-10T09:00:00.000Z",
        status,
        reason: "Khám da",
        createdAt: "2026-08-01T00:00:00.000Z",
    };
}

describe("patient appointment history", () => {
    it("allows soft deletion only for terminal history statuses", () => {
        expect(["CANCELLED", "COMPLETED", "NO_SHOW"].every(canHideAppointmentFromHistory)).toBe(true);
        expect([
            "PROPOSED", "PENDING", "ASSIGNED", "CONFIRMED", "CHECKED_IN", "IN_PROGRESS", "FOLLOW_UP_REQUIRED"
        ].some(canHideAppointmentFromHistory)).toBe(false);
    });

    it("renders an accessible delete launcher only for terminal rows", () => {
        const html = renderToStaticMarkup(
            <PatientAppointmentList
                token="token"
                patientName="Nguyễn An"
                appointments={[
                    appointment("cancelled", "CANCELLED"),
                    appointment("completed", "COMPLETED"),
                    appointment("no-show", "NO_SHOW"),
                    appointment("confirmed", "CONFIRMED"),
                    appointment("follow-up", "FOLLOW_UP_REQUIRED"),
                ]}
                hide={vi.fn(async () => undefined)}
            />
        );

        expect(html.match(/class="appointment-delete-action"/g)).toHaveLength(3);
        expect(html.match(/aria-haspopup="dialog"/g)).toHaveLength(3);
        expect(html).toContain("Xóa lịch");
    });
});
