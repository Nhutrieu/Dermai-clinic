import { expect, test, type Page } from "@playwright/test";
import type { Appointment } from "../src/core/types";
import { openAppointmentHistory, openBooking } from "./support/clinic";

function appointment(): Appointment {
  const start = Date.now() + 48 * 60 * 60_000;
  return {
    id: "appointment-test", patientId: "patient-test", doctorId: "doctor-test",
    startAt: new Date(start).toISOString(), endAt: new Date(start + 30 * 60_000).toISOString(),
    status: "CONFIRMED", createdAt: new Date().toISOString(), reason: "Khám da kiểm thử",
  };
}

async function mockPatient(page: Page, initial: Appointment[] = []) {
  let appointments = initial;
  const mutations: Array<{ path: string; body: unknown }> = [];
  await page.addInitScript(() => {
    localStorage.setItem("dermai-session", JSON.stringify({ accessToken: "history-test", refreshToken: "history-refresh", role: "PATIENT", expiresIn: 3600 }));
  });
  await page.routeWebSocket("**/api/v1/appointments/ws/**", socket => socket.close());
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET") mutations.push({ path, body: request.postData() ? request.postDataJSON() : null });
    if (path.endsWith("/patients/me")) {
      await route.fulfill({ json: { id: "patient-test", identityId: "identity-test", fullName: "Bệnh nhân kiểm thử", dob: "2000-01-01", phone: "0900000000" } });
    } else if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { identityId: "identity-test", role: "PATIENT", status: "ACTIVE", hasAvatar: false } });
    } else if (path.endsWith("/appointments/mine")) {
      await route.fulfill({ json: appointments });
    } else if (path.endsWith("/appointment-test/cancel")) {
      appointments = appointments.map(item => ({ ...item, status: "CANCELLED", cancellationInitiator: "PATIENT_REQUEST" }));
      await route.fulfill({ json: appointments[0] });
    } else if (path.endsWith("/appointment-test/hide")) {
      appointments = [];
      await route.fulfill({ status: 204 });
    } else if (path.endsWith("/refunds/request")) {
      await route.fulfill({ json: { amount: 100000, refundAmount: 100000, status: "REFUND_REQUESTED" } });
    } else if (path.includes("/payments/booking/")) {
      await route.fulfill({ json: { amount: 100000, status: "SUCCESS" } });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.goto("/");
  await expect(page.locator(".patient-dashboard")).toBeVisible();
  return mutations;
}

test("patient history submenu opens the list separately from booking and keeps cancellation and refund actions", async ({ page }) => {
  const mutations = await mockPatient(page, [{ ...appointment(), status: "PENDING_CONFIRMATION" }]);
  await openAppointmentHistory(page);
  await expect(page.getByRole("heading", { name: "Đặt lịch khám da liễu", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Lịch khám", exact: true })).toHaveAttribute("aria-current", "page");
  const row = page.locator('[data-appointment-id="appointment-test"]');
  await expect(row).toContainText("Khám da kiểm thử");
  await row.getByRole("button", { name: "Hủy lịch", exact: true }).click();
  await row.getByLabel("Lý do hủy").fill("Tôi muốn chọn ngày khám khác");
  await row.getByRole("button", { name: "Xác nhận hủy", exact: true }).click();
  await expect(row).toHaveCount(0);
  await page.getByRole("tab", { name: /^Lịch sử đặt lịch/ }).click();
  await expect(row.getByRole("button", { name: "Yêu cầu hoàn tiền cọc", exact: true })).toBeVisible();
  expect(mutations).toContainEqual({ path: "/api/v1/appointments/appointment-test/cancel", body: { reason: "Tôi muốn chọn ngày khám khác" } });
  await row.getByRole("button", { name: "Yêu cầu hoàn tiền cọc", exact: true }).click();
  await row.getByRole("button", { name: "Gửi yêu cầu", exact: true }).click();
  await expect(row.getByText("Đã gửi yêu cầu hoàn tiền", { exact: true })).toBeVisible();
  expect(mutations.some(item => item.path.endsWith("/refunds/request"))).toBe(true);
  await openBooking(page);
  await expect(page.getByRole("heading", { name: "Lịch đã đặt", exact: true })).toHaveCount(0);
});

test("history still supports deleting a completed appointment and opening a new booking", async ({ page }) => {
  const mutations = await mockPatient(page, [{ ...appointment(), status: "COMPLETED" }]);
  await openAppointmentHistory(page);
  await expect(page.getByText("Bạn chưa có lịch khám sắp tới", { exact: true })).toBeVisible();
  await expect(page.locator('[data-appointment-id="appointment-test"]')).toHaveCount(0);
  await page.getByRole("tab", { name: /^Lịch sử đặt lịch/ }).click();
  await page.getByRole("button", { name: /^Xóa lịch .* khỏi danh sách$/ }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Xóa khỏi danh sách", exact: true }).click();
  await expect(page.locator('[data-appointment-id="appointment-test"]')).toHaveCount(0);
  expect(mutations.some(item => item.path.endsWith("/appointment-test/hide"))).toBe(true);
  await page.getByRole("button", { name: "Đặt lịch mới", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Đặt lịch khám da liễu", exact: true })).toBeVisible();
});

test("a reception-confirmed appointment has no patient cancellation control in the booked appointment list", async ({ page }) => {
  const mutations = await mockPatient(page, [appointment()]);
  await openAppointmentHistory(page);
  const row = page.locator('[data-appointment-id="appointment-test"]');
  await expect(row.getByRole("button", { name: "Hủy lịch", exact: true })).toHaveCount(0);
  await expect(row.getByRole("button", { name: "Liên hệ lễ tân để đổi hoặc hủy lịch", exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
});

test("mobile navigation opens the booked appointments submenu and closes the drawer", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPatient(page, [appointment()]);
  await page.getByRole("button", { name: "Mở menu điều hướng", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Menu điều hướng", exact: true });
  await drawer.getByRole("button", { name: "Lịch khám", exact: true }).click();
  await drawer.getByRole("menuitem", { name: "Lịch đã đặt", exact: true }).click();
  await expect(drawer).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Lịch đã đặt", exact: true })).toBeVisible();
  await expect(page.locator('[data-appointment-id="appointment-test"]')).toBeVisible();
  await page.getByRole("tab", { name: /^Lịch sử đặt lịch/ }).click();
  await expect(page.locator('[data-appointment-id="appointment-test"]')).toHaveCount(0);
  await expect(page.getByText("Chưa có lịch sử đặt lịch", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("appointment-tabs-mobile.png"), fullPage: true, animations: "disabled" });
});

test("upcoming and history tabs have disjoint rows and reset filters and pagination when switching", async ({ page }) => {
  const statuses = ["PROPOSED", "PENDING", "ASSIGNED", "PENDING_PAYMENT", "PENDING_CONFIRMATION", "CONFIRMED", "CHECKED_IN", "IN_PROGRESS", "COMPLETED", "CANCELLED", "CANCELLED_EXPIRED", "NO_SHOW", "FOLLOW_UP_REQUIRED"];
  const fixtures = statuses.map((status, index) => ({
    ...appointment(), id: "case-" + status, status, reason: "Kiểm thử " + status,
    startAt: status === "IN_PROGRESS" ? "2020-01-01T08:00:00Z" : new Date(Date.now() + (index + 1) * 60 * 60_000).toISOString(),
  }));
  await mockPatient(page, fixtures);
  await openAppointmentHistory(page);
  const section = page.getByRole("region", { name: "Lịch đã đặt", exact: true });
  const rows = section.locator(".patient-appointment-row");
  const upcoming = section.getByRole("tab", { name: /^Lịch sắp tới/ });
  const history = section.getByRole("tab", { name: /^Lịch sử đặt lịch/ });
  await expect(upcoming).toHaveText("Lịch sắp tới8");
  await expect(history).toHaveText("Lịch sử đặt lịch5");
  await expect(upcoming).toHaveAttribute("aria-selected", "true");
  await expect(rows).toHaveCount(5);
  await section.getByRole("button", { name: "Xem thêm 3 lịch", exact: true }).click();
  await expect(rows).toHaveCount(8);
  const upcomingIds = await rows.evaluateAll(elements => elements.map(element => element.getAttribute("data-appointment-id")));
  expect(upcomingIds).toContain("case-IN_PROGRESS");
  await section.getByRole("combobox", { name: "Trạng thái", exact: true }).selectOption("PENDING_CONFIRMATION");
  await expect(rows).toHaveCount(1);
  await upcoming.focus();
  await page.keyboard.press("ArrowRight");
  await expect(history).toBeFocused();
  await expect(history).toHaveAttribute("aria-selected", "true");
  await expect(section.getByRole("combobox", { name: "Trạng thái", exact: true })).toHaveValue("ALL");
  await expect(rows).toHaveCount(5);
  const historyIds = await rows.evaluateAll(elements => elements.map(element => element.getAttribute("data-appointment-id")));
  expect(historyIds.some(id => upcomingIds.includes(id))).toBe(false);
  expect(historyIds).toContain("case-CANCELLED");
  expect(historyIds).toContain("case-COMPLETED");
  await page.screenshot({ path: test.info().outputPath("appointment-tabs-desktop.png"), fullPage: true, animations: "disabled" });
  await history.press("Home");
  await expect(upcoming).toBeFocused();
  await expect(rows).toHaveCount(5);
});
