import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import ReceptionDashboard from "./ReceptionDashboard";

function props(overrides: Record<string, unknown> = {}) {
  const action = vi.fn(async () => undefined);
  return {
    appointments: [],
    reminders: [],
    searchResults: [],
    selectedPatientId: "",
    query: "",
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
    expect(html).toContain("Dữ liệu đang cập nhật trực tiếp");
  });

  it("keeps the dashboard usable when independent APIs fail", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      queueError: "Không tải được lịch",
      reminderError: "Không tải được nhắc lịch",
    })} />);
    expect(html).toContain("Không thể tải lịch hôm nay");
    expect(html).toContain("Không thể tải danh sách nhắc lịch");
    expect(html).toContain("Đặt lịch hotline");
  });

  it("renders the search empty state without exposing medical data", () => {
    const html = renderToStaticMarkup(<ReceptionDashboard {...props({
      query: "không tồn tại",
      searchAttempted: true,
    })} />);
    expect(html).toContain("Không tìm thấy bệnh nhân phù hợp");
    expect(html).toContain("Mở đặt lịch hotline");
    expect(html).not.toContain("kết quả AI");
  });
});
