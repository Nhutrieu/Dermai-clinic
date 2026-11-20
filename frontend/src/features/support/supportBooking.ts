import type { SupportBookingOption } from "../../core/types";

export type ChatBookingRequest = SupportBookingOption & { requestId: string };
export const SUPPORT_BOOKING_EVENT = "support-booking-selected";

export function chatBookingDate(option: SupportBookingOption) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(option.startAt));
}

export function validChatBooking(value: unknown): value is SupportBookingOption {
  if (!value || typeof value !== "object") return false;
  const option = value as SupportBookingOption;
  return typeof option.doctorId === "string" && !!option.doctorId.trim()
    && typeof option.doctorName === "string" && typeof option.startAt === "string" && typeof option.endAt === "string"
    && Number.isFinite(Date.parse(option.startAt)) && Number.isFinite(Date.parse(option.endAt))
    && Date.parse(option.startAt) > Date.now() && Date.parse(option.endAt) > Date.parse(option.startAt);
}
