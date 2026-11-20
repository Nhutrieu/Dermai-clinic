import { expect, test, type Page } from "@playwright/test";

// Synthetic API fixtures exercise navigation and hold guards without creating real bookings or payments.
async function chatFixture(page: Page, mode: "available" | "stale" | "conflict" | "hold-race" | "existing-screen" = "available") {
  const date = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(Date.now() + 3 * 86400000));
  const startAt = new Date(date + "T09:00:00+07:00").toISOString();
  const endAt = new Date(Date.parse(startAt) + 1800000).toISOString();
  const option = { doctorId: "doctor-2", doctorName: "Bình", startAt, endAt };
  const slot = { ...option, doctorIdentityId: "doctor-2-identity", specialtyCode: "Da liễu", status: "AVAILABLE" };
  const accessToken = "test." + Buffer.from(JSON.stringify({ sub: "patient-identity", exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64") + ".signature";
  const tokens = { accessToken, refreshToken: "fixture-refresh", expiresIn: 3600, role: "PATIENT" };
  await page.addInitScript(tokens => localStorage.setItem("dermai-session", JSON.stringify(tokens)), tokens);
  const messages: Array<Record<string, unknown>> = [];
  const holds: Array<Record<string, unknown>> = [];
  const mutations: string[] = [];
  let held = false;
  let availabilityCalls = 0;
  let race = false;
  const active = mode === "conflict" ? [{ id: "conflict", patientId: "patient-1", doctorId: "doctor-1", startAt, endAt, status: "CONFIRMED" }] : [];
  await page.route("**/api/v1/**", async route => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace("/api/v1", "");
    let body: unknown = [];
    if (path === "/auth/me") body = { identityId: "patient-identity", displayName: "Patient Test", status: "ACTIVE", role: "PATIENT", hasAvatar: false };
    else if (path === "/auth/refresh") body = tokens;
    else if (path === "/patients/me") body = { id: "patient-1", identityId: "patient-identity", fullName: "Patient Test", phone: "0900000000" };
    else if (path === "/doctors") body = [{ id: "doctor-1", identityId: "doctor-1-identity", fullName: "An", specialtyCode: "Da liễu", consultationFee: 150000 }, { id: "doctor-2", identityId: "doctor-2-identity", fullName: "Bình", specialtyCode: "Da liễu", consultationFee: 150000 }];
    else if (path === "/appointments/mine") body = active;
    else if (path === "/payments/deposit-setting") body = { amount: 100000 };
    else if (path === "/appointments/support") body = messages;
    else if (path === "/appointments/support/conversations") body = [{ patientIdentityId: "patient-identity", channelStatus: "AI_ACTIVE", aiFailureCount: 0 }];
    else if (path === "/appointments/support/assistant") {
      const question = req.postDataJSON().question as string;
      const personal = question.includes("Lịch của tôi");
      const answer = personal ? "Lịch khám sắp tới của bạn: 09:00 · Bác sĩ Bình · Chờ lễ tân xác nhận · Đã cọc 100.000 đ" : "Bác sĩ Bình còn khung giờ 09:00. Chọn giờ bên dưới để tiếp tục.";
      const now = new Date().toISOString();
      messages.push({ id: "q" + messages.length, patientIdentityId: "patient-identity", senderRole: "PATIENT", body: question, sentAt: now, readAt: now });
      messages.push({ id: "a" + messages.length, patientIdentityId: "patient-identity", senderRole: "AI", body: answer, bookingOptions: personal ? [] : [option], sentAt: now, readAt: now });
      body = { answer, intent: personal ? "APPOINTMENT_STATUS" : "DOCTOR_AVAILABILITY", escalated: false, conversationStatus: "AI_ACTIVE", intentConfidence: .94 };
    } else if (path === "/appointments/availability") {
      availabilityCalls++;
      const doctorId = url.searchParams.get("doctorId");
      body = { status: "OPEN", timezone: "Asia/Ho_Chi_Minh", items: doctorId !== "doctor-2" ? [] : [{ ...slot, status: mode === "stale" || race ? "BOOKED" : held ? "HELD_BY_YOU" : "AVAILABLE", holdId: held ? "hold-2" : undefined, holdExpiresAt: held ? new Date(Date.now() + 300000).toISOString() : undefined }] };
    } else if (path === "/appointments/holds" && req.method() === "POST") {
      holds.push(req.postDataJSON());
      if (mode === "hold-race") {
        race = true;
        return route.fulfill({ status: 409, json: { detail: "SLOT_CONFLICT" } });
      }
      held = true;
      body = { id: "hold-2", ...req.postDataJSON(), status: "HELD", holdExpiresAt: new Date(Date.now() + 300000).toISOString(), consultationFeeSnapshot: 150000 };
    } else if (path === "/appointments/holds/hold-2" && req.method() === "DELETE") held = false;
    else if (req.method() === "POST" && (path.includes("confirm") || path === "/payments")) mutations.push(path);
    return route.fulfill({ json: body });
  });
  await page.goto(mode === "existing-screen" ? "/?doctorId=doctor-1&date=" + date : "/");
  await expect(page.getByRole("button", { name: "Hỗ trợ", exact: true })).toBeVisible();
  return { date, startAt, endAt, holds, mutations, get availabilityCalls() { return availabilityCalls; } };
}

async function ask(page: Page, question: string) {
  const panel = page.getByRole("region", { name: "Hỗ trợ Derm Clinic" });
  if (!await panel.isVisible()) await page.getByRole("button", { name: "Hỗ trợ", exact: true }).click();
  await panel.getByRole("textbox", { name: "Nội dung cần hỗ trợ" }).fill(question);
  await panel.getByRole("button", { name: "Gửi câu hỏi cho trợ lý hỗ trợ" }).click();
  return panel;
}

test("chat slot opens the matching doctor/date and holds only that time; options survive reload", async ({ page }) => {
  const fixture = await chatFixture(page);
  let panel = await ask(page, "Bác sĩ Bình còn giờ nào ngày mai?");
  await expect(panel.getByRole("group", { name: "Giờ khám được gợi ý" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Hỗ trợ", exact: true }).click();
  panel = page.getByRole("region", { name: "Hỗ trợ Derm Clinic" });
  await panel.getByRole("button", { name: /Đặt lịch với bác sĩ Bình lúc/ }).click();
  await expect(page.locator(".booking-doctor-selector button[aria-pressed=true]")).toContainText("Bình");
  await expect(page.locator("#booking-date")).toHaveValue(fixture.date);
  await expect.poll(() => fixture.holds.length).toBe(1);
  expect(fixture.holds[0]).toMatchObject({ patientId: "patient-1", doctorId: "doctor-2", startAt: fixture.startAt, endAt: fixture.endAt });
  await expect(page.getByText("Khung giờ được giữ riêng cho bạn trong 5 phút.", { exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.get("doctorId")).toBe("doctor-2");
  expect(fixture.mutations).toEqual([]);
});

for (const mode of ["stale", "hold-race", "conflict", "existing-screen"] as const) {
  test(`chat slot handles ${mode} safely`, async ({ page }) => {
    const fixture = await chatFixture(page, mode);
    if (mode === "existing-screen") await expect.poll(() => fixture.availabilityCalls).toBeGreaterThan(0);
    const panel = await ask(page, "Xem lịch bác sĩ Bình ngày mai");
    await panel.getByRole("button", { name: /Đặt lịch với bác sĩ Bình lúc/ }).click();
    await expect(page.locator(".booking-doctor-selector button[aria-pressed=true]")).toContainText("Bình");
    await expect(page.locator("#booking-date")).toHaveValue(fixture.date);
    if (mode === "stale") {
      await expect(page.getByText("Giờ bạn chọn trong chat hiện không còn trống. Vui lòng chọn giờ khác bên dưới.")).toBeVisible();
      expect(fixture.holds).toEqual([]);
    } else if (mode === "conflict") {
      await expect(page.getByRole("dialog")).toBeVisible();
      expect(fixture.holds).toEqual([]);
    } else if (mode === "hold-race") {
      await expect(page.getByText("Khung giờ này vừa được người khác chọn. Vui lòng chọn giờ khác.")).toBeVisible();
      expect(fixture.holds).toHaveLength(1);
    } else {
      await expect.poll(() => fixture.holds.length).toBe(1);
      expect(fixture.holds[0]).toMatchObject({ doctorId: "doctor-2", startAt: fixture.startAt });
    }
    expect(fixture.mutations).toEqual([]);
  });
}

test("patient can ask about existing appointments and deposit without leaving the chat", async ({ page }) => {
  await chatFixture(page);
  const panel = await ask(page, "Lịch của tôi khi nào?");
  await expect(panel.getByText(/Lịch khám sắp tới của bạn: 09:00 · Bác sĩ Bình · Chờ lễ tân xác nhận · Đã cọc 100.000 đ/)).toBeVisible();
  await expect(panel.getByRole("group", { name: "Giờ khám được gợi ý" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" }).getByRole("button", { name: "Tổng quan", exact: true })).toHaveAttribute("aria-current", "page");
});


test("chat slot buttons fit on mobile and open the selected time", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await chatFixture(page);
  const panel = await ask(page, "Bác sĩ Bình có giờ trống ngày mai không?");
  const button = panel.getByRole("button", { name: /Đặt lịch với bác sĩ Bình lúc/ });
  await expect(button).toBeVisible();
  const box = await button.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: "test-results/chat-booking/mobile-chat.png", fullPage: true });
  await button.click();
  await expect.poll(() => fixture.holds.length).toBe(1);
  expect(fixture.holds[0]).toMatchObject({ doctorId: "doctor-2", startAt: fixture.startAt });
});
