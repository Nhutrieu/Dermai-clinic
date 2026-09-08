import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const recordEvidenceVideo = process.env.E2E_VIDEO?.toLowerCase() === "on";
const artifactRoot = process.env.E2E_ARTIFACT_ROOT?.trim();
const artifactPath = (relativePath: string) => artifactRoot ? join(artifactRoot, relativePath) : relativePath;

export default defineConfig({
  testDir: "./e2e",
  outputDir: artifactPath("test-results/artifacts"),
  preserveOutput: "always",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["line"],
    ["html", { outputFolder: artifactPath("playwright-report"), open: "never" }],
    ["junit", { outputFile: artifactPath("test-results/e2e-junit.xml") }],
    ["json", { outputFile: artifactPath("test-results/e2e-results.json") }],
  ],
  use: {
    baseURL,
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: recordEvidenceVideo ? "on" : "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
