import { describe, expect, it } from "vitest";
import { isPaymentReturn, patientLandingTab, withoutDoctorBooking } from "./patientNavigation";

const doctorUrl = "?doctorId=doctor-2&date=2026-11-22";

describe("patient login and booking navigation", () => {
  it("opens Overview for a normal login even if an earlier doctor link or draft remains", () => {
    expect(patientLandingTab(doctorUrl, "profile", true)).toBe("profile");
    expect(patientLandingTab("", null, false)).toBe("profile");
  });
  it("preserves intentional payment returns and doctor links for an existing session", () => {
    expect(patientLandingTab(doctorUrl, "appointments", false)).toBe("appointments");
    expect(patientLandingTab(doctorUrl, null, false)).toBe("appointments");
    expect(isPaymentReturn("/payment/success")).toBe(true);
    expect(isPaymentReturn("/payment/cancel")).toBe(true);
    expect(isPaymentReturn("/")).toBe(false);
  });
  it("honors a newly selected AI or invoice destination over stale booking parameters", () => {
    expect(patientLandingTab(doctorUrl, "ai", true)).toBe("ai");
    expect(patientLandingTab(doctorUrl, "billing", false)).toBe("billing");
  });
  it("removes only the previous booking selection when leaving the booking screen", () => {
    expect(withoutDoctorBooking("https://clinic.test/?doctorId=doctor-2&date=2026-11-22")).toBe("/");
    expect(withoutDoctorBooking("https://clinic.test/?other=value&doctorId=doctor-2&date=2026-11-22#home"))
      .toBe("/?other=value#home");
  });
});
