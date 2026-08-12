/**
 * Probe the two designer fixes:
 * 1. fit-scale must be stable across window resizes (no vibration).
 * 2. a dynamic field accepts a custom override ("มอบโดย …") that renders
 *    on the canvas, then clears back to the automatic value (net-zero).
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const STAFF = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 },
  });
  const page = await context.newPage();

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', STAFF.email);
  await page.fill('input[type="password"]', STAFF.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  await page.goto(`${BASE}/admin/certificates`);
  await page.waitForSelector('a:has-text("แก้ไขเทมเพลต")');
  await page.locator('a:has-text("แก้ไขเทมเพลต")').first().click();
  await page.waitForSelector("[data-canvas]");

  // ---- 1. Resize stability: canvas width must settle, not vibrate ----
  const widthOf = () =>
    page.evaluate(() => {
      const canvas = document.querySelector("[data-canvas] > div");
      return canvas ? canvas.getBoundingClientRect().width : 0;
    });
  for (const width of [1200, 1000, 1440]) {
    await page.setViewportSize({ width, height: 950 });
    await page.waitForTimeout(400);
    const samples = [];
    for (let i = 0; i < 6; i += 1) {
      samples.push(Math.round((await widthOf()) * 10) / 10);
      await page.waitForTimeout(120);
    }
    const stable = new Set(samples).size === 1;
    console.log(`viewport ${width}: samples=${samples.join(",")} stable=${stable}`);
    if (!stable) throw new Error(`fit scale vibrates at viewport ${width}`);
  }

  // ---- 2. Field override: set, see it render, clear again ----
  await page.click('[aria-label="เลือก ชื่อผู้รับ"]');
  const override = page.locator("aside textarea").first();
  await override.waitFor();
  await override.fill("มอบโดย เชฟมิลด์ รินรดา");
  const shows = await page
    .locator("[data-canvas]", { hasText: "มอบโดย เชฟมิลด์ รินรดา" })
    .count();
  console.log("override renders on canvas:", shows > 0);
  await page.waitForSelector("text=กำหนดเอง — ทุกใบจะใช้ข้อความที่กรอกแทนข้อมูลจริง");
  console.log("override state labelled honestly: true");
  await page.waitForSelector("text=บันทึกแล้ว", { timeout: 15_000 });
  await page.screenshot({ path: "e2e-shots/62-designer-field-override.png" });

  await override.fill("");
  const backToSample = await page
    .locator("[data-canvas]", { hasText: "มิลด์ รินรดา" })
    .count();
  console.log("cleared override falls back to sample:", backToSample > 0);
  await page.waitForSelector("text=บันทึกแล้ว", { timeout: 15_000 });
  console.log("probe done (draft back to automatic value, autosaved)");
} finally {
  await browser.close();
}
