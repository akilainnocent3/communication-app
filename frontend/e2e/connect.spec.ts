import { expect, test, type Page } from "@playwright/test";
import { login, shot, watchErrors } from "./helpers";

/** The Google button, or the friendly notice shown when this server has no Google OAuth client configured. */
const googleAction = (page: Page) =>
  page.getByRole("button", { name: /Connect with Google/ }).or(page.getByText("Google sign-in is not set up on this server yet")).first();

/**
 * "Send connect link" from the admin, then the public /connect/[token] page as the office sees it (no login):
 * ready state, wrong-account error, success, and an invalid link. The Google consent screen itself needs real
 * credentials, so the callback outcomes are driven by the `?result=` codes the backend redirects with.
 */
test("connect link: admin dialog and public page states", async ({ page, browser }, testInfo) => {
  const errors = watchErrors(page);
  await login(page, testInfo);
  // Add mailbox wizard: ① office & email → ② detected method → ③ send connect link.
  const email = `e2e.${testInfo.project.name}.${Date.now()}@gmail.com`;
  await page.goto("/gmail/mailboxes/new");
  await page.getByLabel("Office", { exact: true }).selectOption({ index: 0 });
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/Google/).first()).toBeVisible();
  await shot(page, testInfo, "mailbox-new-detected");
  await page.getByRole("button", { name: "Add mailbox" }).click();
  await page.getByRole("button", { name: /Send connect link/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("img", { name: "QR code for the connect link" })).toBeVisible({ timeout: 20_000 });
  await expect(dialog.getByRole("link", { name: /Share on WhatsApp/ })).toHaveAttribute("href", /^https:\/\/wa\.me\/\?text=/);
  await expect(dialog.getByText(/Waiting for the office to connect/)).toBeVisible();
  await shot(page, testInfo, "connect-link-dialog");
  const url = new URL(await dialog.locator("#connect-url").inputValue());
  expect(errors).toEqual([]);

  // The office opens the link on their own phone: a fresh browser context with no session.
  const theme = testInfo.project.name.includes("dark") ? "dark" : "light";
  const visitor = await browser.newContext({ ...testInfo.project.use, baseURL: undefined, colorScheme: theme });
  const office = await visitor.newPage();
  const officeErrors = watchErrors(office);
  const base = testInfo.project.use.baseURL!;
  await office.goto(`${base}${url.pathname}`);
  await expect(office.getByRole("heading", { level: 1 })).toContainText(`wants to connect the mailbox ${email}`);
  await expect(office.getByText(/All access is logged/)).toBeVisible();
  await expect(googleAction(office)).toBeVisible();
  await shot(office, testInfo, "connect-page");

  await office.goto(`${base}${url.pathname}?result=wrong_account&signed_in_as=someone.else%40gmail.com`);
  const problem = office.getByRole("alert").filter({ hasText: "That was a different account" });
  await expect(problem).toContainText(`You signed in as someone.else@gmail.com, but this link is for ${email}`);
  await expect(googleAction(office)).toBeVisible();
  await shot(office, testInfo, "connect-wrong-account");

  await office.goto(`${base}${url.pathname}?result=connected`);
  await expect(office.getByText("Mailbox connected")).toBeVisible();
  await expect(office.getByText(/You can close this page/)).toBeVisible();
  await shot(office, testInfo, "connect-success");

  await office.goto(`${base}/connect/not-a-real-token-${Date.now()}`);
  await expect(office.getByText("This link is not valid")).toBeVisible();
  expect(officeErrors.filter((e) => !/404|Not Found/.test(e))).toEqual([]);
  await visitor.close();

  // Leave the dev database as it was: remove the mailbox this run created.
  const removed = await page.evaluate(async (address) => {
    const csrf = document.cookie.match(/(?:^|; )cm_csrftoken=([^;]+)/)?.[1] ?? "";
    const list = await (await fetch("/api/v1/mail/mailboxes/")).json();
    const rows: { id: number; email: string }[] = Array.isArray(list) ? list : list.results;
    const mailbox = rows.find((row) => row.email === address);
    if (!mailbox) return 0;
    return (await fetch(`/api/v1/mail/mailboxes/${mailbox.id}/`, { method: "DELETE", headers: { "X-CSRFToken": decodeURIComponent(csrf) } })).status;
  }, email);
  expect(removed).toBe(204);
});
