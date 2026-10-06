import { expect, test, type Page } from "@playwright/test";
import {
  activeUpcoming,
  appointmentById,
  browserApi,
  cleanupAppointment,
  credentialsFromEnvironment,
  credentialsMissingReason,
  findBookingCandidate,
  hideAppointment,
  loginAs,
  patientSnapshot,
  roleCredentialsFromEnvironment,
  roleCredentialsMissingReason,
  runtimeUnavailable,
  type Appointment,
} from "./support/clinic";

type Payment = {
  id: string;
  bookingId: string;
  amount: number;
  orderCode: number;
  status: "PENDING" | "SUCCESS" | "CANCELLED" | "REFUND_REQUESTED" | "REFUNDED";
  checkoutUrl: string;
  refundAmount?: number;
  refundMethod?: string;
  refundRecipientName?: string;
};

const patient = credentialsFromEnvironment(1);
const receptionist = roleCredentialsFromEnvironment("RECEPTIONIST");
const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const missingReasons = [
  !patient ? credentialsMissingReason([1]) : "",
  !receptionist ? roleCredentialsMissingReason(["RECEPTIONIST"]) : "",
].filter(Boolean).join(" ");

async function createPendingPayment(page: Page, tag: string) {
  const snapshot = await patientSnapshot(page);
  const active = activeUpcoming(snapshot.appointments);
  if (active.length >= 3) throw new Error("Patient E2E đã đạt giới hạn 3 lịch sắp tới.");
  const candidate = await findBookingCandidate(page, [active]);
  if (!candidate) throw new Error("Không tìm thấy slot thật phù hợp cho payment E2E.");

  const hold = await browserApi<Appointment>(page, "/api/v1/appointments/holds", {
    method: "POST",
    body: {
      patientId: snapshot.patient.id,
      doctorId: candidate.doctor.id,
      doctorIdentityId: candidate.slot.doctorIdentityId,
      startAt: candidate.slot.startAt,
      endAt: candidate.slot.endAt,
    },
  });
  expect(hold.status, JSON.stringify(hold.body)).toBe(201);
  expect(hold.body.status).toBe("HELD");

  const confirmed = await browserApi<Appointment>(
    page,
    `/api/v1/appointments/holds/${hold.body.id}/confirm`,
    { method: "POST", body: { reason: tag } },
  );
  expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200);
  expect(confirmed.body.status).toBe("PENDING_PAYMENT");

  const payment = await browserApi<Payment>(page, "/api/v1/payments", {
    method: "POST",
    body: { bookingId: confirmed.body.id, recipientEmail: patient!.email },
  });
  expect(payment.status, JSON.stringify(payment.body)).toBe(201);
  expect(payment.body).toMatchObject({ bookingId: confirmed.body.id, status: "PENDING" });
  return { appointment: confirmed.body, payment: payment.body };
}

test.describe("payment cancellation and refund", () => {
  test.describe.configure({ mode: "serial" });
  test.skip(Boolean(missingReasons), missingReasons);

  test.beforeEach(async ({ request }) => {
    const reason = await runtimeUnavailable(request);
    test.skip(Boolean(reason), reason || "");
  });

  test("E2E-PAY-001: cancel return closes payment and releases appointment", async ({ page }) => {
    test.setTimeout(120_000);
    await loginAs(page, patient!, "PATIENT");
    let appointmentId: string | null = null;

    try {
      const created = await createPendingPayment(page, "E2E-PAY-001 - hủy tại cổng thanh toán");
      appointmentId = created.appointment.id;
      const orderCode = created.payment.orderCode;

      await page.goto(`/payment/cancel?orderCode=${orderCode}&cancel=true&status=CANCELLED`);
      await expect(page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" })).toBeVisible({ timeout: 30_000 });

      await expect.poll(async () => {
        const current = await browserApi<Payment>(page, `/api/v1/payments/booking/${appointmentId}`);
        return current.ok ? current.body.status : `HTTP_${current.status}`;
      }, { timeout: 15_000 }).toBe("CANCELLED");
      await expect.poll(async () => {
        const current = await appointmentById(page, appointmentId!);
        return current.ok ? current.body.status : `HTTP_${current.status}`;
      }, { timeout: 15_000 }).toBe("CANCELLED");
      await hideAppointment(page, appointmentId);

      await test.info().attach("payment-cancel-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-PAY-001",
          appointmentId,
          orderCode,
          paymentStatus: "CANCELLED",
          appointmentStatus: "CANCELLED",
        }, null, 2)),
        contentType: "application/json",
      });
      appointmentId = null;
    } finally {
      if (appointmentId) {
        const current = await appointmentById(page, appointmentId);
        if (current.ok && current.body.status === "CANCELLED") await hideAppointment(page, appointmentId);
        else await cleanupAppointment(page, appointmentId);
      }
    }
  });

  test("E2E-PAY-002: patient refund request is completed by reception", async ({ browser, page }) => {
    test.setTimeout(150_000);
    const receptionistContext = await browser.newContext({
      baseURL,
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
    });
    const receptionistPage = await receptionistContext.newPage();
    let appointmentId: string | null = null;

    try {
      await Promise.all([
        loginAs(page, patient!, "PATIENT"),
        loginAs(receptionistPage, receptionist!, "RECEPTIONIST"),
      ]);
      const created = await createPendingPayment(page, "E2E-PAY-002 - hoàn cọc theo chính sách");
      appointmentId = created.appointment.id;
      await page.goto(created.payment.checkoutUrl);
      await expect(page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" })).toBeVisible({ timeout: 30_000 });

      await expect.poll(async () => {
        const current = await browserApi<Payment>(page, `/api/v1/payments/booking/${appointmentId}`);
        return current.ok ? current.body.status : `HTTP_${current.status}`;
      }, { timeout: 15_000 }).toBe("SUCCESS");
      await expect.poll(async () => {
        const current = await appointmentById(page, appointmentId!);
        return current.ok ? current.body.status : `HTTP_${current.status}`;
      }, { timeout: 15_000 }).toBe("PENDING_CONFIRMATION");

      const cancelled = await browserApi<Appointment>(page, `/api/v1/appointments/${appointmentId}/cancel`, {
        method: "POST",
        body: { reason: "E2E-PAY-002 - bệnh nhân đổi kế hoạch" },
      });
      expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200);
      expect(cancelled.body.status).toBe("CANCELLED");

      const requested = await browserApi<Payment>(
        page,
        `/api/v1/payments/booking/${appointmentId}/refunds/request`,
        { method: "POST", body: { reason: "E2E-PAY-002 - yêu cầu hoàn cọc" } },
      );
      expect(requested.status, JSON.stringify(requested.body)).toBe(200);
      expect(requested.body).toMatchObject({
        status: "REFUND_REQUESTED",
        refundAmount: created.payment.amount,
      });

      for (let attempt = 0; attempt < 4; attempt += 1) {
        const toast = receptionistPage.locator(".reception-cancellation-toast");
        if (!await toast.isVisible().catch(() => false)) break;
        await toast.getByRole("button", { name: "Đóng thông báo", exact: true }).click();
        await receptionistPage.waitForTimeout(100);
      }
      await receptionistPage.getByRole("navigation", { name: "Điều hướng Lễ tân" })
        .getByRole("button", { name: "Tổng quan", exact: true }).click();
      await receptionistPage.getByRole("menuitem", { name: "Hoàn tiền", exact: true }).click();
      await expect(receptionistPage.getByRole("heading", { name: "Xử lý yêu cầu hoàn tiền", exact: true })).toBeVisible();
      const refundCard = receptionistPage.locator(".refund-list article")
        .filter({ hasText: String(created.payment.orderCode) });
      await expect(refundCard).toBeVisible({ timeout: 15_000 });
      await refundCard.locator(".refund-action select").selectOption("CASH");
      await refundCard.locator(".refund-recipient input").fill("Bệnh nhân E2E Một");
      const completeResponsePromise = receptionistPage.waitForResponse(response =>
        response.request().method() === "POST"
        && new URL(response.url()).pathname.endsWith(`/api/v1/payments/${created.payment.id}/refunds/complete`),
      );
      await refundCard.getByRole("button", { name: "Xác nhận đã hoàn", exact: true }).click();
      const completeResponse = await completeResponsePromise;
      const refunded = await completeResponse.json() as Payment;
      expect(completeResponse.status(), JSON.stringify(refunded)).toBe(200);
      expect(refunded).toMatchObject({
        status: "REFUNDED",
        refundMethod: "CASH",
        refundRecipientName: "Bệnh nhân E2E Một",
      });
      await expect.poll(async () => {
        const current = await browserApi<Payment>(page, `/api/v1/payments/booking/${appointmentId}`);
        return current.ok ? current.body.status : `HTTP_${current.status}`;
      }, { timeout: 15_000 }).toBe("REFUNDED");

      await hideAppointment(page, appointmentId);
      await test.info().attach("payment-refund-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-PAY-002",
          appointmentId,
          paymentId: created.payment.id,
          orderCode: created.payment.orderCode,
          refundAmount: created.payment.amount,
          finalStatus: "REFUNDED",
          refundMethod: "CASH",
        }, null, 2)),
        contentType: "application/json",
      });
      appointmentId = null;
    } finally {
      if (appointmentId) {
        const current = await appointmentById(page, appointmentId);
        if (current.ok && current.body.status === "CANCELLED") await hideAppointment(page, appointmentId);
        else await cleanupAppointment(page, appointmentId);
      }
      await receptionistContext.close();
    }
  });
});
