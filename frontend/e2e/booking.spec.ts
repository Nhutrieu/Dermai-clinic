import { expect, test, type Page } from "@playwright/test";
import {
  activeBookingsAt,
  activeUpcoming,
  beginHoldInUi,
  cleanupAppointment,
  cleanupHold,
  confirmHoldInUi,
  credentialsFromEnvironment,
  credentialsMissingReason,
  displayTime,
  findBookingCandidate,
  loginPatient,
  openBooking,
  patientSnapshot,
  responseBody,
  runtimeUnavailable,
  selectCandidateInUi,
  type Appointment,
} from "./support/clinic";

const patientOne = credentialsFromEnvironment(1);
const patientTwo = credentialsFromEnvironment(2);
const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";

async function skipWhenRuntimeIsUnavailable(request: Parameters<typeof runtimeUnavailable>[0]) {
  const reason = await runtimeUnavailable(request);
  if (!reason) return false;
  test.skip(true, reason);
  return true;
}

async function attachScreenshot(page: Page, name: string) {
  await test.info().attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
}

test.describe("critical patient booking journey", () => {
  test.skip(!patientOne, credentialsMissingReason([1]));

  test("E2E-BOOK-001: patient holds and confirms a real available slot", async ({ page, request }) => {
    if (await skipWhenRuntimeIsUnavailable(request)) return;

    await loginPatient(page, patientOne!);
    const snapshot = await patientSnapshot(page);
    const active = activeUpcoming(snapshot.appointments);
    if (active.length >= 3) {
      test.skip(true, "Tài khoản E2E Patient 1 đã có tối đa 3 lịch sắp tới; không thể tạo dữ liệu kiểm thử hợp lệ.");
      return;
    }

    const candidate = await findBookingCandidate(page, [active]);
    if (!candidate) {
      test.skip(true, "Không tìm thấy slot thật phù hợp trong cửa sổ E2E_SEARCH_DAYS.");
      return;
    }

    await openBooking(page);
    const reason = "E2E-BOOK-001 - kiểm thử luồng đặt lịch";
    let holdId: string | null = null;
    let appointmentId: string | null = null;

    try {
      const slotButton = await selectCandidateInUi(page, candidate);
      const holdResponse = await beginHoldInUi(page, slotButton, active.length);
      const held = await responseBody<Appointment>(holdResponse);
      expect(holdResponse.status(), JSON.stringify(held)).toBe(201);
      expect(held, "API giữ slot phải trả appointment HELD").not.toBeNull();
      holdId = held!.id;
      expect(held).toMatchObject({
        patientId: snapshot.patient.id,
        doctorId: candidate.doctor.id,
        startAt: candidate.slot.startAt,
        status: "HELD",
      });
      expect(held!.holdExpiresAt).toBeTruthy();
      await expect(page.getByText(/giữ riêng cho bạn trong 5 phút/i)).toBeVisible();
      const countdown = page.locator(".booking-hold-status strong");
      // Prove the UI is driven by the server hold expiry, not only a static success message.
      await expect(countdown).toHaveText(/^(?:5:00|4:[3-5]\d)$/);

      const confirmResponse = await confirmHoldInUi(page, holdId, reason);
      const booked = await responseBody<Appointment>(confirmResponse);
      expect(confirmResponse.status(), JSON.stringify(booked)).toBe(200);
      expect(booked, "API xác nhận hold phải trả appointment").not.toBeNull();
      appointmentId = booked!.id;
      holdId = null;
      expect(booked).toMatchObject({
        patientId: snapshot.patient.id,
        doctorId: candidate.doctor.id,
        startAt: candidate.slot.startAt,
        status: "ASSIGNED",
        reason,
      });
      await expect(page.getByText("Đã gửi yêu cầu đặt lịch", { exact: false })).toBeVisible();
      await expect(page.getByText(reason, { exact: true })).toBeVisible();

      await test.info().attach("booking-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-BOOK-001",
          appointmentId,
          patientId: snapshot.patient.id,
          doctorId: candidate.doctor.id,
          startAt: candidate.slot.startAt,
          actualStatus: booked!.status,
        }, null, 2)),
        contentType: "application/json",
      });
      await attachScreenshot(page, "booking-confirmed.png");
    } finally {
      if (appointmentId) await cleanupAppointment(page, appointmentId);
      else if (holdId) await cleanupHold(page, holdId);
    }
  });
});

test.describe("same-slot concurrency", () => {
  test.skip(!patientOne || !patientTwo, credentialsMissingReason([1, 2]));
  test.skip(
    Boolean(patientOne && patientTwo && patientOne.email.toLocaleLowerCase() === patientTwo.email.toLocaleLowerCase()),
    "Hai tài khoản E2E phải có email khác nhau để chứng minh cách ly bệnh nhân.",
  );

  test("E2E-BOOK-002: exactly one of two patients can hold and book the same slot", async ({ browser, page, request }) => {
    if (await skipWhenRuntimeIsUnavailable(request)) return;

    // A separate browser context prevents JWT/sessionStorage and realtime state leaking between patients.
    const secondContext = await browser.newContext({
      baseURL,
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
      viewport: { width: 1440, height: 1000 },
    });
    const secondPage = await secondContext.newPage();
    const pages = [page, secondPage] as const;
    const holdIds: Array<string | null> = [null, null];
    let appointmentId: string | null = null;
    let winnerIndex: 0 | 1 | null = null;

    try {
      await Promise.all([
        loginPatient(page, patientOne!),
        loginPatient(secondPage, patientTwo!),
      ]);
      const [firstSnapshot, secondSnapshot] = await Promise.all([
        patientSnapshot(page),
        patientSnapshot(secondPage),
      ]);
      if (firstSnapshot.patient.identityId === secondSnapshot.patient.identityId) {
        test.skip(true, "Hai credential E2E cùng ánh xạ tới một patient identity; không thể kiểm tra tranh chấp liên bệnh nhân.");
        return;
      }

      const firstActive = activeUpcoming(firstSnapshot.appointments);
      const secondActive = activeUpcoming(secondSnapshot.appointments);
      if (firstActive.length >= 3 || secondActive.length >= 3) {
        test.skip(true, "Ít nhất một tài khoản E2E đã đạt giới hạn 3 lịch sắp tới.");
        return;
      }

      const candidate = await findBookingCandidate(page, [firstActive, secondActive]);
      if (!candidate) {
        test.skip(true, "Không tìm thấy slot thật mà cả hai Patient đều đủ điều kiện đặt.");
        return;
      }

      await Promise.all([openBooking(page), openBooking(secondPage)]);
      const [firstSlotButton, secondSlotButton] = await Promise.all([
        selectCandidateInUi(page, candidate),
        selectCandidateInUi(secondPage, candidate),
      ]);

      // Both clicks start from the same AVAILABLE snapshot; the server/database decides the winner.
      const holdAttempts = await Promise.allSettled([
        beginHoldInUi(page, firstSlotButton, firstActive.length, { programmatic: true }),
        beginHoldInUi(secondPage, secondSlotButton, secondActive.length, { programmatic: true }),
      ]);
      const holdResponses = holdAttempts.map(result => result.status === "fulfilled" ? result.value : null);
      const holdBodies = await Promise.all(holdResponses.map(response => response
        ? responseBody<Appointment & { code?: string; detail?: string }>(response)
        : null));
      holdResponses.forEach((response, index) => {
        if (response?.status() === 201 && holdBodies[index]?.id) holdIds[index] = holdBodies[index]!.id;
      });
      const holdFailures = holdAttempts
        .filter((result): result is PromiseRejectedResult => result.status === "rejected")
        .map(result => String(result.reason));
      expect(holdFailures, JSON.stringify(holdBodies)).toHaveLength(0);

      const successIndexes = holdResponses
        .map((response, index) => ({ status: response?.status(), index }))
        .filter(result => result.status === 201)
        .map(result => result.index);
      const conflictIndexes = holdResponses
        .map((response, index) => ({ status: response?.status(), index }))
        .filter(result => result.status === 409)
        .map(result => result.index);
      expect(successIndexes, JSON.stringify(holdBodies)).toHaveLength(1);
      expect(conflictIndexes, JSON.stringify(holdBodies)).toHaveLength(1);
      winnerIndex = successIndexes[0] as 0 | 1;
      const loserIndex = conflictIndexes[0] as 0 | 1;
      expect(String(holdBodies[loserIndex]?.code || ""), JSON.stringify(holdBodies[loserIndex])).toMatch(/CONFLICT|NOT_AVAILABLE/);
      await expect(pages[loserIndex].locator(".booking-feedback-error")).toBeVisible();

      const winnerPage = pages[winnerIndex];
      const winningHoldId = holdIds[winnerIndex]!;
      const reason = "E2E-BOOK-002 - kiểm thử hai bệnh nhân tranh cùng slot";
      const confirmResponse = await confirmHoldInUi(winnerPage, winningHoldId, reason);
      const booked = await responseBody<Appointment>(confirmResponse);
      expect(confirmResponse.status(), JSON.stringify(booked)).toBe(200);
      expect(booked).not.toBeNull();
      appointmentId = booked!.id;
      holdIds[winnerIndex] = null;
      expect(booked).toMatchObject({
        doctorId: candidate.doctor.id,
        startAt: candidate.slot.startAt,
        status: "ASSIGNED",
      });

      await expect(pages[loserIndex].getByRole("button", {
        name: `${displayTime(candidate.slot.startAt)}, Đã có người đặt`,
        exact: true,
      })).toBeVisible({ timeout: 15_000 });

      const [firstBookings, secondBookings] = await Promise.all([
        activeBookingsAt(page, candidate.doctor.id, candidate.slot.startAt),
        activeBookingsAt(secondPage, candidate.doctor.id, candidate.slot.startAt),
      ]);
      expect(firstBookings.length + secondBookings.length).toBe(1);
      expect((winnerIndex === 0 ? firstBookings : secondBookings)).toHaveLength(1);
      expect((loserIndex === 0 ? firstBookings : secondBookings)).toHaveLength(0);

      await test.info().attach("same-slot-race-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-BOOK-002",
          doctorId: candidate.doctor.id,
          startAt: candidate.slot.startAt,
          holdHttpStatuses: holdResponses.map(response => response?.status() || null),
          winnerPatient: winnerIndex + 1,
          bookedAppointmentsAcrossPatients: firstBookings.length + secondBookings.length,
          appointmentId,
        }, null, 2)),
        contentType: "application/json",
      });
      await Promise.all([
        attachScreenshot(winnerPage, "same-slot-winner.png"),
        attachScreenshot(pages[loserIndex], "same-slot-loser.png"),
      ]);
    } finally {
      const cleanupErrors: Error[] = [];
      if (appointmentId && winnerIndex !== null) {
        try { await cleanupAppointment(pages[winnerIndex], appointmentId); }
        catch (error) { cleanupErrors.push(error as Error); }
      }
      for (const index of [0, 1] as const) {
        if (!holdIds[index]) continue;
        try { await cleanupHold(pages[index], holdIds[index]!); }
        catch (error) { cleanupErrors.push(error as Error); }
      }
      await secondContext.close();
      if (cleanupErrors.length) throw new AggregateError(cleanupErrors, "Không dọn sạch được dữ liệu E2E.");
    }
  });
});
