import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { isMobile, login, shot, watchErrors } from "./helpers";

/**
 * The SMS platform on simulated phones (`seed_demo` with SMS_ENABLE_SIMULATOR): switch platform → sidebar changes →
 * switch phone → open a conversation (name vs number, unread → read) → reply while the phone is offline (Queued) →
 * bring it online (Sent → Delivered, admin label) → dashboard → enroll dialog QR → access limits.
 */

const ARUSHA = "Arusha front desk";
const VIEWER = { email: "viewer@kilimanjaro-trading.example", password: "Demo-pass-2026!" };
const rows = (page: Page) => page.locator("[data-conversation-row]");

async function api(page: Page, method: "GET" | "POST" | "PATCH", path: string, data?: unknown) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "cm_csrftoken")?.value ?? "";
  const response = await page.request.fetch(`/api/v1/${path}`, { method, data, headers: { "X-CSRFToken": csrf } });
  expect(response.ok(), `${method} ${path}: ${response.status()}`).toBeTruthy();
  return response.json();
}

async function switchToSms(page: Page, testInfo: TestInfo) {
  if (isMobile(testInfo)) {
    await page.getByRole("button", { name: "Platform" }).first().click();
    await page.getByRole("option", { name: /SMS/ }).click();
  } else {
    await page.getByRole("tablist", { name: "Platform" }).getByRole("tab", { name: "SMS" }).click();
  }
  await expect(page).toHaveURL(/\/sms\//, { timeout: 30_000 });
}

async function choosePhone(page: Page, name: RegExp | string) {
  await page.getByRole("button", { name: "Phone" }).first().click();
  await page.getByRole("option", { name }).first().click();
}

test("sms journey: switch, open, read, reply offline → online → delivered", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const errors = watchErrors(page);
  await login(page, testInfo);
  // Replies go out immediately (no undo window) so the test does not wait; reload so the session picks it up.
  await api(page, "PATCH", "auth/preferences/", { undo_send_seconds: 0 });
  await page.reload();
  await switchToSms(page, testInfo);
  await expect(rows(page).first()).toBeVisible({ timeout: 30_000 });

  // The sidebar now shows SMS's own navigation (desktop), not Gmail's.
  if (!isMobile(testInfo)) {
    const nav = page.getByRole("navigation").first();
    await expect(nav.getByRole("link", { name: /Awaiting reply/ })).toBeVisible();
    await expect(nav.getByRole("link", { name: /Quick replies/ })).toBeVisible();
    await expect(nav.getByRole("link", { name: /Filters & rules/ })).toHaveCount(0);
  }
  await shot(page, testInfo, "sms-inbox-all");

  // Switch to one phone.
  await choosePhone(page, new RegExp(ARUSHA));
  await expect(page.getByRole("button", { name: "Phone" }).first()).toContainText(ARUSHA);
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });

  const devices = await api(page, "GET", "sms/devices/");
  const arusha = devices.find((device: { name: string }) => device.name === ARUSHA);

  // A saved contact shows its name; an unsaved number shows the formatted number.
  await expect(rows(page).filter({ hasText: "Neema Mushi" }).first()).toBeVisible();
  await expect(rows(page).filter({ hasText: /^\s*.*\+255 \d{3} \d{3} \d{3}/ }).first()).toBeVisible();

  // Receive a fresh unread message, then open it: unread → read.
  await api(page, "POST", `sms/devices/${arusha.id}/simulator/`, { action: "inbound" });
  await page.getByRole("button", { name: "Refresh" }).click();
  const unread = rows(page).filter({ has: page.getByLabel(/^\d+ unread$/) }).first();
  await expect(unread).toBeVisible({ timeout: 20_000 });
  const title = (await unread.getByRole("checkbox").getAttribute("aria-label"))!.replace("Select conversation: ", "");
  const id = await unread.getAttribute("data-conversation-row");
  await page.locator(`[data-conversation-row="${id}"]`).click(); // by id: the list may re-sort while polling
  const chat = page.locator("[data-chat-view]");
  await expect(chat).toBeVisible({ timeout: 20_000 });
  await expect(chat.getByRole("heading", { name: title })).toBeVisible();
  await shot(page, testInfo, "sms-chat");
  if (!isMobile(testInfo)) await expect(page.locator(`[data-conversation-row="${id}"]`).getByLabel(/^\d+ unread$/)).toHaveCount(0, { timeout: 15_000 });

  // The phone goes offline; the reply waits in the queue.
  await api(page, "POST", `sms/devices/${arusha.id}/simulator/`, { action: "offline" });
  const text = `Asante, tumepokea. (${testInfo.project.name} ${Date.now() % 100000})`;
  await chat.getByLabel("Text message").fill(text);
  await chat.getByRole("button", { name: "Send", exact: true }).click();
  const bubble = chat.locator("[data-origin=admin]").filter({ hasText: text });
  await expect(bubble).toBeVisible({ timeout: 20_000 });
  await expect(bubble).toHaveAttribute("data-status", /queued|dispatched/);
  await expect(bubble.getByText(/Waiting for .* to come online/)).toBeVisible();
  await expect(bubble.getByText(/^Admin · /)).toBeVisible();
  await shot(page, testInfo, "sms-queued");

  // Back online: the phone claims, sends and reports delivery.
  await api(page, "POST", `sms/devices/${arusha.id}/simulator/`, { action: "online" });
  await api(page, "POST", `sms/devices/${arusha.id}/simulator/`, { action: "tick" });
  await expect(bubble).toHaveAttribute("data-status", "sent", { timeout: 20_000 });
  await api(page, "POST", `sms/devices/${arusha.id}/simulator/`, { action: "tick" });
  await expect(bubble).toHaveAttribute("data-status", "delivered", { timeout: 20_000 });
  await bubble.getByRole("button", { name: /Message details/ }).click();
  await expect(page.getByRole("list", { name: "Status timeline" })).toContainText("Delivered");
  await shot(page, testInfo, "sms-delivered");
  await page.keyboard.press("Escape");

  await api(page, "PATCH", "auth/preferences/", { undo_send_seconds: 10 });
  expect(errors).toEqual([]);
});

test("sms dashboard, phones and enroll dialog", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const errors = watchErrors(page);
  await login(page, testInfo);
  await page.goto("/sms/dashboard");
  await expect(page.getByRole("heading", { level: 1, name: "SMS dashboard" })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("[data-sms-dashboard]")).toBeVisible();
  await expect(page.getByText("Busiest hours")).toBeVisible();
  await shot(page, testInfo, "sms-dashboard");

  await page.goto("/sms/devices");
  await expect(page.locator(`[data-device-card]`).filter({ hasText: ARUSHA })).toBeVisible({ timeout: 30_000 });
  await shot(page, testInfo, "sms-devices");
  await page.locator("[data-device-card]").filter({ hasText: ARUSHA }).getByRole("link", { name: "Manage" }).click();
  await expect(page.getByRole("heading", { name: "SIM lines" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Who can use this phone" })).toBeVisible();
  await shot(page, testInfo, "sms-device-detail");

  await page.goto("/sms/devices");
  await page.getByRole("button", { name: "Enroll phone" }).first().click();
  const dialog = page.getByRole("dialog", { name: /Enroll a company phone/ });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Phone name").fill(`E2E phone ${testInfo.project.name}`);
  await dialog.getByRole("button", { name: "Create enrollment code" }).click();
  await expect(dialog.getByRole("img", { name: /QR code/ }).locator("svg")).toBeVisible({ timeout: 20_000 });
  await expect(dialog.getByText("Waiting for the phone to enroll…")).toBeVisible();
  // The short code to type on the phone (XXXX-XXXX, Crockford) and the link to tap.
  await expect(dialog.getByLabel("Short code")).toHaveText(/^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$/);
  await expect(dialog.getByLabel(/Link for the phone/)).toHaveValue(/^cmsms:\/\/enroll\?server=/);
  await shot(page, testInfo, "sms-enroll");
  await dialog.getByRole("button", { name: "Revoke code" }).click();

  for (const [path, heading] of [["/sms/outbox", "Outbox"], ["/sms/scheduled", "Scheduled"], ["/sms/contacts", "Contacts"], ["/sms/blocked", "Blocked numbers"], ["/sms/tools/quick-replies", "Quick replies"], ["/sms/tools/rules", "Sensitive-message rules"], ["/sms/tools/settings", "SMS settings"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible({ timeout: 30_000 });
    const width = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(width, `${path} scrolls horizontally`).toBeLessThanOrEqual(0);
  }
  await shot(page, testInfo, "sms-settings");
  expect(errors).toEqual([]);
});

test("a user without access does not see the phone", async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  await login(page, testInfo, VIEWER);
  await page.goto("/sms/inbox");
  await expect(page.getByRole("button", { name: "Phone" }).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Phone" }).first().click();
  await expect(page.getByRole("option", { name: /Head Office reception/ })).toBeVisible();
  await expect(page.getByRole("option", { name: new RegExp(ARUSHA) })).toHaveCount(0);
  await page.keyboard.press("Escape");
  const devices = await page.request.get("/api/v1/sms/devices/");
  expect((await devices.json()).map((device: { name: string }) => device.name)).toEqual(["Head Office reception"]);
  // Read-only: no composer, an explanation instead.
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });
  await rows(page).first().click();
  await expect(page.locator("[data-sms-composer=disabled]")).toContainText("not send");
  expect(errors).toEqual([]);
});
