import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Appointment } from "../../core/types";
import ReceptionHotlineBookingView from "./HotlineBookingView";
import {
  BookingConflictDialog,
  NotificationDeliveryStatus,
  ReceptionCancelControl,
  ReceptionRescheduleControl,
} from "./ReceptionAppointmentActions";

const appointment: Appointment = {
  id: "appointment-1",
  patientId: "patient-1",
  doctorId: "doctor-1",
  startAt: "2026-08-03T02:30:00.000Z",
  endAt: "2026-08-03T03:00:00.000Z",
  status: "CONFIRMED",
  reason: "Ngứa da",
  createdAt: "2026-08-01T00:00:00.000Z",
};

describe("reception appointment actions", () => {
  it("renders an accessible conflict dialog without technical error codes", () => {
    const html = renderToStaticMarkup(
      <BookingConflictDialog
        issue={{
          code: "SLOT_CONFLICT",
          title: "Khung giờ vừa được đặt",
          detail: "Khung giờ không còn trống.",
          action: "Chọn giờ khác.",
          conflict: true,
        }}
        onClose={vi.fn()}
        onChooseAnother={vi.fn()}
      />,
    );
    expect(html).toContain('role="alertdialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("Khung giờ vừa được đặt");
    expect(html).toContain("Các thông tin bệnh nhân và lý do khám vẫn được giữ nguyên");
    expect(html).not.toContain("SLOT_CONFLICT");
  });

  it("states notification delivery honestly", () => {
    const html = renderToStaticMarkup(<NotificationDeliveryStatus />);
    expect(html).toContain("chưa trả trạng thái gửi email hoặc SMS");
    expect(html).not.toContain("Đã gửi SMS");
  });

  it("keeps reschedule and cancel controls explicit", () => {
    const reschedule = renderToStaticMarkup(
      <ReceptionRescheduleControl
        token="token"
        appointment={appointment}
        patientName="Nguyễn An"
        doctorName="Bình"
        submit={vi.fn(async () => appointment)}
      />,
    );
    const cancel = renderToStaticMarkup(
      <ReceptionCancelControl
        appointment={appointment}
        patientName="Nguyễn An"
        doctorName="Bình"
        submit={vi.fn(async () => appointment)}
      />,
    );
    expect(reschedule).toContain("Đổi lịch");
    expect(cancel).toContain("Hủy lịch");
  });

  it("keeps the hotline launcher keyboard-accessible before opening the workflow", () => {
    const html = renderToStaticMarkup(
      <ReceptionHotlineBookingView session={{
        accessToken: "token",
        refreshToken: "refresh",
        expiresIn: 3600,
        role: "RECEPTIONIST",
      }} />,
    );
    expect(html).toContain("Đặt lịch hotline");
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-expanded="false"');
  });
});
