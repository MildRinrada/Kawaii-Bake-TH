/** Probe: the home hero banner blends into the gradient (no hard seam). */
import { chromium } from "playwright";

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(process.env.BASE_URL ?? "http://localhost:3000", {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("text=อบขนมให้อร่อย");
  await page.screenshot({ path: "e2e-shots/63-home-hero-blend.png" });
  const featured = page.locator("text=คอร์สเด่นประจำสัปดาห์");
  if (await featured.count()) {
    await featured.scrollIntoViewIfNeeded();
    await page.waitForTimeout(800);
    await page.screenshot({ path: "e2e-shots/65-home-featured-course.png" });
  }
  console.log("shots saved");
} finally {
  await browser.close();
}
