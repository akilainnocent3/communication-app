import { expect, type Page, type TestInfo } from "@playwright/test";

export const ADMIN = { email: "admin@kilimanjaro-trading.example", password: "Demo-pass-2026!" };

/** Signs in through the real form and applies the project's theme (from the project name). */
export async function login(page: Page, testInfo: TestInfo, user = ADMIN) {
  const theme = testInfo.project.name.includes("dark") ? "dark" : "light";
  // Not addInitScript: that also runs inside the sandboxed email iframe, where Chrome blocks it and logs an error.
  await page.goto("/login");
  await page.evaluate((value) => { try { localStorage.setItem("theme", value); } catch {} }, theme);
  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/gmail\//, { timeout: 20_000 });
}

/**
 * Fails the test on uncaught page errors and React/console errors.
 * Ignored: Chrome's "Blocked script execution in 'about:srcdoc'" for the sandboxed email frame. It shows up only
 * intermittently under Playwright click/back sequences; the frame's HTML is script-free (checked via the API) and an
 * isolated Chromium repro of every operation the app performs on the frame logs nothing. Blocking is the intended
 * behaviour of the sandbox, so the message is not an app error.
 */
export function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !/Failed to load resource|favicon|\[Fast Refresh\]|Download the React DevTools|Blocked script execution in 'about:srcdoc'/.test(message.text())) errors.push(`console: ${message.text()}`);
  });
  return errors;
}

export async function shot(page: Page, testInfo: TestInfo, name: string) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `../docs/screenshots/${testInfo.project.name}-${name}.png`, fullPage: false });
}

export const isMobile = (testInfo: TestInfo) => testInfo.project.name.startsWith("mobile");
