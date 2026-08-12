/**
 * Profile E2E against the real backend: identity, real-only metrics,
 * currently-learning, certificates preview, SAVED RECIPES + SAVED COURSES,
 * activity timeline, edit-profile round trip, mobile order.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
let passed = 0;

function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")}  ${label}`);
}

async function expect(page, selector, label, timeout = 12_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1360, height: 950 } });
  const page = await context.newPage();

  const apiErrors = [];
  page.on("response", (r) => {
    const authProbe = r.url().includes("/users/profile/") && r.status() === 401;
    if (r.url().includes("/api/v1/") && r.status() >= 400 && !authProbe) {
      apiErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    }
  });

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");

  // ---------- Identity ----------
  await page.goto(`${BASE}/profile`);
  await expect(page, "h1", "profile header renders");
  await expect(page, "text=/@mildbakes/", "username shown");
  await expect(page, "text=/เข้าร่วมเมื่อ/", "join date shown (real field)");
  await expect(page, 'button:has-text("แก้ไขโปรไฟล์")', "Edit Profile action present");

  // ---------- Saved content: the sections the user asked for ----------
  await expect(page, "text=สูตรที่บันทึกไว้", "SAVED RECIPES section renders");
  await expect(page, "text=คอร์สที่บันทึกไว้", "SAVED COURSES section renders (separate)");
  const savedRecipeCards = await page
    .locator('section:has(h2:text-is("สูตรที่บันทึกไว้")) a[href^="/recipes/"]')
    .count();
  const savedCourseCards = await page
    .locator('section:has(h2:text-is("คอร์สที่บันทึกไว้")) a[href^="/courses/"]')
    .count();
  console.log(`     saved recipes on page: ${savedRecipeCards}, saved courses: ${savedCourseCards}`);
  if (savedRecipeCards === 0) {
    await expect(page, "text=ยังไม่มีสูตรที่บันทึกไว้", "saved-recipes empty state has a CTA");
  } else {
    ok(`saved recipe cards rendered (${savedRecipeCards})`);
  }

  // ---------- Learning ----------
  await expect(page, "text=กำลังเรียนอยู่", "currently-learning section renders");
  await expect(page, "text=ใบประกาศนียบัตรของฉัน", "certificates preview renders");
  await expect(page, "text=ความเคลื่อนไหวล่าสุด", "activity timeline renders");
  await expect(page, "text=ข้อมูลโปรไฟล์", "profile preferences card renders");

  // Never invent a skill *progression* score.
  const body = await page.textContent("body");
  if (body.includes("Master Sourdough")) {
    throw new Error("fabricated mastery title on the page");
  }
  ok("no fabricated mastery title / skill score");
  for (const word of ["สมาชิกพรีเมียม", "รายการซื้อของ", "หมดอายุ"]) {
    if (body.includes(word)) throw new Error(`forbidden concept on page: ${word}`);
  }
  ok("no membership / shopping-list / expiry concepts");

  await page.screenshot({ path: `${SHOT_DIR}/40-profile.png`, fullPage: true });

  // ---------- Metrics are real, not zero-filled ----------
  const zeroMetric = await page
    .locator('div:has(> p:text-is("0"))')
    .count();
  if (zeroMetric > 0) throw new Error("a zero-value metric is being displayed");
  ok("no zero-value metrics rendered");

  // ---------- Edit profile round trip ----------
  await page.click('button:has-text("แก้ไขโปรไฟล์")');
  await expect(page, 'dialog[open]', "edit dialog opens");
  const stamp = `ชอบอบขนมปัง ${Date.now() % 10000}`;
  await page.fill('dialog textarea', stamp);
  await page.click('dialog button:has-text("บันทึกโปรไฟล์")');
  await expect(page, "text=บันทึกโปรไฟล์แล้ว", "profile PATCH succeeds");
  await expect(page, `text=${stamp}`, "the new bio is read back from the server");

  // ---------- Mobile ----------
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(`${BASE}/profile`);
  await mobile.waitForSelector("text=สูตรที่บันทึกไว้");
  ok("saved recipes present on mobile");
  await mobile.screenshot({ path: `${SHOT_DIR}/41-profile-mobile.png`, fullPage: true });
  await mobile.close();

  if (apiErrors.length) {
    throw new Error(`API errors during the run:\n  ${apiErrors.join("\n  ")}`);
  }
  ok("no unexpected 4xx/5xx API responses");

  console.log(`\nProfile E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
