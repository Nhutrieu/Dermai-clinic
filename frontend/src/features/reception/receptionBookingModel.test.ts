import { describe, expect, it } from "vitest";
import { ApiError } from "../../core/api";
import type { AvailabilitySlot } from "../../core/types";
import {
  APPOINTMENT_ALREADY_HANDLED_MESSAGE,
  isAppointmentAlreadyHandledError,
  isConfirmedAppointmentStatus,
  receptionSlotDetails,
  toBookingIssue,
} from "./receptionBookingModel";

describe("reception booking presentation rules", () => {
  it("keeps every slot state explicit instead of relying on color", () => {
    const states: AvailabilitySlot["status"][] = [
      "AVAILABLE",
      "BOOKED",
      "ON_LEAVE",
      "HELD_BY_YOU",
      "HELD_BY_OTHER",
    ];
    const details = states.map(receptionSlotDetails);
    expect(details.map(item => item.label)).toEqual([
      "Còn trống",
      "Đã có lịch",
      "Bác sĩ nghỉ",
      "Đang giữ cho bạn",
      "Đang được giữ",
    ]);
    expect(details.filter(item => item.selectable)).toHaveLength(1);
  });

  it("maps backend conflict codes to an actionable message", () => {
    const issue = toBookingIssue(new ApiError(
      "Bác sĩ đã có lịch trong khoảng thời gian này.",
      409,
      "SLOT_CONFLICT",
    ));
    expect(issue).toMatchObject({
      code: "SLOT_CONFLICT",
      title: "Khung giờ vừa được đặt",
      conflict: true,
    });
    expect(issue.action).toContain("khung giờ");
  });

  it("does not treat a created request as a confirmed booking", () => {
    expect(isConfirmedAppointmentStatus("PENDING")).toBe(false);
    expect(isConfirmedAppointmentStatus("ASSIGNED")).toBe(false);
    expect(isConfirmedAppointmentStatus("CONFIRMED")).toBe(true);
  });

  it("recognizes a confirmation that another receptionist already handled", () => {
    const error = new ApiError(
      "Không thể chuyển trạng thái lịch khám.",
      409,
      "INVALID_TRANSITION",
    );

    expect(isAppointmentAlreadyHandledError(error)).toBe(true);
    expect(APPOINTMENT_ALREADY_HANDLED_MESSAGE).toContain("lễ tân khác xử lý");
    expect(isAppointmentAlreadyHandledError(new ApiError("Lỗi", 500))).toBe(false);
  });
});
