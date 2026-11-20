import { describe, expect, it } from "vitest";
import { adminNotificationFeed, EMPTY_ADMIN_ALERTS, type AdminAlertData } from "./adminNotificationFeed";

const now = Date.parse("2026-11-19T10:00:00Z");
const leave = { id: "leave", doctorId: "doctor", doctorName: "Bình", status: "PENDING" as const, startAt: "2026-11-20T01:00:00Z", endAt: "2026-11-20T10:00:00Z", reason: "Có việc riêng" };
const review = { id: "review", appointmentId: "visit", displayName: "An", rating: 2, comment: "Cần hỗ trợ", status: "PENDING" as const, createdAt: "2026-11-19T09:00:00Z" };
const refund = { id: "refund", status: "REFUND_REQUESTED", amount: 100000, refundAmount: 50000 };
const stock = { productId: "product", sku: "SKU", name: "Thuốc A", unit: "viên", currentQuantity: 0, minThreshold: 5, shortageQuantity: 5 };
const expiry = { batchId: "batch", productId: "product", sku: "SKU", productName: "Thuốc A", batchNumber: "LOT", expiryDate: "2026-11-22", quantity: 10, daysRemaining: 3 };
const stale = { id: "visit", patientId: "patient", status: "IN_PROGRESS", startAt: "2026-11-19T07:00:00Z", endAt: "2026-11-19T08:00:00Z", createdAt: "2026-11-18T00:00:00Z" };
const data: AdminAlertData = { leave: [leave], review: [review], refund: [refund], lowStock: [stock], expiring: [expiry], stale: [stale] };

describe("admin notification feed", () => {
  it("routes six real operational issues to their admin screens", () => {
    const alerts = adminNotificationFeed(data, now);
    expect(alerts).toHaveLength(6);
    expect(alerts.find(item => item.kind === "leave")).toMatchObject({ tab: "appointments", target: "admin-leave-requests" });
    expect(alerts.find(item => item.kind === "review")).toMatchObject({ tab: "reviews", target: "admin-review-queue", urgent: true });
    expect(alerts.find(item => item.kind === "refund")).toMatchObject({ tab: "refunds", target: "admin-refund-queue" });
    expect(alerts.find(item => item.kind === "lowStock")).toMatchObject({ tab: "inventory", urgent: true });
    expect(alerts.find(item => item.kind === "expiring")).toMatchObject({ tab: "inventory", target: "admin-expiring-alerts" });
    expect(alerts.find(item => item.kind === "stale")).toMatchObject({ tab: "profile", target: "admin-stale-consultations" });
  });
  it("removes resolved requests, moderated reviews, refunded payments and healthy stock", () => {
    expect(adminNotificationFeed({
      leave: [{ ...leave, status: "APPROVED" }], review: [{ ...review, status: "APPROVED" }],
      refund: [{ ...refund, status: "REFUNDED" }], lowStock: [{ ...stock, currentQuantity: 5 }],
      expiring: [{ ...expiry, quantity: 0 }], stale: [{ ...stale, status: "COMPLETED" }],
    }, now)).toEqual([]);
  });
  it("prioritizes urgent warnings and does not flag consultations within the grace period", () => {
    const alerts = adminNotificationFeed({ ...data, stale: [{ ...stale, endAt: "2026-11-19T09:30:00Z" }] }, now);
    expect(alerts.some(item => item.kind === "stale")).toBe(false);
    const urgentCount = alerts.filter(item => item.urgent).length;
    expect(alerts.slice(0, urgentCount).every(item => item.urgent)).toBe(true);
  });
  it("keeps stable read keys for unchanged issues and resurfaces worsening stock", () => {
    const first = adminNotificationFeed({ ...EMPTY_ADMIN_ALERTS, lowStock: [{ ...stock, currentQuantity: 2 }] }, now)[0];
    const same = adminNotificationFeed({ ...EMPTY_ADMIN_ALERTS, lowStock: [{ ...stock, currentQuantity: 2 }] }, now + 30000)[0];
    const worse = adminNotificationFeed({ ...EMPTY_ADMIN_ALERTS, lowStock: [stock] }, now)[0];
    expect(first.key).toBe(same.key);expect(worse.key).not.toBe(first.key);
  });
  it("uses Vietnamese clinic time for leave requests", () => {
    const alert = adminNotificationFeed({ ...EMPTY_ADMIN_ALERTS, leave: [{ ...leave, startAt: "2026-11-19T19:00:00Z" }] }, now)[0];
    expect(alert.body).toContain("20/11");expect(alert.body).toContain("02:00");
  });
});
