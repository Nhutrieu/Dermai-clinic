import { afterEach, describe, expect, it, vi } from "vitest";
import { buildCashFlowDays, sumCollectedDeposits } from "./AdminBilling";

describe("deposit reconciliation", () => {
  afterEach(() => vi.useRealTimers());

  it("counts a refunded deposit as money received and shows its refund separately", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-04T12:00:00Z"));
    const payment = {
      id: "payment-1",
      status: "REFUNDED",
      amount: 5000,
      refundAmount: 2500,
      createdAt: "2026-10-03T03:00:00Z",
      refundedAt: "2026-10-04T03:00:00Z",
    };

    expect(sumCollectedDeposits([payment], Date.parse("2026-10-03T00:00:00Z"), Date.parse("2026-10-05T00:00:00Z"))).toBe(5000);
    const flow = buildCashFlowDays([], [payment]);
    expect(flow.find(day => day.date === "2026-10-03")).toMatchObject({ online: 5000, refunded: 0 });
    expect(flow.find(day => day.date === "2026-10-04")).toMatchObject({ online: 0, refunded: 2500 });
  });

  it("excludes a cancelled checkout that never collected a deposit", () => {
    expect(sumCollectedDeposits([{
      id: "payment-2", status: "CANCELLED", amount: 100000, createdAt: "2026-10-04T03:00:00Z",
    }], Date.parse("2026-10-04T00:00:00Z"), Date.parse("2026-10-05T00:00:00Z"))).toBe(0);
  });
});
