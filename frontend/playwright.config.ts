import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL?.trim() || "http://localhost:3000";
const recordEvidenceVideo = process.env.E2E_VIDEO?.toLowerCase() === "on";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "test-results/artifacts",
  preserveOutput: "always",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["line"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["junit", { outputFile: "test-results/e2e-junit.xml" }],
    ["json", { outputFile: "test-results/e2e-results.json" }],
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
