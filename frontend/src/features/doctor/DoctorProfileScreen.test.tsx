import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Doctor, WorkSchedule } from "../../core/types";
import DoctorProfileScreen from "./DoctorProfileScreen";

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

describe("DoctorProfileScreen", () => {
  it("presents the public profile and weekly availability in one accessible hierarchy", () => {
    const html = renderToStaticMarkup(
      <DoctorProfileScreen token="token" doctor={doctor} work={work} leave={[]} saved={() => undefined} />,
    );

    expect(html).toContain("Hồ sơ hiển thị với bệnh nhân");
    expect(html).toContain("150.000 đ");
    expect(html).toContain("Thứ Hai - Thứ Sáu");
    expect(html).toContain("Chưa có ngày nghỉ");
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-label="Chọn ảnh đại diện mới"');
  });
});
