import { existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Response } from "@playwright/test";
import {
  browserApi,
  credentialsFromEnvironment,
  credentialsMissingReason,
  loginAs,
  patientSnapshot,
  responseBody,
  roleCredentialsFromEnvironment,
  roleCredentialsMissingReason,
  runtimeUnavailable,
} from "./support/clinic";

type AiAssessment = {
  id: string;
  predictedLabel: string;
  sharedWithDoctor: boolean;
  imageAvailable: boolean;
  modelVersion: string;
};

type AiPrediction = {
  disease: string;
  confidence: number;
  top3: Array<{ label: string; probability: number }>;
  gradcam_image: string;
  model_version: string;
};
type AiAnalysisResponse = { assessment: AiAssessment; prediction: AiPrediction };

type SupportConversation = {
  patientIdentityId: string;
  assignedReceptionistIdentityId?: string | null;
  channelStatus: "AI_ACTIVE" | "WAITING_RECEPTIONIST" | "ASSIGNED";
};

const patient = credentialsFromEnvironment(1);
const receptionist = roleCredentialsFromEnvironment("RECEPTIONIST");
const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const configuredImagePath = process.env.E2E_AI_IMAGE_PATH?.trim();
const imagePath = resolve(configuredImagePath || "e2e/fixtures/synthetic-eczema-e2e.png");
const imageProblem = !existsSync(imagePath)
    ? `Không tìm thấy ảnh E2E tại ${imagePath}.`
    : statSync(imagePath).size > 10 * 1024 * 1024
      ? "Ảnh E2E vượt giới hạn upload 10 MB."
      : "";

function isApiResponse(response: Response, method: string, suffix: string) {
  return response.request().method() === method && new URL(response.url()).pathname.endsWith(suffix);
}

test.describe("AI assessment persistence and sharing consent", () => {
  const missing = [!patient ? credentialsMissingReason([1]) : "", imageProblem].filter(Boolean).join(" ");
  test.skip(Boolean(missing), missing);

  test("E2E-AI-001: patient uploads a real image and opts in to appointment sharing", async ({ page, request }) => {
    test.setTimeout(180_000);
    const runtimeReason = await runtimeUnavailable(request);
    if (runtimeReason) {
      test.skip(true, runtimeReason);
      return;
    }
    const health = await request.get("/ai/health", { failOnStatusCode: false, timeout: 10_000 });
    if (!health.ok()) {
      test.skip(true, `AI runtime không sẵn sàng (GET /ai/health trả HTTP ${health.status()}).`);
      return;
    }
    const healthBody = await health.json() as { modelReady?: boolean };
    if (!healthBody.modelReady) {
      test.skip(true, "AI runtime đang chạy nhưng checkpoint chưa được nạp (modelReady=false).");
      return;
    }

    await loginAs(page, patient!, "PATIENT");
    const before = await browserApi<AiAssessment[]>(page, "/api/v1/patients/me/ai-assessments");
    expect(before.ok, JSON.stringify(before.body)).toBeTruthy();
    let assessmentId: string | null = null;

    try {
      await page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" })
        .getByRole("button", { name: "Kiểm tra da AI", exact: true }).click();
      await page.locator('input[type="file"]').setInputFiles(imagePath!);
      await page.getByRole("checkbox", { name: /Cho phép chia sẻ với bác sĩ khi đặt lịch/ }).check();

      const analyzePromise = page.waitForResponse(
        response => isApiResponse(response, "POST", "/api/v1/patients/me/ai-assessments/analyze"),
        { timeout: 120_000 },
      );
      page.once("dialog", dialog => void dialog.accept());
      await page.getByRole("button", { name: /KHỞI TẠO PHÂN TÍCH AI/i }).click();

      const analyzeResponse = await analyzePromise;
      const analyzed = await responseBody<AiAnalysisResponse>(analyzeResponse);
      expect(analyzeResponse.status(), JSON.stringify(analyzed)).toBe(201);
      expect(analyzed).not.toBeNull();
      const prediction = analyzed!.prediction;
      const saved = analyzed!.assessment;
      expect(prediction.disease).not.toHaveLength(0);
      expect(prediction.confidence).toBeGreaterThanOrEqual(0);
      expect(prediction.confidence).toBeLessThanOrEqual(1);
      expect(prediction.top3).toHaveLength(3);
      prediction.top3.forEach(item => {
        expect(item.label).not.toHaveLength(0);
        expect(item.probability).toBeGreaterThanOrEqual(0);
        expect(item.probability).toBeLessThanOrEqual(1);
      });
      expect(prediction.gradcam_image).toMatch(/^data:image\/png;base64,/);
      assessmentId = saved.id;
      expect(saved.sharedWithDoctor).toBe(true);

      await expect(page.getByRole("heading", { name: "Đặt lịch với bác sĩ da liễu" })).toBeVisible({ timeout: 15_000 });
      await expect(page.locator(".skin-v2-score-ring strong")).toHaveText(String(Math.round(prediction.confidence * 100)));
      await expect(page.locator(".skin-v2-prediction-list > li")).toHaveCount(3);
      await expect(page.getByAltText("Ảnh Grad-CAM từ mô hình")).toBeVisible();
      const after = await browserApi<AiAssessment[]>(page, "/api/v1/patients/me/ai-assessments");
      expect(after.ok).toBeTruthy();
      const persisted = after.body.find(item => item.id === assessmentId);
      expect(persisted).toMatchObject({ sharedWithDoctor: true, imageAvailable: true });
      expect(before.body.some(item => item.id === assessmentId)).toBe(false);
      await page.getByRole("button", { name: "Đặt lịch khám ngay", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Đặt lịch khám da liễu" })).toBeVisible();
      await expect(page.locator(".ai-booking-context")
        .getByText("Đính kèm kết quả AI tham khảo", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Triệu chứng hoặc nhu cầu thăm khám", { exact: true }))
        .toHaveValue(/Kết quả kiểm tra da bằng AI \(tham khảo\)/);

      await test.info().attach("ai-assessment-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-AI-001",
          assessmentId,
          predictedLabel: persisted!.predictedLabel,
          modelVersion: persisted!.modelVersion,
          top3Count: prediction.top3.length,
          gradcamImageReturned: prediction.gradcam_image.startsWith("data:image/png;base64,"),
          sharedWithDoctor: persisted!.sharedWithDoctor,
          imageAvailable: persisted!.imageAvailable,
          bookingFlowOpenedWithAssessment: true,
        }, null, 2)),
        contentType: "application/json",
      });
      await test.info().attach("ai-assessment-completed.png", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    } finally {
      if (assessmentId) {
        const deleted = await browserApi<unknown>(page, `/api/v1/patients/me/ai-assessments/${assessmentId}`, { method: "DELETE" });
        if (!deleted.ok) throw new Error(`Không thể xóa assessment E2E ${assessmentId}: HTTP ${deleted.status}.`);
      }
    }
  });
});

test.describe("support assistant handoff", () => {
  const missing = [
    !patient ? credentialsMissingReason([1]) : "",
    !receptionist ? roleCredentialsMissingReason(["RECEPTIONIST"]) : "",
  ].filter(Boolean).join(" ");
  test.skip(Boolean(missing), missing);

  test("E2E-CHAT-001: assistant hands off, receptionist claims and replies", async ({ browser, page, request }) => {
    const runtimeReason = await runtimeUnavailable(request);
    if (runtimeReason) {
      test.skip(true, runtimeReason);
      return;
    }

    const receptionistContext = await browser.newContext({ baseURL, locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const receptionistPage = await receptionistContext.newPage();
    let claimed = false;
    let resolved = false;
    let patientIdentityId = "";

    try {
      await Promise.all([
        loginAs(page, patient!, "PATIENT"),
        loginAs(receptionistPage, receptionist!, "RECEPTIONIST"),
      ]);
      const [patientState, receptionistProfile] = await Promise.all([
        patientSnapshot(page),
        browserApi<{ identityId: string }>(receptionistPage, "/api/v1/auth/me"),
      ]);
      expect(receptionistProfile.ok).toBeTruthy();
      patientIdentityId = patientState.patient.identityId;

      const existingResult = await browserApi<SupportConversation[]>(page, "/api/v1/appointments/support/conversations");
      expect(existingResult.ok).toBeTruthy();
      const existing = existingResult.body.find(item => item.patientIdentityId === patientIdentityId);
      if (existing?.channelStatus === "ASSIGNED"
        && existing.assignedReceptionistIdentityId !== receptionistProfile.body.identityId) {
        test.skip(true, "Hội thoại E2E đang do một lễ tân khác phụ trách; không được phép chiếm quyền xử lý.");
        return;
      }
      if (existing?.channelStatus === "WAITING_RECEPTIONIST" && !existing.assignedReceptionistIdentityId) {
        const claim = await browserApi<unknown>(receptionistPage, `/api/v1/appointments/support/conversations/${patientIdentityId}/claim`, { method: "POST" });
        expect(claim.ok).toBeTruthy();
        claimed = true;
      } else if (existing?.channelStatus === "ASSIGNED") {
        claimed = true;
      }
      if (claimed) {
        const reset = await browserApi<unknown>(receptionistPage, `/api/v1/appointments/support/conversations/${patientIdentityId}/resolve`, { method: "POST" });
        expect(reset.ok).toBeTruthy();
        claimed = false;
      }

      await page.reload();
      await expect(page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" })).toBeVisible();
      // The unread badge contributes its count to the button's accessible name.
      // Keep the selector strict about the launcher label while allowing that count.
      await page.getByRole("button", { name: /^Hỗ trợ(?:\s+\d+\+?)?$/ }).click();
      const patientQuestion = "Tôi muốn hủy lịch và cần lễ tân hỗ trợ E2E-CHAT-001";
      await page.getByLabel("Nội dung cần hỗ trợ", { exact: true }).fill(patientQuestion);
      const assistantResponsePromise = page.waitForResponse(response =>
        isApiResponse(response, "POST", "/api/v1/appointments/support/assistant"),
      );
      await page.getByRole("button", { name: "Gửi câu hỏi cho trợ lý hỗ trợ", exact: true }).click();
      const assistantResponse = await assistantResponsePromise;
      const assistantResult = await responseBody<{ escalated: boolean; conversationStatus: string }>(assistantResponse);
      expect(assistantResponse.status(), JSON.stringify(assistantResult)).toBe(200);
      expect(assistantResult).toMatchObject({ escalated: true, conversationStatus: "WAITING_RECEPTIONIST" });
      await expect(page.getByText("Đã chuyển yêu cầu của bạn đến lễ tân.", { exact: true })).toBeVisible();

      await receptionistPage.reload();
      await expect(receptionistPage.getByRole("navigation", { name: "Điều hướng Lễ tân" })).toBeVisible();
      await receptionistPage.getByRole("button", { name: /^Hộp thư hỗ trợ(?:\s+\d+\+?)?$/ }).click();
      const conversationButton = receptionistPage.locator(".support-conversations button")
        .filter({ hasText: patientState.patient.fullName });
      await expect(conversationButton).toBeVisible({ timeout: 15_000 });
      await conversationButton.click();
      const claimResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/support/conversations/${patientIdentityId}/claim`),
      );
      await receptionistPage.getByRole("button", { name: "Nhận xử lý", exact: true }).click();
      const claimResponse = await claimResponsePromise;
      expect(claimResponse.status()).toBe(200);
      claimed = true;

      // Leave the conversation closed so the incoming reply must raise an unread badge.
      await page.locator(".support-launch").click();
      await expect(page.locator(".support-panel")).toBeHidden();

      const reply = "Lễ tân đã tiếp nhận yêu cầu E2E-CHAT-001.";
      await receptionistPage.getByLabel("Nội dung tin nhắn hỗ trợ", { exact: true }).fill(reply);
      const replyResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", "/api/v1/appointments/support"),
      );
      await receptionistPage.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
      const replyResponse = await replyResponsePromise;
      expect(replyResponse.status()).toBe(201);
      await test.info().attach("support-handoff-receptionist.png", {
        body: await receptionistPage.screenshot({ fullPage: true }),
        contentType: "image/png",
      });

      // No reload: WebSocket delivery must raise the unread badge while chat is closed.
      const patientUnreadBadge = page.locator(".support-launch .support-badge");
      await expect(patientUnreadBadge).toBeVisible({ timeout: 15_000 });
      await expect(patientUnreadBadge).toHaveText(/^\d+\+?$/);
      await page.locator(".support-launch").click();
      await expect(page.getByText(reply, { exact: true }).last()).toBeVisible({ timeout: 15_000 });
      await expect(patientUnreadBadge).toBeHidden({ timeout: 15_000 });
      await test.info().attach("support-handoff-patient.png", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });

      receptionistPage.once("dialog", dialog => void dialog.accept());
      const resolveResponsePromise = receptionistPage.waitForResponse(response =>
        isApiResponse(response, "POST", `/api/v1/appointments/support/conversations/${patientIdentityId}/resolve`),
      );
      await receptionistPage.getByRole("button", { name: "Hoàn tất hỗ trợ cuộc trò chuyện", exact: true }).click();
      const resolveResponse = await resolveResponsePromise;
      expect(resolveResponse.status()).toBe(200);
      claimed = false;
      resolved = true;

      await test.info().attach("support-handoff-result.json", {
        body: Buffer.from(JSON.stringify({
          testCase: "E2E-CHAT-001",
          patientIdentityId,
          assistantEscalated: assistantResult!.escalated,
          receptionistClaimed: true,
          receptionistReplyVisibleToPatient: true,
          finalConversationStatus: "AI_ACTIVE",
        }, null, 2)),
        contentType: "application/json",
      });
    } finally {
      if (claimed && !resolved && patientIdentityId) {
        const cleanup = await browserApi<unknown>(receptionistPage, `/api/v1/appointments/support/conversations/${patientIdentityId}/resolve`, { method: "POST" });
        if (!cleanup.ok) throw new Error(`Không thể resolve hội thoại E2E: HTTP ${cleanup.status}.`);
      }
      await receptionistContext.close();
    }
  });
});
