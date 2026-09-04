import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Doctor, SlotDurationPolicy, WorkSchedule } from "../../core/types";
import DoctorProfileScreen, { slotMinutesOn } from "./DoctorProfileScreen";

const doctor: Doctor = {
  id: "doctor-1",
  identityId: "identity-1",
  fullName: "Bình",
  specialtyCode: "DA LIỄU TỔNG QUÁT",
  experienceYears: 6,
  certificateNo: "CCHN-BINH-001",
  consultationFee: 150000,
};

const work: WorkSchedule[] = [1, 2, 3, 4, 5].map(weekday => ({
  id: `schedule-${weekday}`,
  weekday,
  startTime: "08:00:00",
  endTime: "17:00:00",
  slotMinutes: 30,
}));
const slotPolicies: SlotDurationPolicy[] = [{
  id: "policy-1",
  doctorId: "doctor-1",
  effectiveFrom: "2026-09-10",
  slotMinutes: 60,
}];

describe("DoctorProfileScreen", () => {
  it("presents the public profile and weekly availability in one accessible hierarchy", () => {
    const html = renderToStaticMarkup(
      <DoctorProfileScreen token="token" doctor={doctor} work={work} slotPolicies={slotPolicies} leave={[]} saved={() => undefined} />,
    );

    expect(html).toContain("Hồ sơ hiển thị với bệnh nhân");
    expect(html).toContain("150.000 đ");
    expect(html).toContain("Thứ Hai - Thứ Sáu");
    expect(html).toContain("Áp dụng slot từ ngày");
    expect(html).toContain("Slot mới áp dụng cho mọi ngày làm việc kể từ ngày đã chọn");
    expect(html).toContain("Chưa có ngày nghỉ");
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-label="Chọn ảnh đại diện mới"');
  });

  it("uses the old duration before the effective date and the new one from that date onward", () => {
    expect(slotMinutesOn("2026-09-09", work, slotPolicies)).toBe(30);
    expect(slotMinutesOn("2026-09-10", work, slotPolicies)).toBe(60);
    expect(slotMinutesOn("2026-10-01", work, slotPolicies)).toBe(60);
  });
});
