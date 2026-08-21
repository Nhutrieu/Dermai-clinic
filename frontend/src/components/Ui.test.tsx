import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { CalendarDays } from "lucide-react";
import { EmptyState, ErrorState, StateSkeleton } from "./Ui";

describe("authenticated application states", () => {
  it("renders a useful empty state and its action", () => {
    const html = renderToStaticMarkup(<EmptyState
      icon={CalendarDays}
      title="Bạn chưa có lịch khám"
      description="Chọn bác sĩ và khung giờ phù hợp để bắt đầu."
      action={{ label: "Đặt lịch mới", onClick: vi.fn() }}
    />);

    expect(html).toContain("Bạn chưa có lịch khám");
    expect(html).toContain("Đặt lịch mới");
    expect(html).toContain("aria-hidden=\"true\"");
  });

  it("announces recoverable errors and loading states", () => {
    const error = renderToStaticMarkup(<ErrorState description="Dịch vụ tạm thời gián đoạn." retry={vi.fn()} />);
    const loading = renderToStaticMarkup(<StateSkeleton label="Đang tải lịch khám" />);

    expect(error).toContain("role=\"alert\"");
    expect(error).toContain("Thử lại");
    expect(loading).toContain("role=\"status\"");
    expect(loading).toContain("aria-label=\"Đang tải lịch khám\"");
  });
});
