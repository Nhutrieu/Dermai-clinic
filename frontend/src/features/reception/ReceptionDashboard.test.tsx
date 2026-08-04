import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import ReceptionDashboard from "./ReceptionDashboard";

function props(overrides: Record<string, unknown> = {}) {
  const action = vi.fn(async () => undefined);
  return {
    token: "token",
    appointments: [],
    reminders: [],
    searchResults: [],
    selectedPatientId: "",
    query: "",
    lastSearchTerm: "",
    queueLoading: false,
    queueError: "",
    reminderLoading: false,
    reminderError: "",
    searchLoading: false,
    searchAttempted: false,
    searchError: "",
    notice: "",
    noticeError: false,
    busyAppointmentId: "",
    realtimeState: "connected" as const,
    lastSyncedAt: null,
    liveRevision: 0,
    changedAppointmentIds: [],
    actionErrorAppointmentId: "",
    patientName: () => "Bệnh nhân",
    doctorName: () => "Bác sĩ",
    onQueryChange: vi.fn(),
    onSearch: action,
    onClearSearch: vi.fn(),
    onSelectPatient: vi.fn(),
    onOpenSupport: vi.fn(),
    onOpenHotline: vi.fn(),
    onOpenRequests: vi.fn(),
    onOpenAccepted: vi.fn(),
    onConfirm: action,
    onNoShow: action,
    onRemind: action,
    onRetryQueue: action,
    onRetryReminders: action,
    ...overrides,
  };
}

describe("ReceptionDashboard", () => {
  it("renders the operational hierarchy and accessible patient search", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props()} />);
    expect(html).toContain("Điều phối hôm nay");
    expect(html).toContain('role="search"');
    expect(html).toContain('for="reception-patient-search"');
    expect(html).toContain("Hôm nay chưa có lịch hẹn");
    expect(html).toContain("Đã kết nối trực tiếp");
    expect(html).toContain("Hệ thống chưa ghi nhận bước tiếp nhận tại quầy");
  });

  it("renders only real queue actions and does not invent check-in controls", () => {
    const start = new Date(Date.now() - 40 * 60_000);
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      appointments: [{
        id: "appointment-1",
        patientId: "patient-1",
        doctorId: "doctor-1",
        startAt: start.toISOString(),
        endAt: new Date(start.getTime() + 30 * 60_000).toISOString(),
        status: "CONFIRMED",
        reason: "Khám da",
        createdAt: start.toISOString(),
      }],
    })} />);
    expect(html).toContain("Quá giờ hẹn");
    expect(html).toContain("Ghi nhận vắng");
    expect(html).not.toContain("Gọi bệnh nhân tiếp theo");
    expect(html).not.toContain("Xác nhận đã đến");
  });

  it("keeps the latest rows visible when realtime and refresh are unavailable", () => {
    const start = new Date(Date.now() + 30 * 60_000);
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      realtimeState: "closed",
      lastSyncedAt: new Date(),
      queueError: "Không thể làm mới",
      appointments: [{
        id: "appointment-stale",
        patientId: "patient-stale",
        doctorId: "doctor-1",
        startAt: start.toISOString(),
        endAt: new Date(start.getTime() + 30 * 60_000).toISOString(),
        status: "CONFIRMED",
        createdAt: start.toISOString(),
      }],
    })} />);
    expect(html).toContain("Mất kết nối trực tiếp");
    expect(html).toContain("đồng bộ định kỳ dự phòng vẫn hoạt động");
    expect(html).toContain("Bệnh nhân");
  });

  it("exposes a clear loading state without removing the operational shell", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({ queueLoading: true })} />);
    expect(html).toContain('aria-label="Đang tải hàng đợi hôm nay"');
    expect(html).toContain("Đặt lịch hotline");
  });

  it("keeps the dashboard usable when independent APIs fail", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      queueError: "Không tải được lịch",
      reminderError: "Không tải được nhắc lịch",
    })} />);
    expect(html).toContain("Không thể tải hàng đợi");
    expect(html).toContain("Không thể tải danh sách nhắc lịch");
    expect(html).toContain("Đặt lịch hotline");
  });

  it("renders the search empty state without exposing medical data", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      query: "không tồn tại",
      searchAttempted: true,
    })} />);
    expect(html).toContain("Không có hồ sơ khớp");
    expect(html).toContain("Tạo hồ sơ qua hotline");
    expect(html).not.toContain("kết quả AI");
  });

  it("masks contact data and warns when search results share a name", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      query: "Nguyễn An",
      lastSearchTerm: "Nguyễn An",
      searchAttempted: true,
      searchResults: [
        { id: "patient-1111", identityId: "identity-1", fullName: "Nguyễn An", phone: "0352790904", dob: "2000-01-01", accountLinked: true },
        { id: "patient-2222", identityId: "identity-2", fullName: "Nguyễn An", phone: "0901234567", dob: "1998-03-02", accountLinked: false },
      ],
    })} />);
    expect(html).toContain("Có hồ sơ trùng họ tên");
    expect(html).toContain("035 *** 904");
    expect(html).not.toContain("0352790904");
    expect(html).toContain("Xem thông tin");
    expect(html).not.toContain("Tiền sử bệnh");
  });
});
