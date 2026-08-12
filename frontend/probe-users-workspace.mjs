/**
 * Probe the users-workspace write paths end-to-end through the UI:
 * create an account, find it, deactivate + reactivate from the row
 * menu, then leave it deactivated (it cannot sign in, and it feeds the
 * "ถูกปิดใช้งาน" stat honestly).
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const HANDLE = "probeworkspace";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 },
  });
  const page = await context.newPage();

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "admin@kawaiibake.local");
  await page.fill('input[type="password"]', "Kawaii!Chef2026");
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  await page.goto(`${BASE}/admin/users`);
  await page.waitForSelector("tbody tr");
  await page.screenshot({ path: "e2e-shots/64-admin-users-workspace.png", fullPage: true });

  // Create (idempotent-ish: a rerun fails on the taken handle, and the
  // form surfaces that as a field error - also worth seeing once).
  await page.click('button:has-text("+ เพิ่มผู้ใช้")');
  await page.waitForSelector("text=รหัสผ่านเริ่มต้น", { timeout: 10_000 });
  const panel = page.locator("dialog[open]");
  await panel.locator('input[type="email"]').fill(`${HANDLE}@example.com`);
  await panel.getByLabel("ชื่อผู้ใช้").fill(HANDLE);
  await panel.getByLabel("รหัสผ่านเริ่มต้น").fill("Torte!Praline88");
  await page.getByRole("button", { name: "สร้างบัญชี" }).click();
  const outcome = await Promise.race([
    page
      .waitForSelector(`text=สร้างบัญชี @${HANDLE} แล้ว`, { timeout: 10_000 })
      .then(() => "created"),
    page
      .waitForSelector("text=ถูกใช้แล้ว, text=มีบัญชีอยู่แล้ว", { timeout: 10_000 })
      .then(() => "duplicate"),
  ]).catch(() => "unknown");
  console.log("create outcome:", outcome);
  if (outcome === "duplicate") await page.keyboard.press("Escape");

  // Find it and toggle activation through the row menu.
  await page.fill('input[type="search"]', HANDLE);
  await page.waitForSelector(`text=@${HANDLE}`, { timeout: 10_000 });
  const row = page.locator("tbody tr", { hasText: `@${HANDLE}` }).first();

  await row.locator('button[aria-haspopup="menu"]').click();
  const canDeactivate = await page
    .locator('button[role="menuitem"]:has-text("ปิดการใช้งาน")')
    .count();
  if (canDeactivate) {
    await page.click('button[role="menuitem"]:has-text("ปิดการใช้งาน")');
    await page.click('dialog[open] button:has-text("ปิดการใช้งาน")');
    await page.waitForSelector(`text=ปิดการใช้งาน @${HANDLE} แล้ว`, { timeout: 10_000 });
    console.log("deactivated: true");
  }

  await page.waitForTimeout(600);
  await row.locator('button[aria-haspopup="menu"]').click();
  await page.click('button[role="menuitem"]:has-text("เปิดใช้งานอีกครั้ง")');
  await page.waitForSelector(`text=เปิดใช้งาน @${HANDLE} แล้ว`, { timeout: 10_000 });
  console.log("reactivated: true");

  // Leave it deactivated so the probe account cannot sign in.
  await page.waitForTimeout(600);
  await page.locator("tbody tr", { hasText: `@${HANDLE}` }).first()
    .locator('button[aria-haspopup="menu"]').click();
  await page.click('button[role="menuitem"]:has-text("ปิดการใช้งาน")');
  await page.click('dialog[open] button:has-text("ปิดการใช้งาน")');
  await page.waitForSelector(`text=ปิดการใช้งาน @${HANDLE} แล้ว`, { timeout: 10_000 });
  console.log("left deactivated: true");
  console.log("probe done");
} finally {
  await browser.close();
}
