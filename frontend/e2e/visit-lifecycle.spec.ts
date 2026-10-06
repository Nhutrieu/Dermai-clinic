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
const pharmacist = roleCredentialsFromEnvironment("PHARMACIST");
const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const missingReasons = [
  !patient ? credentialsMissingReason([1]) : "",
  !receptionist || !doctor || !pharmacist ? roleCredentialsMissingReason(["RECEPTIONIST", "DOCTOR", "PHARMACIST"]) : "",
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
    test.setTimeout(240_000);
    const runtimeReason = await runtimeUnavailable(request);
    if (runtimeReason) {
      test.skip(true, runtimeReason);
      return;
    }

    const receptionistContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const doctorContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const pharmacistContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const receptionistPage = await receptionistContext.newPage();
    const doctorPage = await doctorContext.newPage();
    const pharmacistPage = await pharmacistContext.newPage();
    let holdId: string | null = null;
    let appointmentId: string | null = null;
    let medicalRecordId: string | null = null;
    let prescriptionId: string | null = null;
    let invoiceId: string | null = null;

    try {
      await Promise.all([
        loginAs(page, patient!, "PATIENT"),
        loginAs(receptionistPage, receptionist!, "RECEPTIONIST"),
        loginAs(doctorPage, doctor!, "DOCTOR"),
        loginAs(pharmacistPage, pharmacist!, "PHARMACIST"),
      ]);

      type InventoryProduct = { id: string; sku: string; name: string; currentQuantity: number };
      const productsResult = await browserApi<InventoryProduct[]>(pharmacistPage, "/api/v1/inventory/products");
      expect(productsResult.ok, JSON.stringify(productsResult.body)).toBeTruthy();
      let medicine = productsResult.body.find(item => item.sku === "E2E-HYDROCORT");
      if (!medicine) {
        const created = await browserApi<InventoryProduct>(pharmacistPage, "/api/v1/inventory/products", {
          method: "POST",
          body: {
            sku: "E2E-HYDROCORT",
            name: "Hydrocortisone E2E",
            unit: "tuýp",
            importPrice: 20000,
            sellingPrice: 35000,
            minThreshold: 5,
          },
        });
        expect(created.status, JSON.stringify(created.body)).toBe(201);
        medicine = created.body;
      }
      if (medicine.currentQuantity < 10) {
        const expires = new Date();
        expires.setUTCFullYear(expires.getUTCFullYear() + 1);
        const imported = await browserApi(pharmacistPage, "/api/v1/inventory/import-batch", {
          method: "POST",
          body: {
            productId: medicine.id,
            batchNumber: `E2E-${Date.now()}`,
            expiryDate: expires.toISOString().slice(0, 10),
            quantity: 100,
          },
        });
        expect(imported.status, JSON.stringify(imported.body)).toBe(201);
      }

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
      expect(booked!.status).toBe("PENDING_PAYMENT");

      await receptionistPage.reload();
      await expectRoleNavigation(receptionistPage, "Lễ tân");
      await receptionistPage.getByRole("navigation", { name: "Điều hướng Lễ tân" })
        .getByRole("button", { name: "Yêu cầu đặt lịch", exact: true }).click();
      await expect(receptionistPage.getByRole("heading", { name: "Yêu cầu đặt lịch", exact: true })).toBeVisible();
      const requestRow = receptionistPage.locator(".reception-request-item")
        .filter({ hasText: reason })
        .filter({ has: receptionistPage.getByRole("button", { name: "Xác nhận yêu cầu", exact: true }) });
      await expect(requestRow).toBeVisible({ timeout: 15_000 });
      const confirmResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/${appointmentId}/confirm`),
      );
      await requestRow.getByRole("button", { name: "Xác nhận yêu cầu", exact: true }).click();
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

      const medicineSearch = consultation.getByLabel("Tìm thuốc cho dòng 1", { exact: true });
      await medicineSearch.fill("Hydrocortisone E2E");
      await consultation.getByRole("option", { name: /Hydrocortisone E2E/ }).click();
      await consultation.getByLabel("Số lượng thuốc 1", { exact: true }).fill("2");
      await consultation.getByLabel("Liều dùng", { exact: true }).fill("Bôi một lớp mỏng");
      await consultation.getByLabel("Tần suất", { exact: true }).fill("2 lần/ngày");
      await consultation.getByLabel("Thời gian dùng", { exact: true }).fill("7 ngày");
      await consultation.getByLabel("Hướng dẫn riêng", { exact: true }).fill("Ngưng dùng nếu kích ứng.");
      await consultation.locator(".prescription-general-instructions textarea")
        .fill("Giữ vùng da sạch và tái khám khi triệu chứng tăng.");
      const prescriptionResponsePromise = doctorPage.waitForResponse(response =>
        isApiResponse(response, "POST", "/api/v1/prescriptions"),
      );
      await consultation.getByRole("button", { name: "Ký đơn thuốc", exact: true }).click();
      const prescriptionResponse = await prescriptionResponsePromise;
      const prescription = await responseBody<{ id: string; recordId: string; items: Array<{ drugName: string }> }>(prescriptionResponse);
      expect(prescriptionResponse.status(), JSON.stringify(prescription)).toBe(201);
      prescriptionId = prescription?.id || null;
      expect(prescription).toMatchObject({ recordId: medicalRecordId });
      expect(prescription?.items).toEqual(expect.arrayContaining([
        expect.objectContaining({ drugName: "Hydrocortisone E2E" }),
      ]));

      const firstService = consultation.locator(".doctor-service-options input[type=checkbox]").first();
      await expect(firstService).toBeVisible();
      await firstService.check();
      const servicesResponsePromise = doctorPage.waitForResponse(response =>
        isApiResponse(response, "PUT", `/api/v1/appointments/${appointmentId}/performed-services`),
      );
      await consultation.locator(".doctor-service-confirmation > footer button").click();
      const servicesResponse = await servicesResponsePromise;
      const confirmedServices = await responseBody<{ confirmedAt: string; items: Array<{ serviceId: string; unitPrice: number }> }>(servicesResponse);
      expect(servicesResponse.status(), JSON.stringify(confirmedServices)).toBe(200);
      expect(confirmedServices?.confirmedAt).toBeTruthy();
      expect(confirmedServices?.items).toHaveLength(1);

      const completeResponsePromise = doctorPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/${appointmentId}/complete`),
      );
      await consultation.getByRole("button", { name: "Hoàn thành ca khám", exact: true }).click();
      const completeResponse = await completeResponsePromise;
      expect(completeResponse.status()).toBe(200);
      expect((await responseBody<Appointment>(completeResponse))?.status).toBe("COMPLETED");
      await test.info().attach("visit-lifecycle-doctor-completed.png", {
        body: await doctorPage.screenshot({ fullPage: true }),
        contentType: "image/png",
      });

      await receptionistPage.getByRole("navigation", { name: "Điều hướng Lễ tân" })
        .getByRole("button", { name: "Hóa đơn", exact: true }).click();
      await expect(receptionistPage.getByRole("heading", { name: "Hóa đơn", exact: true })).toBeVisible();
      await receptionistPage.locator(".cashier-hero").getByRole("button", { name: "Làm mới", exact: true }).click();
      const appointmentPicker = receptionistPage.locator("#cashier-patient-picker");
      await appointmentPicker.fill(patientState.patient.fullName);
      const appointmentOption = receptionistPage.locator(".cashier-patient-results button").filter({ hasText: patientState.patient.fullName }).first();
      await expect(appointmentOption).toBeVisible({ timeout: 30_000 });
      await appointmentOption.click();
      const confirmedServicePanel = receptionistPage.locator(".cashier-services-confirmed");
      await expect(confirmedServicePanel.locator("li")).toHaveCount(1, { timeout: 15_000 });
      await expect(confirmedServicePanel.locator("input[type=checkbox]")).toHaveCount(0);
      const createInvoiceButton = receptionistPage.getByRole("button", { name: "Tạo hóa đơn", exact: true });
      await expect(createInvoiceButton).toBeEnabled({ timeout: 15_000 });
      const invoiceResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", "/api/v1/billing/invoices"),
      );
      await createInvoiceButton.click();
      const invoiceResponse = await invoiceResponsePromise;
      type Invoice = {
        id: string;
        status: "AWAITING_PAYMENT" | "PAID" | "DISPENSED";
        remainingAmount: number;
        medicineFulfillment: string;
        serviceItems: Array<{ serviceId: string; serviceName: string; unitPrice: number }>;
        items: Array<{ medicineName: string; prescribedQuantity: number }>;
      };
      let invoice = await responseBody<Invoice>(invoiceResponse);
      expect(invoiceResponse.status(), JSON.stringify(invoice)).toBe(201);
      expect(invoice).toMatchObject({
        medicineFulfillment: "CLINIC_PHARMACY",
        serviceItems: [expect.objectContaining({ serviceId: confirmedServices!.items[0].serviceId })],
        items: [expect.objectContaining({ medicineName: "Hydrocortisone E2E", prescribedQuantity: 2 })],
      });
      invoiceId = invoice!.id;

      const invoiceCard = receptionistPage.locator(".cashier-invoice")
        .filter({ hasText: `#${invoiceId.slice(0, 8).toUpperCase()}` });
      await expect(invoiceCard).toBeVisible({ timeout: 15_000 });
      await invoiceCard.getByRole("button", { name: "Xem chi tiết", exact: true }).click();
      if (invoice!.status === "AWAITING_PAYMENT") {
        const cashInput = invoiceCard.locator("footer label").filter({ hasText: "Khách đưa" }).locator("input");
        await cashInput.fill(String(invoice!.remainingAmount));
        const cashResponsePromise = receptionistPage.waitForResponse(response =>
          isApiResponse(response, "POST", `/api/v1/billing/invoices/${invoiceId}/cash`),
        );
        await invoiceCard.getByRole("button", { name: "Thu tiền mặt", exact: true }).click();
        const cashResponse = await cashResponsePromise;
        const receipt = await responseBody<{ invoice: Invoice }>(cashResponse);
        expect(cashResponse.status(), JSON.stringify(receipt)).toBe(200);
        invoice = receipt!.invoice;
      }
      expect(invoice!.status).toBe("PAID");
      await expect(invoiceCard.getByText("Đã chuyển sang quầy Dược", { exact: true })).toBeVisible({ timeout: 15_000 });

      await pharmacistPage.reload();
      await expectRoleNavigation(pharmacistPage, "Dược sĩ");
      await pharmacistPage.getByRole("navigation", { name: "Điều hướng Dược sĩ" })
        .getByRole("button", { name: "Đơn chờ xuất", exact: true }).click();
      await expect(pharmacistPage.getByRole("heading", { name: "Xuất thuốc an toàn, đúng lô", exact: true })).toBeVisible();
      const prescriptionCode = `RX-${invoiceId.slice(0, 8).toUpperCase()}`;
      const pharmacyRow = pharmacistPage.locator(".pharmacy-queue-item").filter({ hasText: prescriptionCode });
      await expect(pharmacyRow).toBeVisible({ timeout: 15_000 });
      await pharmacyRow.click();
      const dispenseResponsePromise = pharmacistPage.waitForResponse(response =>
        isApiResponse(response, "POST", "/api/v1/pharmacy/dispense"),
      );
      await pharmacistPage.getByRole("button", { name: "Xác nhận Xuất kho & Giao thuốc", exact: true }).click();
      const dispenseResponse = await dispenseResponsePromise;
      const dispensed = await responseBody<{ prescriptionId: string; status: string }>(dispenseResponse);
      expect(dispenseResponse.status(), JSON.stringify(dispensed)).toBe(200);
      expect(dispensed).toMatchObject({ prescriptionId: invoiceId, status: "DISPENSED" });
      const synchronizedInvoice = await browserApi<Invoice>(
        receptionistPage,
        `/api/v1/billing/invoices/${invoiceId}`,
      );
      expect(synchronizedInvoice.status, JSON.stringify(synchronizedInvoice.body)).toBe(200);
      expect(synchronizedInvoice.body.status).toBe("DISPENSED");

      await page.reload();
      await expectRoleNavigation(page, "Bệnh nhân");
      await page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" })
        .getByRole("button", { name: "Kết quả khám", exact: true }).click();
      await page.getByRole("menuitem", { name: "Kết quả khám", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Kết quả khám của bạn" })).toBeVisible();
      const medicalResult = page.locator(".patient-medical-list li").filter({ hasText: reason });
      await expect(medicalResult).toBeVisible({ timeout: 15_000 });
      await medicalResult.getByRole("button", { name: "Xem chi tiết", exact: true }).click();
      const medicalDetail = page.locator(".patient-medical-detail");
      await expect(medicalDetail.getByRole("heading", { name: "E2E: đánh giá da liễu đã hoàn tất", exact: true })).toBeVisible();
      await expect(medicalDetail.getByText("Hydrocortisone E2E", { exact: true })).toBeVisible();
      await expect(medicalDetail.getByRole("button", { name: "Xem và in đơn thuốc", exact: true })).toBeVisible();

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
          prescriptionId,
          invoiceId,
          doctorId: candidate!.doctor.id,
          startAt: candidate!.slot.startAt,
          finalStatus: "COMPLETED",
          invoiceStatus: "DISPENSED",
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
      await Promise.all([receptionistContext.close(), doctorContext.close(), pharmacistContext.close()]);
      if (cleanupErrors.length) throw new AggregateError(cleanupErrors, "Không dọn sạch được dữ liệu lifecycle E2E.");
    }
  });
});
