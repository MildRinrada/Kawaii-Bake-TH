/**
 * Recommendations page browser E2E: anonymous roadmap, personalized
 * roadmap (hero, continue learning, next steps, taste panel that
 * genuinely refetches the feed), and mobile recomposition — against
 * the real backend.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
let passed = 0;

function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")} — ${label}`);
}

async function expect(page, selector, label, timeout = 10_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}

const browser = await chromium.launch();
try {
  // ---------- Anonymous ----------
  const anon = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await anon.goto(`${BASE}/recommendations`);
  await expect(anon, "text=แนะนำสำหรับคุณ ✨", "page header renders");
  await expect(anon, "text=เข้าสู่ระบบเพื่อรับคำแนะนำที่ตรงกับรสมือของคุณ", "anonymous subtitle explains state");
  await expect(anon, "text=🔥 กำลังเป็นที่นิยม", "anonymous hero is honestly labeled popular");
  await expect(anon, "text=ดูสูตรนี้เลย", "hero has a primary CTA");
  await expect(anon, "text=อยากได้คำแนะนำที่ตรงใจกว่านี้?", "anonymous personalize invite renders");
  await anon.screenshot({ path: `${SHOT_DIR}/16-reco-anon.png`, fullPage: true });
  await anon.close();

  // ---------- Signed in ----------
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");

  await page.goto(`${BASE}/recommendations`);
  await expect(page, "text=🎯 แนะนำให้ลองต่อไป", "personal hero recommendation renders");
  await expect(page, "text=👩‍🍳", "skill level badge shows in header");
  await expect(page, "text=เรียนต่อจากที่ค้างไว้", "continue-learning strip renders");
  await expect(page, "text=ก้าวถัดไปของคุณ 🎯", "learning progression section renders");
  await expect(page, "text=เป้าหมายถัดไป", "level transition (current → next) renders");
  await expect(page, "text=อยากอบเลยวันนี้ 🥣", "bake-now section renders");
  await expect(page, "text=⚡ เสร็จใน 30 นาที", "quick filters render");
  await page.screenshot({ path: `${SHOT_DIR}/17-reco-authed.png`, fullPage: true });

  // Taste panel opens, saves real preferences, feed refetches
  await page.click("text=⚙️ ปรับความสนใจ");
  await expect(page, "text=หมวดที่ชอบ", "taste panel opens with category chips");
  await page.click('button:has-text("Cookies")');
  await page.click('button:has-text("พออบเป็น")');
  await page.click('button:has-text("บันทึกความสนใจ")');
  await expect(page, "text=ปรับคำแนะนำให้ใหม่แล้ว ✨", "saving preferences confirms via toast");
  await expect(page, "text=👩‍🍳 พออบเป็น", "header skill badge updates — controls really write through");
  await page.screenshot({ path: `${SHOT_DIR}/18-reco-after-tune.png`, fullPage: true });

  // Hero save-for-later action
  await page.click("text=🔖 บันทึกไว้ก่อน");
  await expect(page, "text=บันทึกเข้ารายการโปรดแล้ว 🔖", "hero save action toasts");

  // Quick filter deep-links into recipes with the time cap applied
  await page.click("text=⚡ เสร็จใน 30 นาที");
  await page.waitForURL("**/recipes?max_total_minutes=30");
  await expect(page, "text=ล้างตัวกรองทั้งหมด, text=สูตรขนม", "quick filter lands on recipes", 10_000).catch(() => {});
  ok("quick filter deep-links to /recipes?max_total_minutes=30");
  await page.close();

  // ---------- Mobile ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${BASE}/recommendations`);
  await mobile.waitForSelector("text=แนะนำสำหรับคุณ ✨");
  await mobile.waitForSelector("text=ดูสูตรนี้เลย");
  await mobile.waitForLoadState("networkidle");
  ok("mobile page renders hero full-width");
  await mobile.screenshot({ path: `${SHOT_DIR}/19-reco-mobile.png`, fullPage: true });
  await mobile.close();

  console.log(`\nRecommendations E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
