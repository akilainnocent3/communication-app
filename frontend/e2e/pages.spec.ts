import { expect, test } from "@playwright/test";
import { login, shot, watchErrors } from "./helpers";

/** Every page renders its heading without runtime errors, in both projects (desktop light, mobile dark). */
const PAGES: [string, string | RegExp, string][] = [
  ["/gmail/dashboard", "Mail dashboard", "dashboard"],
  ["/gmail/mailboxes", "Connected mailboxes", "mailboxes"],
  ["/gmail/mailboxes/new", "Add a mailbox", "mailbox-new"],
  ["/gmail/labels", /Labels|Folders/, "labels"],
  ["/gmail/scheduled", "Scheduled", "scheduled"],
  ["/gmail/drafts", "Drafts", "drafts"],
  ["/gmail/tools/templates", "Templates", "templates"],
  ["/gmail/tools/filters", "Filters & rules", "filters"],
  ["/gmail/tools/signatures", "Signatures", "signatures"],
  ["/gmail/tools/vacation", "Vacation responder", "vacation"],
  ["/settings/preferences", "Preferences", "preferences"],
  ["/settings/users", "Users & roles", "users"],
  ["/settings/offices", "Offices", "offices"],
  ["/settings/platforms", "Platforms", "platforms"],
  ["/settings/integrations", "Integrations", "integrations"],
  ["/settings/audit", "Audit log", "audit"],
];

test("every page renders", async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  await login(page, testInfo);
  for (const [path, heading, name] of PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading }).first()).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: /error|failed|couldn't/i })).toHaveCount(0);
    await shot(page, testInfo, name);
    const width = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(width, `${path} scrolls horizontally`).toBeLessThanOrEqual(0);
  }
  expect(errors).toEqual([]);
});

test("mailbox detail page", async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  await login(page, testInfo);
  await page.goto("/gmail/mailboxes");
  await page.getByRole("link", { name: "Manage", exact: true }).first().click();
  await expect(page).toHaveURL(/\/gmail\/mailboxes\/\d+/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Connection" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Who can use this mailbox" })).toBeVisible();
  await shot(page, testInfo, "mailbox-detail");
  expect(errors).toEqual([]);
});
