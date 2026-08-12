import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "admin@kawaiibake.local");
  await page.fill('input[type="password"]', "Kawaii!Chef2026");
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.goto(`${BASE}/admin/users`);
  await page.waitForSelector("tbody tr");
  await page.click('button:has-text("+ เพิ่มผู้ใช้")');
  await page.waitForSelector("text=รหัสผ่านเริ่มต้น");
  console.log("dialogs:", await page.locator("dialog").count());
  console.log("open dialogs:", await page.locator("dialog[open]").count());
  const info = await page.evaluate(() => {
    const dialog = document.querySelector("dialog[open]");
    const labels = dialog
      ? [...dialog.querySelectorAll("label")].map((l) => ({
          text: l.textContent?.slice(0, 30),
          htmlFor: l.htmlFor,
        }))
      : [];
    return labels;
  });
  console.log(JSON.stringify(info, null, 1));
} finally {
  await browser.close();
}
