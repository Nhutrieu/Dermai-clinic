import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Appointment, Doctor, Patient, ReminderItem } from "../../core/types";
import ReceptionAcceptedAppointments from "./ReceptionAcceptedAppointments";

const patient: Patient = {
  id: "patient-1",
  identityId: "identity-1",
  fullName: "Nguyễn An",
  phone: "0352790904",
};

const doctor: Doctor = {
  id: "doctor-1",
  identityId: "doctor-identity-1",
  fullName: "Bình",
  specialtyCode: "GENERAL_DERMATOLOGY",
  experienceYears: 4,
};

const appointment: Appointment = {
  id: "appointment-1",
  patientId: patient.id,
  doctorId: doctor.id,
  startAt: "2026-08-08T01:00:00.000Z",
  endAt: "2026-08-08T01:30:00.000Z",
  status: "CONFIRMED",
  reason: "Ngứa da kéo dài",
  createdAt: "2026-08-02T03:00:00.000Z",
};

function render(overrides: Partial<Parameters<typeof ReceptionAcceptedAppointments>[0]> = {}) {
  const action = vi.fn(async () => undefined);
  const update = vi.fn(async () => appointment);
  return renderToStaticMarkup(<ReceptionAcceptedAppointments
    token="token"
    appointments={[]}
    reminders={[]}
    patients={[patient]}
    doctors={[doctor]}
    queueLoading={false}
    queueRefreshing={false}
    queueError=""
    reminderLoading={false}
    reminderError=""
    patientLoadWarning=""
    actionMessage=""
    actionMessageError={false}
    busyAppointmentId=""
    realtimeState="connected"
    lastUpdatedAt={new Date("2026-08-02T04:00:00.000Z")}
    onRetryQueue={action}
    onRetryReminders={action}
    onRemind={action}
    onReschedule={update}
    onCancel={update}
    onNoShow={action}
    onOpenSupport={vi.fn()}
    onOpenRequests={vi.fn()}
    {...overrides}
  />);
}

describe("ReceptionAcceptedAppointments", () => {
  it("renders compact and distinct empty states without database wording", () => {
    const html = render();
    expect(html).toContain("Không có lịch cần nhắc");
    expect(html).toContain("Chưa có lịch được tiếp nhận");
    expect(html).toContain("Xem yêu cầu đặt lịch");
    expect(html).not.toContain("database");
    expect(html).not.toContain("accepted-count-badge");
  });

  it("renders reminder contact data, current reminder actions and accessible filters", () => {
    const reminders: ReminderItem[] = [{ appointment }];
    const html = render({ appointments: [appointment], reminders });
    expect(html).toContain("Nguyễn An");
    expect(html).toContain("0352790904");
    expect(html).toContain("Ngứa da kéo dài");
    expect(html).toContain("Đã gọi xác nhận");
    expect(html).toContain("Gửi nhắc lại");
    expect(html).toContain("Tìm bệnh nhân, bác sĩ hoặc lý do");
    expect(html).toContain("Tất cả trạng thái");
    expect(html).toContain("Hiển thị <strong>1</strong> trong 1 lịch");
  });

  it("only exposes reschedule and cancel controls for confirmed appointments", () => {
    const confirmedHtml = render({ appointments: [appointment] });
    expect(confirmedHtml).toContain("Đổi lịch");
    expect(confirmedHtml).toContain("Hủy lịch");

    const completedHtml = render({ appointments: [{ ...appointment, status: "COMPLETED" }] });
    expect(completedHtml).toContain("Hoàn tất");
    expect(completedHtml).not.toContain("Đổi lịch");
    expect(completedHtml).not.toContain("Hủy lịch");
  });

  it("keeps stale data visible when reminder and queue refreshes fail", () => {
    const html = render({
      appointments: [appointment],
      reminders: [{ appointment }],
      queueError: "Không thể kết nối",
      reminderError: "Không thể kết nối",
      realtimeState: "closed",
    });
    expect(html).toContain("Dữ liệu gần nhất vẫn được giữ lại");
    expect(html).toContain("Mất kết nối trực tiếp");
    expect(html).toContain("Nguyễn An");
    expect(html).toContain("Thử lại");
  });

  it("shows local retry states instead of misleading empty states after an initial failure", () => {
    const html = render({
      queueError: "Không thể kết nối",
      reminderError: "Không thể kết nối",
    });
    expect(html).toContain("Chưa thể tải lịch cần nhắc");
    expect(html).toContain("Chưa thể tải lịch đã nhận");
    expect(html).not.toContain("Không có lịch cần nhắc");
    expect(html).not.toContain("Chưa có lịch được tiếp nhận");
  });
});
