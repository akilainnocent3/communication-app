import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the fake mail provider (`python manage.py seed_demo`). Start Django on :8000 and
 * Next.js on :3000 first, or set E2E_BASE_URL. Screenshots go to docs/screenshots/.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop-light", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, colorScheme: "light" } },
    { name: "desktop-dark", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, colorScheme: "dark" } },
    { name: "mobile-light", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 }, colorScheme: "light" } },
    { name: "mobile-dark", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 }, colorScheme: "dark" } },
  ],
});
