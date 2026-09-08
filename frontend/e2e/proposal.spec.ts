import { expect, test, type Page } from "@playwright/test";
import {
  browserApi,
  credentialsFromEnvironment,
  credentialsMissingReason,
  loginAs,
  patientSnapshot,
  roleCredentialsFromEnvironment,
  roleCredentialsMissingReason,
  runtimeUnavailable,
  type Appointment,
  type AvailabilitySlot,
  type Doctor,
} from "./support/clinic";

type AvailabilityResponse = { items: AvailabilitySlot[] };

const patient = credentialsFromEnvironment(1);
const receptionist = roleCredentialsFromEnvironment("RECEPTIONIST");
const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const missing = [
  !patient ? credentialsMissingReason([1]) : "",
  !receptionist ? roleCredentialsMissingReason(["RECEPTIONIST"]) : "",
].filter(Boolean).join(" ");

function clinicDate(daysFromToday: number) {
  const date = new Date(Date.now() + daysFromToday * 24 * 60 * 60 * 1000);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

async function availableSlot(page: Page, doctor: Doctor, daysFromToday: number) {
  const date = clinicDate(daysFromToday);
  const result = await browserApi<AvailabilityResponse>(
    page,
    `/api/v1/appointments/availability?doctorId=${encodeURIComponent(doctor.id)}&date=${date}`,
  );
  expect(result.ok, JSON.stringify(result.body)).toBeTruthy();
  return result.body.items.find(item => item.status === "AVAILABLE") || null;
}

test.describe("receptionist appointment proposals", () => {
  test.skip(Boolean(missing), missing);

  test("E2E-PROPOSAL-001: patient accepts one proposal and declines another", async ({ browser, page, request }) => {
    test.setTimeout(120_000);
    const runtimeReason = await runtimeUnavailable(request);
    if (runtimeReason) {
      test.skip(true, runtimeReason);
      return;
    }

    const receptionistContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const receptionistPage = await receptionistContext.newPage();
    const createdIds: string[] = [];

    try {
      await Promise.all([
        loginAs(page, patient!, "PATIENT"),
        loginAs(receptionistPage, receptionist!, "RECEPTIONIST"),
      ]);
      const [patientState, doctorResult] = await Promise.all([
        patientSnapshot(page),
        browserApi<Doctor[]>(receptionistPage, "/api/v1/doctors"),
      ]);
      expect(doctorResult.ok, JSON.stringify(doctorResult.body)).toBeTruthy();
      const doctor = doctorResult.body[0];
      expect(doctor).toBeTruthy();

      const createProposal = async (daysFromToday: number, reason: string) => {
        const slot = await availableSlot(receptionistPage, doctor, daysFromToday);
        expect(slot, `Không có slot trống ngày ${clinicDate(daysFromToday)}.`).not.toBeNull();
        const result = await browserApi<Appointment>(receptionistPage, "/api/v1/appointments/proposals", {
          method: "POST",
          body: {
            patientId: patientState.patient.id,
            patientIdentityId: patientState.patient.identityId,
            doctorId: slot!.doctorId,
            doctorIdentityId: slot!.doctorIdentityId,
            startAt: slot!.startAt,
            endAt: slot!.endAt,
            reason,
          },
        });
        expect(result.status, JSON.stringify(result.body)).toBe(201);
        expect(result.body.status).toBe("PROPOSED");
        createdIds.push(result.body.id);
        return result.body;
      };

      const respondInUi = async (proposal: Appointment, action: "accept" | "decline") => {
        await page.reload();
        await expect(page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" })).toBeVisible();
        await page.getByRole("button", { name: "Thông báo lịch khám", exact: true }).click();
        const actionLabel = action === "accept" ? "Xác nhận thông tin" : "Thông tin chưa đúng";
        const responsePromise = page.waitForResponse(response => (
          response.request().method() === "POST"
          && new URL(response.url()).pathname.endsWith(`/api/v1/appointments/proposals/${proposal.id}/${action}`)
        ));
        await page.getByRole("button", { name: actionLabel, exact: true }).click();
        const response = await responsePromise;
        const body = await response.json() as Appointment;
        expect(response.status(), JSON.stringify(body)).toBe(200);
        return body;
      };

      const acceptedProposal = await createProposal(1, "E2E-PROPOSAL-001 - nhánh chấp nhận");
      const accepted = await respondInUi(acceptedProposal, "accept");
      expect(accepted.status).toBe("CONFIRMED");
      await expect(page.getByText("Đã xác nhận thông tin lịch khám.", { exact: true })).toBeVisible();

      const cancelled = await browserApi<Appointment>(receptionistPage, `/api/v1/appointments/${accepted.id}/cancel`, {
        method: "POST",
        body: { reason: "E2E_CLEANUP_BEFORE_DECLINE_BRANCH" },
      });
      expect(cancelled.ok, JSON.stringify(cancelled.body)).toBeTruthy();
      const hidden = await browserApi<unknown>(page, `/api/v1/appointments/${accepted.id}/hide`, { method: "PATCH" });
      expect(hidden.ok, JSON.stringify(hidden.body)).toBeTruthy();
      createdIds.splice(createdIds.indexOf(accepted.id), 1);

      const declinedProposal = await createProposal(2, "E2E-PROPOSAL-001 - nhánh từ chối");
      const declined = await respondInUi(declinedProposal, "decline");
      expect(declined.status).toBe("CANCELLED");
      await expect(page.getByText("Đã báo thông tin chưa đúng và chuyển yêu cầu đến lễ tân.", { exact: true })).toBeVisible();
      createdIds.splice(createdIds.indexOf(declined.id), 1);

      await test.info().attach("proposal-decisions-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-PROPOSAL-001",
          acceptedProposalId: accepted.id,
          acceptedFinalStatus: accepted.status,
          declinedProposalId: declined.id,
          declinedFinalStatus: declined.status,
          separateProposalsUsed: true,
        }, null, 2)),
        contentType: "application/json",
      });
      await test.info().attach("proposal-decisions-patient.png", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    } finally {
      const cleanupErrors: Error[] = [];
      for (const id of createdIds) {
        const cancelled = await browserApi<Appointment>(receptionistPage, `/api/v1/appointments/${id}/cancel`, {
          method: "POST",
          body: { reason: "E2E_CLEANUP" },
        });
        if (!cancelled.ok && cancelled.status !== 409) {
          cleanupErrors.push(new Error(`Không thể hủy proposal E2E ${id}: HTTP ${cancelled.status}.`));
          continue;
        }
        const hidden = await browserApi<unknown>(page, `/api/v1/appointments/${id}/hide`, { method: "PATCH" });
        if (!hidden.ok && hidden.status !== 404) cleanupErrors.push(new Error(`Không thể ẩn proposal E2E ${id}: HTTP ${hidden.status}.`));
      }
      await receptionistContext.close();
      if (cleanupErrors.length) throw new AggregateError(cleanupErrors, "Không dọn sạch được dữ liệu proposal E2E.");
    }
  });
});
