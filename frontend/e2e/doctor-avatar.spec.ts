import { expect, test, type Page } from "@playwright/test";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3ioAAAAASUVORK5CYII=", "base64");
const oldPhoto = { name: "anh-cu.png", mimeType: "image/png", buffer: Buffer.concat([png, Buffer.alloc(1536 * 1024 - png.length)]) };
const otherPhoto = { name: "anh-khac.png", mimeType: "image/png", buffer: png };

async function openDoctorProfile(page: Page, rejectUpload = false) {
  let uploads = 0;
  let doctor = { id: "doctor-test", identityId: "doctor-identity", fullName: "Bình", specialtyCode: "Da liễu", experienceYears: 6, consultationFee: 150000, avatarUrl: "/api/v1/doctors/doctor-test/avatar?v=0" };
  await page.addInitScript(() => localStorage.setItem("dermai-session", JSON.stringify({ accessToken: "avatar-test", refreshToken: "avatar-refresh", role: "DOCTOR", expiresIn: 3600 })));
  await page.routeWebSocket("**/api/v1/**", socket => socket.close());
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/doctors/me/avatar") && request.method() === "POST") {
      uploads++;
      if (rejectUpload) {
        await route.fulfill({ status: 413, json: { status: 413, error: "Payload Too Large" } });
      } else {
        doctor = { ...doctor, avatarUrl: "/api/v1/doctors/doctor-test/avatar?v=" + uploads };
        await route.fulfill({ json: doctor });
      }
    } else if (path.endsWith("/doctors/me/personal")) {
      doctor = { ...doctor, ...request.postDataJSON() };
      await route.fulfill({ json: doctor });
    } else if (path.endsWith("/doctors/me")) {
      await route.fulfill({ json: doctor });
    } else if (path.endsWith("/doctors/me/schedule")) {
      await route.fulfill({ json: { workSchedules: [], leavePeriods: [] } });
    } else if (path.endsWith("/avatar")) {
      await route.fulfill({ contentType: "image/png", body: png });
    } else if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { identityId: doctor.identityId, role: "DOCTOR", status: "ACTIVE", hasAvatar: false } });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Thông tin cá nhân", exact: true })).toBeVisible();
  return () => uploads;
}

test("a doctor can replace the avatar and then select the same old photo again", async ({ page }) => {
  const uploads = await openDoctorProfile(page);
  for (const [index, photo] of [oldPhoto, otherPhoto, oldPhoto, oldPhoto].entries()) {
    await page.getByRole("button", { name: "Chỉnh sửa thông tin cá nhân", exact: true }).click();
    const input = page.locator('.doctor-profile-avatar-picker input[type="file"]');
    await input.setInputFiles(photo);
    await expect(input).toHaveValue("");
    await page.locator(".doctor-profile-bio-form").getByRole("button", { name: "Lưu", exact: true }).click();
    await expect(page.getByText("Đã lưu thông tin cá nhân.", { exact: true })).toBeVisible();
    await expect(page.locator(".doctor-profile-avatar-picker img")).toHaveAttribute("src", `/api/v1/doctors/doctor-test/avatar?v=${index + 1}`);
    await expect(page.locator(".app-user-trigger img")).toHaveAttribute("src", `/api/v1/doctors/doctor-test/avatar?v=${index + 1}`);
  }
  expect(uploads()).toBe(4);
});

test("an upload size rejection displays the image limit instead of a connection error", async ({ page }) => {
  await openDoctorProfile(page, true);
  await page.getByRole("button", { name: "Chỉnh sửa thông tin cá nhân", exact: true }).click();
  await page.locator('.doctor-profile-avatar-picker input[type="file"]').setInputFiles(oldPhoto);
  await page.locator(".doctor-profile-bio-form").getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Ảnh đại diện tối đa 2 MB");
  await expect(page.getByText("Không thể kết nối dịch vụ.", { exact: true })).toHaveCount(0);
  await expect(page.locator(".app-user-trigger img")).toHaveAttribute("src", "/api/v1/doctors/doctor-test/avatar?v=0");
});

test("invalid avatar files are rejected before upload and can be replaced with a valid photo", async ({ page }) => {
  const uploads = await openDoctorProfile(page);
  await page.getByRole("button", { name: "Chỉnh sửa thông tin cá nhân", exact: true }).click();
  const input = page.locator('.doctor-profile-avatar-picker input[type="file"]');
  await input.setInputFiles({ name: "qua-lon.png", mimeType: "image/png", buffer: Buffer.alloc(2 * 1024 * 1024 + 1) });
  await expect(page.getByRole("alert")).toContainText("Ảnh đại diện tối đa 2 MB");
  await input.setInputFiles({ name: "khong-phai-anh.txt", mimeType: "text/plain", buffer: Buffer.from("test") });
  await expect(page.getByRole("alert")).toContainText("Chỉ nhận ảnh JPG, PNG hoặc WebP");
  expect(uploads()).toBe(0);
  await input.setInputFiles(otherPhoto);
  await page.locator(".doctor-profile-bio-form").getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText("Đã lưu thông tin cá nhân.", { exact: true })).toBeVisible();
  expect(uploads()).toBe(1);
});
