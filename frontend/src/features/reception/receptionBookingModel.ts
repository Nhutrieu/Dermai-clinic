import { ApiError } from "../../core/api";
import type { AvailabilitySlot } from "../../core/types";

export type BookingIssue = {
  code: string;
  title: string;
  detail: string;
  action: string;
  conflict: boolean;
};

const CONFLICT_MESSAGES: Record<string, Omit<BookingIssue, "code" | "conflict">> = {
  SLOT_CONFLICT: {
    title: "Khung giờ vừa được đặt",
    detail: "Một lịch khác đã được xác nhận cho bác sĩ trong khoảng thời gian này.",
    action: "Chọn một khung giờ còn trống khác.",
  },
  DOCTOR_SLOT_CONFLICT: {
    title: "Khung giờ không còn khả dụng",
    detail: "Lịch làm việc của bác sĩ vừa thay đổi hoặc khung giờ đã có lịch khác.",
    action: "Kiểm tra danh sách giờ vừa cập nhật và chọn lại.",
  },
  PATIENT_TIME_CONFLICT: {
    title: "Bệnh nhân đã có lịch trùng giờ",
    detail: "Bệnh nhân không thể có hai lịch khám trong cùng một khoảng thời gian.",
    action: "Chọn một giờ khác không trùng lịch hiện có.",
  },
  SAME_DOCTOR_SAME_DAY: {
    title: "Bệnh nhân đã có lịch với bác sĩ này",
    detail: "Hệ thống chỉ cho phép một lịch với cùng bác sĩ trong một ngày.",
    action: "Chọn ngày khác hoặc kiểm tra lịch đã có.",
  },
  ACTIVE_APPOINTMENT_LIMIT: {
    title: "Bệnh nhân đã đạt giới hạn lịch",
    detail: "Bệnh nhân đã có số lịch sắp tới tối đa theo quy định hiện tại.",
    action: "Kiểm tra lịch đang hoạt động trước khi đặt thêm.",
  },
  HOLD_EXPIRED: {
    title: "Thời gian giữ chỗ đã hết",
    detail: "Khung giờ không còn được giữ và có thể đã được người khác chọn.",
    action: "Tải lại giờ trống và chọn một khung giờ khác.",
  },
  OUTSIDE_DOCTOR_WORK_SCHEDULE: {
    title: "Bác sĩ không làm việc vào thời gian này",
    detail: "Khung giờ nằm ngoài lịch làm việc hiện tại của bác sĩ.",
    action: "Chọn giờ khác trong danh sách còn trống.",
  },
  DOCTOR_ON_LEAVE: {
    title: "Bác sĩ nghỉ trong thời gian này",
    detail: "Khung giờ đã chọn trùng với lịch nghỉ của bác sĩ.",
    action: "Chọn một ngày hoặc khung giờ khác.",
  },
  BOOKING_TOO_FAR_AHEAD: {
    title: "Ngày khám nằm ngoài thời gian cho phép",
    detail: "Hệ thống chỉ nhận lịch trong phạm vi đặt trước hiện tại.",
    action: "Chọn một ngày gần hơn.",
  },
  CLINIC_CLOSED: {
    title: "Phòng khám đóng cửa trong ngày này",
    detail: "Ngày đã chọn thuộc lịch nghỉ chung của phòng khám.",
    action: "Chọn một ngày làm việc khác.",
  },
};

export function clinicDateInput(addDays = 0) {
  const value = new Date();
  value.setDate(value.getDate() + addDays);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(value);
}

export function formatReceptionTime(value: string) {
  return new Date(value).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatReceptionDate(value: string) {
  return new Date(value).toLocaleDateString("vi-VN", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatReceptionDateTime(value: string) {
  return `${formatReceptionTime(value)}, ${formatReceptionDate(value)}`;
}

export function receptionSlotDetails(status: AvailabilitySlot["status"]) {
  switch (status) {
    case "AVAILABLE":
      return { label: "Còn trống", className: "is-available", selectable: true };
    case "BOOKED":
      return { label: "Đã có lịch", className: "is-booked", selectable: false };
    case "ON_LEAVE":
      return { label: "Bác sĩ nghỉ", className: "is-unavailable", selectable: false };
    case "HELD_BY_YOU":
      return { label: "Đang giữ cho bạn", className: "is-held", selectable: false };
    case "HELD_BY_OTHER":
      return { label: "Đang được giữ", className: "is-held", selectable: false };
  }
}

export function toBookingIssue(error: unknown): BookingIssue {
  const code = error instanceof ApiError ? error.code || "" : "";
  const known = CONFLICT_MESSAGES[code];
  if (known) return { code, conflict: true, ...known };

  const detail = error instanceof Error && error.message
    ? error.message
    : "Không thể hoàn tất thao tác. Vui lòng thử lại.";
  return {
    code: code || "UNKNOWN",
    title: "Chưa thể hoàn tất thao tác",
    detail,
    action: "Giữ nguyên thông tin đã nhập và thử lại sau khi kiểm tra kết nối.",
    conflict: error instanceof ApiError && error.status === 409,
  };
}

export function isConfirmedAppointmentStatus(status: string) {
  return status === "CONFIRMED";
}
