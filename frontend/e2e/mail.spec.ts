import { expect, test, type Page } from "@playwright/test";
import { isMobile, login, shot, watchErrors } from "./helpers";

/**
 * The core Gmail journey on the fake provider: switch mailbox → open thread → reply → archive with undo →
 * search → label → delete forever. Runs at desktop (light) and mobile (dark).
 */

const rows = (page: Page) => page.getByRole("row");

async function chooseMailbox(page: Page, name: RegExp) {
  await page.getByRole("button", { name: "Mailbox" }).first().click();
  await page.getByRole("option", { name }).click();
}

async function openFirstThread(page: Page) {
  const row = rows(page).first();
  await expect(row).toBeVisible({ timeout: 20_000 });
  const subject = (await row.getByRole("checkbox").getAttribute("aria-label"))!.replace("Select conversation: ", "");
  await row.click();
  await expect(page.locator("[data-thread-view]")).toBeVisible({ timeout: 20_000 });
  return subject;
}

test("mail journey: switch, open, reply, archive + undo, search, label, delete forever", async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  await login(page, testInfo);
  await page.goto("/gmail/inbox");
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });
  await shot(page, testInfo, "inbox-all");

  // Switch to one office mailbox.
  const scopedList = page.waitForResponse((response) => /\/mail\/threads\/\?mailbox=\d+/.test(response.url()) && response.ok());
  await chooseMailbox(page, /Finance/i);
  await expect(page.getByRole("button", { name: "Mailbox" }).first()).toContainText("Finance");
  await scopedList;
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });

  // Open a thread and reply.
  const subject = await openFirstThread(page);
  await shot(page, testInfo, "thread");
  await page.getByRole("button", { name: "Reply", exact: true }).last().click();
  const editor = page.locator(".ProseMirror").last();
  await editor.click();
  await editor.fill("Thanks, received. We will follow up today.");
  await page.getByRole("button", { name: "Send (Ctrl+Enter)" }).last().click();
  await expect(page.getByText("Message sent.")).toBeVisible({ timeout: 40_000 }); // after the undo-send window

  // Archive, then undo from the toast.
  await page.getByRole("button", { name: "Archive (e)" }).first().click();
  await page.locator("[data-sonner-toast]").filter({ hasText: "Conversation archived." }).getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Action undone.")).toBeVisible();

  // Search by the subject's first words.
  const words = subject.split(/\s+/).slice(0, 2).join(" ");
  if (isMobile(testInfo)) await page.goto(`/gmail/search?q=${encodeURIComponent(`subject:"${words}"`)}`);
  else {
    await page.getByLabel("Search mail").fill(`subject:"${words}"`);
    await page.getByLabel("Search mail").press("Enter");
  }
  await expect(page).toHaveURL(/\/gmail\/search/, { timeout: 30_000 }); // first visit compiles the route in dev
  await expect(rows(page).filter({ hasText: words }).first()).toBeVisible({ timeout: 20_000 });
  await shot(page, testInfo, "search");

  // Label the thread from the thread view.
  await rows(page).filter({ hasText: words }).first().click();
  await expect(page.locator("[data-thread-view]")).toBeVisible();
  await page.getByRole("button", { name: "Labels (l)" }).first().click();
  const picker = page.getByRole("dialog", { name: "Label as" });
  const box = picker.getByRole("checkbox", { checked: false }).first(); // the other project may have labelled this thread already
  const labelName = (await box.evaluate((el) => (el.closest("label")?.textContent ?? "").trim()));
  await box.check();
  await picker.getByRole("button", { name: "Apply" }).click();
  await expect(page.locator("[data-thread-view]").getByRole("button", { name: `Remove label ${labelName}` })).toBeVisible();

  // Delete: to Trash, then forever (with confirmation).
  await page.getByRole("button", { name: "Delete (#)" }).first().click();
  await page.goto("/gmail/trash");
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });
  await rows(page).first().getByRole("checkbox").check();
  await page.getByRole("toolbar", { name: "Bulk actions" }).getByRole("button", { name: "Delete forever" }).click();
  const confirm = page.getByRole("alertdialog").or(page.getByRole("dialog", { name: /Delete forever/ }));
  await expect(confirm.first()).toBeVisible();
  await shot(page, testInfo, "delete-forever-confirm");
  await confirm.first().getByRole("button", { name: /Delete forever/ }).click();
  await expect(page.getByText(/deleted forever/i).first()).toBeVisible();

  expect(errors).toEqual([]);
});

test("keyboard shortcuts and cheat sheet", async ({ page }, testInfo) => {
  test.skip(isMobile(testInfo), "Keyboard shortcuts are a desktop feature.");
  const errors = watchErrors(page);
  await login(page, testInfo);
  await page.goto("/gmail/inbox");
  await expect(rows(page).first()).toBeVisible({ timeout: 20_000 });
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("j");
  await page.keyboard.press("o");
  await expect(page.locator("[data-thread-view]")).toBeVisible();
  await page.keyboard.press("u");
  await page.keyboard.press("Shift+?");
  await expect(page.getByRole("dialog", { name: /Keyboard shortcuts/i })).toBeVisible();
  await shot(page, testInfo, "shortcuts");
  await page.keyboard.press("Escape");
  await page.keyboard.press("c");
  await expect(page.getByRole("dialog", { name: /New message/i }).or(page.getByLabel("Subject")).first()).toBeVisible();
  await shot(page, testInfo, "compose");
  expect(errors).toEqual([]);
});
