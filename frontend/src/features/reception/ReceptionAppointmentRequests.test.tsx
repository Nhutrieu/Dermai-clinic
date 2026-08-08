import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Appointment, Doctor, Patient } from "../../core/types";
import ReceptionAppointmentRequests from "./ReceptionAppointmentRequests";

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
  consultationFee: 150000,
};

const request: Appointment = {
  id: "appointment-1",
  patientId: patient.id,
  doctorId: doctor.id,
  startAt: "2026-08-08T01:00:00.000Z",
  endAt: "2026-08-08T01:30:00.000Z",
  status: "PENDING",
  reason: "Ngứa da kéo dài",
  createdAt: "2026-08-02T03:00:00.000Z",
};

function render(requests: Appointment[], error = "") {
  return renderToStaticMarkup(
    <ReceptionAppointmentRequests
      requests={requests}
      patients={requests.length ? [patient] : []}
      doctors={[doctor]}
      recommendations={[]}
      recommendFor=""
      loading={false}
      refreshing={false}
      error={error}
      profileWarning=""
      actionMessage=""
      actionMessageError={false}
      busyAppointmentId=""
      lastUpdatedAt={new Date("2026-08-02T04:00:00.000Z")}
      onRefresh={vi.fn(async () => undefined)}
      onRecommend={vi.fn(async () => undefined)}
      onAssign={vi.fn(async () => undefined)}
      onConfirm={vi.fn(async () => undefined)}
      onCancel={vi.fn(async () => request)}
      onOpenSupport={vi.fn()}
      onOpenAccepted={vi.fn()}
    />,
  );
}

describe("ReceptionAppointmentRequests", () => {
  it("renders real request details, accessible filters and one primary action", () => {
    const html = render([request]);
    expect(html).toContain("Nguyễn An");
    expect(html).toContain("0352790904");
    expect(html).toContain("Ngứa da kéo dài");
    expect(html).toContain("Chờ xử lý");
    expect(html).toContain("Đề xuất bác sĩ");
    expect(html).toContain('id="reception-request-search"');
    expect(html).toContain("Mới nhất trước");
  });

  it("counts assigned requests as work that still needs receptionist action", () => {
    const html = render([{ ...request, status: "ASSIGNED" }]);
    expect(html).toContain("Cần xử lý (1)");
    expect(html).toContain("1</strong><span>yêu cầu đang cần lễ tân xử lý");
  });

  it("renders the guided empty state without database wording", () => {
    const html = render([]);
    expect(html).toContain("Không có yêu cầu mới");
    expect(html).toContain("Các yêu cầu đặt lịch mới từ bệnh nhân sẽ xuất hiện tại đây.");
    expect(html).toContain("Xem lịch đã nhận");
    expect(html).not.toContain("database");
  });

  it("renders a retry action when the initial request fails", () => {
    const html = render([], "Không thể kết nối máy chủ");
    expect(html).toContain('role="alert"');
    expect(html).toContain("Chưa thể tải yêu cầu đặt lịch");
    expect(html).toContain("Thử lại");
  });
});
