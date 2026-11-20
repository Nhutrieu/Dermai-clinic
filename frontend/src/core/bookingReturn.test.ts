import { describe, expect, it, vi } from "vitest";
import { doctorBookingSelection, doctorBookingUrl, resolveBookingReturn } from "./bookingReturn";

const saved = JSON.stringify({ orderCode: 123, bookingId: "booking-2", bookingSelection: { doctorId: "doctor-2", date: "2026-11-22" } });

describe("returning to the booked doctor", () => {
  it("restores the matching payment's doctor and date without changing the booking", async () => {
    const load = vi.fn();
    const target = await resolveBookingReturn(saved, "123", "booking-2", load);
    expect(doctorBookingUrl(target)).toBe("/?doctorId=doctor-2&date=2026-11-22");
    expect(load).not.toHaveBeenCalled();
  });
  it("loads the actual appointment when checkout returns in another tab without browser storage", async () => {
    const load = vi.fn().mockResolvedValue({ doctorId: "doctor-2", startAt: "2026-11-21T18:30:00Z" });
    const target = await resolveBookingReturn(null, "123", "booking-2", load);
    expect(target).toEqual({ doctorId: "doctor-2", date: "2026-11-22" });
    expect(load).toHaveBeenCalledExactlyOnceWith("booking-2");
  });
  it("does not restore another payment's cached doctor", async () => {
    const load = vi.fn().mockResolvedValue({ doctorId: "doctor-3", startAt: "2026-11-23T02:00:00Z" });
    expect(await resolveBookingReturn(saved, "456", "booking-3", load))
      .toEqual({ doctorId: "doctor-3", date: "2026-11-23" });
    expect(load).toHaveBeenCalledExactlyOnceWith("booking-3");
  });
  it("uses the server appointment when the cached booking ID disagrees", async () => {
    const load = vi.fn().mockResolvedValue({ doctorId: "doctor-3", startAt: "2026-11-23T02:00:00Z" });
    expect(await resolveBookingReturn(saved, "123", "booking-3", load))
      .toEqual({ doctorId: "doctor-3", date: "2026-11-23" });
  });
  it("recovers older pending payments without stored doctor context", async () => {
    const load = vi.fn().mockResolvedValue({ doctorId: "doctor-2", startAt: "2026-11-22T02:00:00Z" });
    expect(await resolveBookingReturn(JSON.stringify({ orderCode: 123, bookingId: "booking-2" }), "123", undefined, load))
      .toEqual({ doctorId: "doctor-2", date: "2026-11-22" });
  });
  it("still completes a payment return when context cannot be recovered", async () => {
    const load = vi.fn().mockRejectedValue(new Error("Not available"));
    expect(doctorBookingUrl(await resolveBookingReturn("broken JSON", "123", "booking-2", load))).toBe("/");
    expect(await resolveBookingReturn(saved, "456", undefined, load)).toBeUndefined();
  });
  it("supports refreshing a doctor link while ignoring invalid dates and empty doctor IDs", () => {
    expect(doctorBookingSelection("?doctorId=doctor-2&date=2026-11-22"))
      .toEqual({ doctorId: "doctor-2", date: "2026-11-22" });
    expect(doctorBookingSelection("?doctorId=doctor-2&date=2026-02-30"))
      .toEqual({ doctorId: "doctor-2" });
    expect(doctorBookingSelection("?doctorId=%20")).toBeUndefined();
    expect(doctorBookingUrl({ doctorId: "doctor&other=1" })).toBe("/?doctorId=doctor%26other%3D1");
  });
});
