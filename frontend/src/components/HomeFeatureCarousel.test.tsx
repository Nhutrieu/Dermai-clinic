import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import HomeFeatureCarousel from "./HomeFeatureCarousel";

describe("HomeFeatureCarousel", () => {
  it("renders four accessible feature slides and manual controls", () => {
    const html = renderToStaticMarkup(<HomeFeatureCarousel />);

    expect(html.match(/clinic-home-feature-slide/g)).toHaveLength(4);
    expect(html).toContain("Tư vấn trực tiếp");
    expect(html).toContain("AI hỗ trợ đánh giá da");
    expect(html).toContain("Đặt lịch dễ dàng");
    expect(html).toContain("Hỗ trợ khi bạn cần");
    expect(html).toContain('aria-label="Slide trước"');
    expect(html).toContain('aria-label="Slide tiếp theo"');
    expect(html).toContain('aria-current="true"');
  });
});
