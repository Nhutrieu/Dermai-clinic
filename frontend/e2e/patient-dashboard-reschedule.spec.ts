import { expect, test, type Page } from "@playwright/test";
import type { Appointment } from "../src/core/types";

async function mockDashboard(page: Page, status: string, rejectMove = false) {
  const now = Date.now();
  let appointment: Appointment = {
    id: "reschedule-test", patientId: "patient-test", doctorId: "doctor-test", doctorName: "Bác sĩ kiểm thử",
    status, createdAt: new Date(now - 5 * 60_000).toISOString(),
    startAt: new Date(now + 24 * 60 * 60_000).toISOString(),
    endAt: new Date(now + 24 * 60 * 60_000 + 30 * 60_000).toISOString(), reason: "Khám da kiểm thử",
  };
  const slot = { doctorId: "doctor-test", doctorIdentityId: "doctor-identity", doctorName: "Bác sĩ kiểm thử", specialtyCode: "DERMATOLOGY", score: 1,
    startAt: new Date(now + 48 * 60 * 60_000).toISOString(), endAt: new Date(now + 48 * 60 * 60_000 + 30 * 60_000).toISOString() };
  const moves: Array<{ body: unknown; idempotencyKey: string | undefined }> = [];
  await page.addInitScript(() => localStorage.setItem("dermai-session", JSON.stringify({ accessToken: "reschedule-test", refreshToken: "reschedule-refresh", role: "PATIENT", expiresIn: 3600 })));
  await page.routeWebSocket("**/api/v1/appointments/ws/**", socket => socket.close());
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/patients/me")) {
      await route.fulfill({ json: { id: "patient-test", identityId: "identity-test", fullName: "Bệnh nhân kiểm thử", dob: "2000-01-01", phone: "0900000000" } });
    } else if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { identityId: "identity-test", role: "PATIENT", status: "ACTIVE", hasAvatar: false } });
    } else if (path.endsWith("/appointments/mine")) {
      await route.fulfill({ json: [appointment] });
    } else if (path.endsWith("/appointments/recommendations")) {
      await route.fulfill({ json: { items: [slot], algorithmVersion: "test", timezone: "Asia/Ho_Chi_Minh" } });
    } else if (path.endsWith("/reschedule")) {
      moves.push({ body: request.postDataJSON(), idempotencyKey: request.headers()["idempotency-key"] });
      if (rejectMove) {
        await route.fulfill({ status: 409, json: { detail: "Không thể kết nối dịch vụ." } });
      } else {
        appointment = { ...appointment, ...request.postDataJSON() };
        await route.fulfill({ json: appointment });
      }
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.goto("/");
  const section = page.getByRole("region", { name: "Lịch khám sắp tới", exact: true });
  await expect(section).toBeVisible();
  return { section, slot, moves };
}

for (const status of ["PENDING_CONFIRMATION", "CONFIRMED"]) {
  test(`paid ${status} appointments show only the patient actions allowed before or after reception confirmation`, async ({ page }) => {
    const { section, moves } = await mockDashboard(page, status);
    await expect(section.getByRole("button", { name: "Đổi lịch", exact: true })).toHaveCount(0);
    if (status === "CONFIRMED") {
      await expect(section.getByRole("button", { name: "Hủy lịch", exact: true })).toHaveCount(0);
      await expect(section.getByRole("button", { name: "Liên hệ lễ tân để đổi hoặc hủy lịch", exact: true })).toBeVisible();
    } else {
      await expect(section.getByRole("button", { name: "Liên hệ lễ tân để đổi lịch", exact: true })).toBeVisible();
      await section.getByRole("button", { name: "Hủy lịch", exact: true }).click();
      await expect(section.getByText(/Hủy lịch không tự động hoàn tiền/)).toBeVisible();
    }
    expect(moves).toEqual([]);
  });
}

test("rescheduling displays neutral instructions and a handled error when the selected slot is rejected", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const { section, moves } = await mockDashboard(page, "PENDING", true);
  await section.getByRole("button", { name: "Đổi lịch", exact: true }).click();
  await section.getByLabel("Thời gian mong muốn", { exact: true }).fill("2030-11-11T07:00");
  await section.getByRole("button", { name: "Tìm giờ khám", exact: true }).click();
  const form = section.locator(".appointment-inline-form");
  await expect(form.locator(".appointment-reschedule-message")).toHaveClass(/is-info/);
  await expect(form.getByRole("status")).toHaveText("Chọn giờ khám mới phù hợp với bạn trong danh sách dưới đây.");
  await form.locator(".appointment-recommended-slot").click();
  await expect(form.getByRole("alert")).toContainText("Lịch hẹn hoặc khung giờ có thể đã thay đổi");
  await expect(form.getByRole("button", { name: "Đóng", exact: true })).toBeEnabled();
  await expect(section.getByText("Không thể kết nối dịch vụ.", { exact: true })).toHaveCount(0);
  expect(moves).toHaveLength(1);
  expect(errors).toEqual([]);
});

test("an unpaid appointment can move to a recommended slot and refresh the displayed appointment", async ({ page }) => {
  const { section, slot, moves } = await mockDashboard(page, "ASSIGNED");
  await section.getByRole("button", { name: "Đổi lịch", exact: true }).click();
  await section.getByLabel("Thời gian mong muốn", { exact: true }).fill("2030-11-11T07:00");
  await section.getByRole("button", { name: "Tìm giờ khám", exact: true }).click();
  await section.locator(".appointment-recommended-slot").click();
  await expect(section.getByText("Đã chuyển lịch khám sang khung giờ mới.", { exact: true })).toBeVisible();
  await expect(section.locator(".appointment-inline-form")).toHaveCount(0);
  expect(moves).toHaveLength(1);
  expect(moves[0].body).toEqual({ startAt: slot.startAt, endAt: slot.endAt });
  expect(moves[0].idempotencyKey).toBeTruthy();
});
