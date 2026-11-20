import { doctorBookingSelection } from "./bookingReturn";

export function isPaymentReturn(pathname: string) {
  return pathname === "/payment/success" || pathname === "/payment/cancel";
}

export function patientLandingTab(search: string, intent: string | null, hasHomeBooking: boolean) {
  // A fresh, explicit login destination wins over a URL left by an earlier booking.
  if (intent === "profile" || intent === "ai" || intent === "billing") return intent;
  if (intent === "appointments" || hasHomeBooking || doctorBookingSelection(search)) return "appointments";
  return "profile";
}

export function withoutDoctorBooking(href: string) {
  const url = new URL(href, "https://clinic.invalid");
  url.searchParams.delete("doctorId");url.searchParams.delete("date");
  return url.pathname + url.search + url.hash;
}

export function clearPatientNavigation(preserveHomeBooking = false) {
  sessionStorage.removeItem("derm-home-intent");
  sessionStorage.removeItem("dermai-ai-booking");
  if (!preserveHomeBooking) sessionStorage.removeItem("derm-home-booking");
  // Keep the payment callback intact when a session expires during checkout.
  if (!isPaymentReturn(window.location.pathname)) {
    window.history.replaceState(window.history.state, "", withoutDoctorBooking(window.location.href));
  }
}
