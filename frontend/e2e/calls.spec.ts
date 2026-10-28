import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { isMobile, login, shot, watchErrors } from "./helpers";

/**
 * The Calls platform on simulated phones (`seed_demo` with SMS_ENABLE_SIMULATOR): switch platform → dashboard → a
 * missed call arrives → open it → add an outcome → create a call-back → the phone calls back → done; live board,
 * directory, tools, and access limits.
 */

const ARUSHA = "Arusha front desk";
const VIEWER = { email: "viewer@kilimanjaro-trading.example", password: "Demo-pass-2026!" };
const rows = (page: Page) => page.locator("[data-call-row]");

async function api(page: Page, method: "GET" | "POST" | "PATCH", path: string, data?: unknown) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "cm_csrftoken")?.value ?? "";
  const response = await page.request.fetch(`/api/v1/${path}`, { method, data, headers: { "X-CSRFToken": csrf } });
  expect(response.ok(), `${method} ${path}: ${response.status()}`).toBeTruthy();
  return response.status() === 204 ? null : response.json();
}

async function switchToCalls(page: Page, testInfo: TestInfo) {
  if (isMobile(testInfo)) {
    await page.getByRole("button", { name: "Platform" }).first().click();
    await page.getByRole("option", { name: /Calls/ }).click();
  } else {
    await page.getByRole("tablist", { name: "Platform" }).getByRole("tab", { name: "Calls" }).click();
  }
  await expect(page).toHaveURL(/\/calls\//, { timeout: 30_000 });
}

test("calls journey: dashboard, missed call, note, call-back done by the phone", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const errors = watchErrors(page);
  await login(page, testInfo);
  await switchToCalls(page, testInfo);
  await expect(page.locator("[data-calls-dashboard]")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Busiest hours")).toBeVisible();
  await expect(page.getByText("Waiting for a call back")).toBeVisible();
  if (!isMobile(testInfo)) {
    const nav = page.getByRole("navigation").first();
    await expect(nav.getByRole("link", { name: /Unreturned/ })).toBeVisible();
    await expect(nav.getByRole("link", { name: /Directory/ })).toBeVisible();
    await expect(nav.getByRole("link", { name: /Quick replies/ })).toHaveCount(0);
  }
  await shot(page, testInfo, "calls-dashboard");

  // A missed call arrives on the Arusha phone; it appears at the top of Missed.
  const devices = await api(page, "GET", "calls/devices/");
  const arusha = devices.find((device: { name: string }) => device.name === ARUSHA);
  await api(page, "POST", `calls/devices/${arusha.id}/simulator/`, { action: "missed" });
  await page.goto("/calls/log/missed");
  await expect(rows(page).first()).toBeVisible({ timeout: 30_000 });
  const latest = (await api(page, "GET", `calls/calls/?folder=missed&device=${arusha.id}`)).results[0];
  await page.getByRole("button", { name: "Refresh" }).click();
  const row = page.locator(`[data-call-row="${latest.id}"]`);
  await expect(row).toBeVisible({ timeout: 20_000 });
  await shot(page, testInfo, "calls-missed");
  await row.click(); // by id: the list may re-sort while polling (and holds its order under the pointer)

  const drawer = page.locator(`[data-call-detail="${latest.id}"]`);
  await expect(drawer).toBeVisible({ timeout: 20_000 });
  await expect(drawer.getByText("Not returned yet")).toBeVisible();
  // Outcome and note (encrypted on the server).
  await drawer.getByRole("radiogroup", { name: "Outcome" }).getByRole("radio", { name: "Follow-up" }).click();
  await drawer.getByRole("textbox", { name: "Note" }).fill(`Asked for a quote (${testInfo.project.name})`);
  await drawer.getByRole("button", { name: "Save note" }).click();
  await expect(drawer.getByText(`Asked for a quote (${testInfo.project.name})`)).toBeVisible({ timeout: 20_000 });
  await shot(page, testInfo, "calls-detail");

  // Create a call-back for the Arusha phone.
  await drawer.getByRole("button", { name: "Create call-back" }).click();
  const dialog = page.getByRole("dialog", { name: "Create call-back" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Reason").fill("Quote for 40 bags of cement");
  await dialog.getByRole("button", { name: "Send to phone" }).click();
  await expect(page.getByText("Call-back sent to the phone")).toBeVisible({ timeout: 20_000 });
  await page.keyboard.press("Escape");

  await page.goto("/calls/callbacks/open");
  const task = page.locator("[data-callback]").filter({ hasText: "Quote for 40 bags of cement" }).first();
  await expect(task).toBeVisible({ timeout: 20_000 });
  await shot(page, testInfo, "calls-callbacks");
  // The staff member taps Call on the phone (simulated): the call-back is done and the missed call returned.
  await api(page, "POST", `calls/devices/${arusha.id}/simulator/`, { action: "tick" });
  await expect.poll(async () => (await api(page, "GET", `calls/calls/${latest.id}/?peek=1`)).returned_at, { timeout: 20_000 }).not.toBeNull();
  await page.goto("/calls/callbacks/done");
  await expect(page.locator("[data-callback]").filter({ hasText: "Quote for 40 bags of cement" }).first()).toBeVisible({ timeout: 20_000 });
  expect(errors).toEqual([]);
});

test("calls live board, directory and tools", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const errors = watchErrors(page);
  await login(page, testInfo);
  await page.goto("/calls/live");
  await expect(page.locator(`[data-live-phone="${ARUSHA}"]`)).toBeVisible({ timeout: 30_000 });
  await shot(page, testInfo, "calls-live");

  await page.goto("/calls/customers");
  await expect(page.locator("[data-customers] li").first()).toBeVisible({ timeout: 30_000 });
  await page.locator("[data-customers] li a").first().click();
  await expect(page.locator("[data-customer-timeline]")).toBeVisible({ timeout: 30_000 });
  await shot(page, testInfo, "calls-customer");

  for (const [path, heading] of [["/calls/log/all", "All calls"], ["/calls/log/unreturned", "Unreturned"], ["/calls/devices", "Calls phones"], ["/calls/tools/outcomes", "Outcomes"],
    ["/calls/tools/hours", "Office hours"], ["/calls/tools/missed-sms", "Missed-call SMS and call rules"], ["/calls/tools/tariffs", "Tariffs"], ["/calls/tools/export", "Export calls"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible({ timeout: 30_000 });
    const width = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(width, `${path} scrolls horizontally`).toBeLessThanOrEqual(0);
  }
  await shot(page, testInfo, "calls-tools");
  expect(errors).toEqual([]);
});

test("a user without access does not see the phone's calls", async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  await login(page, testInfo, VIEWER);
  await page.goto("/calls/log/all");
  await expect(page.getByRole("button", { name: "Phone" }).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Phone" }).first().click();
  await expect(page.getByRole("option", { name: /Head Office reception/ })).toBeVisible();
  await expect(page.getByRole("option", { name: new RegExp(ARUSHA) })).toHaveCount(0);
  await page.keyboard.press("Escape");
  const calls = await (await page.request.get("/api/v1/calls/calls/")).json();
  expect(new Set(calls.results.map((call: { device: { name: string } }) => call.device.name))).toEqual(new Set(["Head Office reception"]));
  // Read-only: no "Create call-back" in the detail.
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });
  await rows(page).first().click();
  await expect(page.locator("[data-call-detail]")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Create call-back" })).toHaveCount(0);
  expect(errors).toEqual([]);
});
