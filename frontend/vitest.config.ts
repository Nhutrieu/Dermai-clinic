import { mergeConfig } from "vite";
import { defineConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(viteConfig, defineConfig({
  test: {
    // Playwright owns browser E2E files; Vitest remains scoped to fast source tests.
    include: ["src/**/*.test.{ts,tsx}"],
  },
}));
