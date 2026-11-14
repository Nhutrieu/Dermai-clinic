import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Appointment } from "../core/types";
import PatientAppointmentList, { canHideAppointmentFromHistory, isUpcomingPatientAppointment } from "./PatientAppointmentList";

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
    it.each(["PROPOSED", "PENDING", "ASSIGNED", "PENDING_PAYMENT", "PENDING_CONFIRMATION", "CONFIRMED", "CHECKED_IN", "IN_PROGRESS"])("keeps %s in upcoming appointments", status => {
        expect(isUpcomingPatientAppointment(status)).toBe(true);
    });

    it.each(["COMPLETED", "CANCELLED", "CANCELLED_EXPIRED", "NO_SHOW", "FOLLOW_UP_REQUIRED"])("keeps %s only in booking history", status => {
        expect(isUpcomingPatientAppointment(status)).toBe(false);
    });

    it("defaults to ongoing appointments even when their scheduled time has passed", () => {
        const html = renderToStaticMarkup(<PatientAppointmentList grouped appointments={[
            { ...appointment("ongoing", "IN_PROGRESS"), reason: "Ca đang khám" },
            { ...appointment("paid", "PENDING_CONFIRMATION"), reason: "Ca đã cọc" },
            { ...appointment("completed", "COMPLETED"), reason: "Ca đã hoàn tất" },
            { ...appointment("cancelled", "CANCELLED"), startAt: "2099-01-01T08:00:00Z", reason: "Ca đã hủy" },
        ]} />);
        expect(html).toContain('role="tablist"');
        expect(html).toContain('role="tabpanel"');
        expect(html).toContain("Ca đang khám");
        expect(html).toContain("Ca đã cọc");
        expect(html).not.toContain("Ca đã hoàn tất");
        expect(html).not.toContain("Ca đã hủy");
    });

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

    it("only offers a refund request for a paid patient cancellation", () => {
        const cancelled = { ...appointment("cancelled", "CANCELLED"), cancellationInitiator: "PATIENT_REQUEST" };
        const render = (status: "CANCELLED" | "SUCCESS" | "REFUND_REQUESTED") => renderToStaticMarkup(
            <PatientAppointmentList
                token="token"
                appointments={[cancelled]}
                refundPayments={{ cancelled: { amount: 5000, status } }}
                requestRefund={vi.fn(async () => undefined)}
                hide={vi.fn(async () => undefined)}
            />
        );

        expect(render("CANCELLED")).not.toContain("Yêu cầu hoàn tiền cọc");
        expect(render("CANCELLED")).toContain("Xóa lịch");
        expect(render("SUCCESS")).toContain("Yêu cầu hoàn tiền cọc");
        expect(render("REFUND_REQUESTED")).toContain("Đã gửi yêu cầu hoàn tiền");
        const clinicCancelled = renderToStaticMarkup(
            <PatientAppointmentList
                appointments={[{ ...cancelled, cancellationInitiator: "CLINIC" }]}
                refundPayments={{ cancelled: { amount: 5000, status: "SUCCESS" } }}
                requestRefund={vi.fn(async () => undefined)}
            />
        );
        expect(clinicCancelled).not.toContain("Yêu cầu hoàn tiền cọc");
    });
});
