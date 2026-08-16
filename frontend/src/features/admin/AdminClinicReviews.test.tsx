import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { ClinicReview } from "../../core/types";
import { AdminClinicReviewList } from "./AdminClinicReviews";

describe("AdminClinicReviewList stored-XSS protection", () => {
    it("renders persisted review and API error values only as escaped text", () => {
        const maliciousReview: ClinicReview = {
            id: "review-1",
            appointmentId: "appointment-1",
            displayName: '<img src=x onerror="globalThis.pwned=true">',
            rating: 5,
            comment: "<script>globalThis.pwned=true</script>",
            status: "PENDING",
            createdAt: "2026-08-14T00:00:00.000Z",
        };

        const html = renderToStaticMarkup(<AdminClinicReviewList
            reviews={[maliciousReview]}
            error={'<svg onload="globalThis.pwned=true">'}
            onModerate={vi.fn(async () => undefined)}
        />);

        expect(html).not.toContain("<img");
        expect(html).not.toContain("<script");
        expect(html).not.toContain("<svg");
        expect(html).toContain("&lt;img");
        expect(html).toContain("&lt;script&gt;");
        expect(html).toContain("&lt;svg");
    });
});
