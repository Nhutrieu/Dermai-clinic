import { expect, test, type Page } from "@playwright/test";
import type { AiAssessment } from "../src/core/types";

const latest: AiAssessment = {
  id: "latest-assessment", patientId: "patient-test", predictedLabel: "Acne",
  confidence: 0.8, top3: [{ label: "Acne", probability: 0.8 }], uncertain: false,
  modelVersion: "test", sharedWithDoctor: false, imageAvailable: true,
  createdAt: "2026-11-10T02:00:00Z",
};
const previous: AiAssessment = {
  ...latest, id: "previous-assessment", predictedLabel: "Eczema",
  imageAvailable: false, createdAt: "2026-09-07T02:00:00Z",
};

async function openDashboard(page: Page, assessments: AiAssessment[], failDelete = false) {
  const deleted: string[] = [];
  await page.addInitScript(() => {
    localStorage.setItem("dermai-session", JSON.stringify({
      accessToken: "dashboard-test", refreshToken: "dashboard-refresh",
      role: "PATIENT", expiresIn: 3600,
    }));
  });
  await page.routeWebSocket("**/api/v1/appointments/ws/**", socket => socket.close());
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "DELETE") {
      if (failDelete) {
        await route.fulfill({ status: 500, json: { detail: "Không thể xóa kết quả lúc này." } });
      } else {
        deleted.push(path.split("/").pop()!);
        await route.fulfill({ status: 204 });
      }
    } else if (path.endsWith("/patients/me/ai-assessments")) {
      await route.fulfill({ json: assessments.filter(item => !deleted.includes(item.id)) });
    } else if (path.endsWith("/image")) {
      await route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="red"/></svg>' });
    } else if (path.endsWith("/patients/me")) {
      await route.fulfill({ json: { id: "patient-test", identityId: "identity-test", fullName: "Bệnh nhân kiểm thử", dob: "2000-01-01", phone: "0900000000" } });
    } else if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { identityId: "identity-test", role: "PATIENT", status: "ACTIVE", hasAvatar: false } });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.goto("/");
  const section = page.getByRole("region", { name: "Phân tích da gần đây" });
  await expect(section.getByText("Mụn trứng cá", { exact: true })).toBeVisible();
  await expect(section.getByRole("img")).toBeVisible();
  return { section, deleted };
}

test("deleting the latest analysis waits for an explicit action before showing an older result", async ({ page }) => {
  const { section, deleted } = await openDashboard(page, [previous, latest]);
  await section.getByRole("button", { name: "Xóa kết quả", exact: true }).click();
  expect(deleted).toEqual([]);
  await section.getByRole("button", { name: "Xác nhận xóa", exact: true }).click();
  await expect(section.getByText("Đã xóa kết quả phân tích", { exact: true })).toBeVisible();
  expect(deleted).toEqual([latest.id]);
  await expect(section.getByRole("img")).toHaveCount(0);
  await expect(section.getByText("Chàm / viêm da dạng chàm", { exact: true })).toHaveCount(0);
  await expect(section.getByRole("button", { name: "Đặt lịch khám", exact: true })).toHaveCount(0);

  await section.getByRole("button", { name: "Xem kết quả trước đó", exact: true }).click();
  await expect(section.getByText("Chàm / viêm da dạng chàm", { exact: true })).toBeVisible();
  await expect(section.getByRole("img")).toHaveCount(0);
  await expect(section.getByText("Mụn trứng cá", { exact: true })).toHaveCount(0);
  await expect(section.getByText("Đã xóa kết quả phân tích", { exact: true })).toHaveCount(0);
});

test("deleting the only analysis offers a new analysis without an older result action", async ({ page }) => {
  const { section, deleted } = await openDashboard(page, [latest]);
  await section.getByRole("button", { name: "Xóa kết quả", exact: true }).click();
  await section.getByRole("button", { name: "Xác nhận xóa", exact: true }).click();
  await expect(section.getByText("Đã xóa kết quả phân tích", { exact: true })).toBeVisible();
  expect(deleted).toEqual([latest.id]);
  await expect(section.getByRole("button", { name: "Xem kết quả trước đó", exact: true })).toHaveCount(0);
  await section.getByRole("button", { name: "Phân tích ảnh mới", exact: true }).click();
  await expect(page.getByRole("button", { name: "KHỞI TẠO PHÂN TÍCH AI", exact: true })).toBeVisible();
});

test("cancelling or failing deletion preserves the current analysis and its image", async ({ page }) => {
  const { section, deleted } = await openDashboard(page, [previous, latest], true);
  await section.getByRole("button", { name: "Xóa kết quả", exact: true }).click();
  await section.getByRole("button", { name: "Hủy", exact: true }).click();
  expect(deleted).toEqual([]);
  await expect(section.getByText("Mụn trứng cá", { exact: true })).toBeVisible();
  await section.getByRole("button", { name: "Xóa kết quả", exact: true }).click();
  await section.getByRole("button", { name: "Xác nhận xóa", exact: true }).click();
  await expect(section.getByRole("alert")).toBeVisible();
  await expect(section.getByText("Mụn trứng cá", { exact: true })).toBeVisible();
  await expect(section.getByRole("img")).toBeVisible();
  await expect(section.getByText("Đã xóa kết quả phân tích", { exact: true })).toHaveCount(0);
  expect(deleted).toEqual([]);
});
