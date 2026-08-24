import { expect, test, type Page, type Response } from "@playwright/test";
import {
  activeUpcoming,
  beginHoldInUi,
  browserApi,
  cleanupHold,
  cleanupVisitAppointment,
  confirmHoldInUi,
  credentialsFromEnvironment,
  credentialsMissingReason,
  findBookingCandidate,
  loginAs,
  openBooking,
  patientSnapshot,
  responseBody,
  roleCredentialsFromEnvironment,
  roleCredentialsMissingReason,
  runtimeUnavailable,
  selectCandidateInUi,
  type Appointment,
  type BookingCandidate,
  type Doctor,
} from "./support/clinic";

const patient = credentialsFromEnvironment(1);
const receptionist = roleCredentialsFromEnvironment("RECEPTIONIST");
const doctor = roleCredentialsFromEnvironment("DOCTOR");
const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const missingReasons = [
  !patient ? credentialsMissingReason([1]) : "",
  !receptionist || !doctor ? roleCredentialsMissingReason(["RECEPTIONIST", "DOCTOR"]) : "",
].filter(Boolean).join(" ");

function isApiResponse(response: Response, method: string, suffix: string) {
  return response.request().method() === method && new URL(response.url()).pathname.endsWith(suffix);
}

async function expectRoleNavigation(page: Page, roleLabel: string) {
  await expect(page.getByRole("navigation", { name: `Điều hướng ${roleLabel}` })).toBeVisible({ timeout: 15_000 });
}

test.describe("complete clinic visit lifecycle", () => {
  test.skip(Boolean(missingReasons), missingReasons);

  test("E2E-FLOW-001: booking through reception, consultation and patient review", async ({ browser, page, request }) => {
    test.setTimeout(180_000);
    const runtimeReason = await runtimeUnavailable(request);
    if (runtimeReason) {
      test.skip(true, runtimeReason);
      return;
    }

    const receptionistContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const doctorContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const receptionistPage = await receptionistContext.newPage();
    const doctorPage = await doctorContext.newPage();
    let holdId: string | null = null;
    let appointmentId: string | null = null;
    let medicalRecordId: string | null = null;

    try {
      await Promise.all([
        loginAs(page, patient!, "PATIENT"),
        loginAs(receptionistPage, receptionist!, "RECEPTIONIST"),
        loginAs(doctorPage, doctor!, "DOCTOR"),
      ]);

      const [patientState, doctorResult] = await Promise.all([
        patientSnapshot(page),
        browserApi<Doctor>(doctorPage, "/api/v1/doctors/me"),
      ]);
      expect(doctorResult.ok, JSON.stringify(doctorResult.body)).toBeTruthy();
      const active = activeUpcoming(patientState.appointments);
      if (active.length >= 3) {
        test.skip(true, "Patient E2E đã đạt giới hạn 3 lịch sắp tới.");
        return;
      }

      const reason = "E2E-FLOW-001 - hành trình khám hoàn chỉnh";
      const rejectedStartAts: string[] = [];
      let candidate: BookingCandidate | null = null;
      let held: Appointment | null = null;
      await openBooking(page);

      // Availability is a snapshot. If another request claims a slot between the GET and
      // the hold POST, refresh and try the next real slot instead of making the suite flaky.
      for (let attempt = 0; attempt < 3 && !held; attempt += 1) {
        candidate = await findBookingCandidate(page, [active], {
          doctorId: doctorResult.body.id,
          startDayOffset: 0,
          endDayOffset: 0,
          minimumLeadMinutes: 2,
          excludedStartAts: rejectedStartAts,
        });
        if (!candidate) {
          if (attempt === 0) {
            test.skip(true, "Bác sĩ E2E không có slot còn trống trong hôm nay; không thể kiểm tra check-in thật.");
            return;
          }
          break;
        }

        const slotButton = await selectCandidateInUi(page, candidate);
        const holdResponse = await beginHoldInUi(page, slotButton, active.length);
        const holdBody = await responseBody<Appointment>(holdResponse);
        if (holdResponse.status() === 201) {
          held = holdBody;
          holdId = held?.id || null;
          break;
        }
        if (holdResponse.status() !== 409) {
          expect(holdResponse.status(), JSON.stringify(holdBody)).toBe(201);
        }
        rejectedStartAts.push(candidate.slot.startAt);
        await page.reload();
        await expectRoleNavigation(page, "Bệnh nhân");
        await openBooking(page);
      }

      expect(held, `Không giữ được slot sau ${rejectedStartAts.length} xung đột availability.`).not.toBeNull();
      expect(candidate).not.toBeNull();
      expect(holdId).not.toBeNull();

      const bookingResponse = await confirmHoldInUi(page, holdId!, reason);
      const booked = await responseBody<Appointment>(bookingResponse);
      expect(bookingResponse.status(), JSON.stringify(booked)).toBe(200);
      expect(booked).not.toBeNull();
      appointmentId = booked!.id;
      holdId = null;
      expect(booked!.status).toBe("ASSIGNED");

      await receptionistPage.reload();
      await expectRoleNavigation(receptionistPage, "Lễ tân");
      await receptionistPage.getByRole("navigation", { name: "Điều hướng Lễ tân" })
        .getByRole("button", { name: "Yêu cầu đặt lịch", exact: true }).click();
      await expect(receptionistPage.getByRole("heading", { name: "Yêu cầu đặt lịch", exact: true })).toBeVisible();
      const requestRow = receptionistPage.locator(".reception-request-item")
        .filter({ hasText: reason })
        .filter({ has: receptionistPage.getByRole("button", { name: "Xác nhận lịch", exact: true }) });
      await expect(requestRow).toBeVisible({ timeout: 15_000 });
      const confirmResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/${appointmentId}/confirm`),
      );
      await requestRow.getByRole("button", { name: "Xác nhận lịch", exact: true }).click();
      const receptionConfirmResponse = await confirmResponsePromise;
      expect(receptionConfirmResponse.status()).toBe(200);
      expect((await responseBody<Appointment>(receptionConfirmResponse))?.status).toBe("CONFIRMED");

      await receptionistPage.getByRole("navigation", { name: "Điều hướng Lễ tân" })
        .getByRole("button", { name: "Lịch đã nhận", exact: true }).click();
      await expect(receptionistPage.getByRole("heading", { name: "Lịch đã được tiếp nhận" })).toBeVisible();
      const acceptedRow = receptionistPage.locator(`.accepted-appointment-item[data-appointment-id="${appointmentId}"]`);
      await expect(acceptedRow).toBeVisible({ timeout: 15_000 });
      await acceptedRow.locator("summary").click();
      const checkInResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/${appointmentId}/check-in`),
      );
      await acceptedRow.getByRole("button", { name: "Xác nhận đã đến", exact: true }).click();
      const checkInResponse = await checkInResponsePromise;
      expect(checkInResponse.status()).toBe(200);
      expect((await responseBody<Appointment>(checkInResponse))?.status).toBe("CHECKED_IN");
      await test.info().attach("visit-lifecycle-reception-check-in.png", {
        body: await receptionistPage.screenshot({ fullPage: true }),
        contentType: "image/png",
      });

      await doctorPage.reload();
      await expectRoleNavigation(doctorPage, "Bác sĩ");
      await doctorPage.getByRole("navigation", { name: "Điều hướng Bác sĩ" })
        .getByRole("button", { name: "Lịch khám", exact: true }).click();
      await expect(doctorPage.getByRole("heading", { name: "Lịch khám hôm nay" })).toBeVisible();
      const doctorRow = doctorPage.locator(".doctor-appointment-row")
        .filter({ hasText: reason })
        .filter({ has: doctorPage.getByRole("button", { name: "Bắt đầu khám", exact: true }) });
      await expect(doctorRow).toBeVisible({ timeout: 15_000 });
      const startResponsePromise = doctorPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/${appointmentId}/start`),
      );
      await doctorRow.getByRole("button", { name: "Bắt đầu khám", exact: true }).click();
      const startResponse = await startResponsePromise;
      expect(startResponse.status()).toBe(200);
      expect((await responseBody<Appointment>(startResponse))?.status).toBe("IN_PROGRESS");

      const consultation = doctorPage.getByRole("dialog", { name: new RegExp(`Ca khám: ${patientState.patient.fullName}`) });
      await expect(consultation).toBeVisible();
      await consultation.getByLabel("Chẩn đoán cuối", { exact: true }).fill("E2E: đánh giá da liễu đã hoàn tất");
      await consultation.getByLabel("Ghi chú lâm sàng", { exact: true }).fill("Hồ sơ sinh bởi E2E-FLOW-001.");
      const recordResponsePromise = doctorPage.waitForResponse(response =>
        isApiResponse(response, "POST", "/api/v1/medical-records"),
      );
      await consultation.getByRole("button", { name: "Ký hồ sơ", exact: true }).click();
      const recordResponse = await recordResponsePromise;
      const record = await responseBody<{ id: string }>(recordResponse);
      expect(recordResponse.status(), JSON.stringify(record)).toBe(201);
      medicalRecordId = record?.id || null;
      expect(medicalRecordId).toBeTruthy();

      const completeResponsePromise = doctorPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/${appointmentId}/complete`),
      );
      await consultation.getByRole("button", { name: "Hoàn thành không kê đơn", exact: true }).click();
      const completeResponse = await completeResponsePromise;
      expect(completeResponse.status()).toBe(200);
      expect((await responseBody<Appointment>(completeResponse))?.status).toBe("COMPLETED");
      await test.info().attach("visit-lifecycle-doctor-completed.png", {
        body: await doctorPage.screenshot({ fullPage: true }),
        contentType: "image/png",
      });

      await page.reload();
      await expectRoleNavigation(page, "Bệnh nhân");
      await openBooking(page);
      const patientRow = page.locator(`.patient-appointment-row[data-appointment-id="${appointmentId}"]`);
      await expect(patientRow).toBeVisible({ timeout: 15_000 });
      await patientRow.getByRole("button", { name: "Đánh giá phòng khám", exact: true }).click();
      // Opening the control re-renders the appointment actions; anchor subsequent steps to the open form itself.
      const reviewControl = page.locator(".appointment-review-control.is-open");
      await expect(reviewControl).toBeVisible();
      const rating = reviewControl.getByRole("combobox", { name: "Mức độ hài lòng", exact: true });
      await rating.selectOption({ value: "5" });
      await expect(rating).toHaveValue("5");
      await reviewControl.getByRole("textbox", { name: "Chia sẻ trải nghiệm", exact: true })
        .fill("Quy trình E2E từ đặt lịch đến hoàn tất hoạt động đúng.");
      const reviewResponsePromise = page.waitForResponse(response =>
        isApiResponse(response, "PUT", `/api/v1/appointments/reviews/${appointmentId}`),
      );
      await reviewControl.getByRole("button", { name: "Gửi đánh giá", exact: true }).click();
      const reviewResponse = await reviewResponsePromise;
      expect(reviewResponse.status()).toBe(200);
      await expect(patientRow.getByText("Cảm ơn bạn đã gửi đánh giá.", { exact: true })).toBeVisible();
      await expect(patientRow.getByRole("button", { name: "Đã đánh giá", exact: true })).toBeDisabled();

      await test.info().attach("visit-lifecycle-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-FLOW-001",
          appointmentId,
          medicalRecordId,
          doctorId: candidate!.doctor.id,
          startAt: candidate!.slot.startAt,
          finalStatus: "COMPLETED",
          reviewSubmitted: true,
        }, null, 2)),
        contentType: "application/json",
      });
      await test.info().attach("visit-lifecycle-completed.png", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    } finally {
      const cleanupErrors: Error[] = [];
      if (appointmentId) {
        try { await cleanupVisitAppointment(page, receptionistPage, doctorPage, appointmentId); }
        catch (error) { cleanupErrors.push(error as Error); }
      } else if (holdId) {
        try { await cleanupHold(page, holdId); }
        catch (error) { cleanupErrors.push(error as Error); }
      }
      if (medicalRecordId) {
        const hidden = await browserApi<unknown>(page, `/api/v1/medical-records/${medicalRecordId}/hide`, { method: "PATCH" });
        if (!hidden.ok) cleanupErrors.push(new Error(`Không thể ẩn hồ sơ E2E ${medicalRecordId}: HTTP ${hidden.status}.`));
      }
      await Promise.all([receptionistContext.close(), doctorContext.close()]);
      if (cleanupErrors.length) throw new AggregateError(cleanupErrors, "Không dọn sạch được dữ liệu lifecycle E2E.");
    }
  });
});
