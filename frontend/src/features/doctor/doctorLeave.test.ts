import { describe, expect, it } from "vitest";
import { fullDayLeaveRange } from "./doctorLeave";

describe("fullDayLeaveRange", () => {
  it("covers the whole selected local calendar day", () => {
    const range = fullDayLeaveRange("2026-08-25");
    expect(new Date(range.endAt).getTime() - new Date(range.startAt).getTime())
      .toBe(24 * 60 * 60 * 1000);
  });

  it("rejects an empty date", () => {
    expect(() => fullDayLeaveRange("")).toThrow("Vui lòng chọn ngày nghỉ.");
  });
});
