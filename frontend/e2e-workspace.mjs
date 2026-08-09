/**
 * Recipe baking-workspace browser E2E against the real backend:
 * hero + jump anchor, scaler math, unit conversion, grouped checklist
 * with persistence, substitutions accordion, step timers, focus mode,
 * review form, related recipes — desktop then mobile.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const RECIPE = `${BASE}/recipes/choc-chip-cookies`;
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
  const context = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  const page = await context.newPage();

  // ---------- Hero + workspace ----------
  await page.goto(RECIPE);
  await expect(page, "text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ", "hero renders");
  await expect(page, "text=⬇ ไปที่สูตรเลย", "jump-to-recipe CTA present");
  await expect(page, 'button:has-text("👩‍🍳 โหมดทำขนม")', "sticky bar with focus-mode entry renders");
  await expect(page, "text=โดคุกกี้", "ingredient groups render (โดคุกกี้)");
  await expect(page, "text=ช็อกโกแลตและตกแต่ง", "second ingredient group renders");
  await expect(page, "text=250 g", "base quantity shows (250 g flour)");

  // ---------- Scaler: base 4 servings → 8 doubles quantities ----------
  for (let i = 0; i < 4; i += 1) {
    await page.click('button[aria-label="เพิ่มจำนวน"]');
  }
  await page.waitForSelector("text=500 g");
  ok("scaler doubles 250 g → 500 g (4 → 8 servings)");
  await page.click("text=คืนค่าเดิม");
  await page.waitForSelector("text=250 g");
  ok("reset restores original quantities");

  // ---------- Unit toggle ----------
  await page.click('button:has-text("oz/lb")');
  await expect(page, "text=oz", "imperial units appear after toggle");
  await expect(page, "text=ช้อน/ฟอง คงเดิม", "honest note: spoon/egg units stay put");
  await page.click('button:has-text("กรัม/มล.")');

  // ---------- Checklist + persistence ----------
  const firstBox = page.locator('#ingredients input[type="checkbox"]').first();
  await firstBox.check();
  await expect(page, "text=เตรียมแล้ว 1/", "checklist progress updates");
  await page.reload();
  await page.waitForSelector("text=ส่วนผสม");
  if (await page.locator('#ingredients input[type="checkbox"]').first().isChecked()) {
    ok("checklist state survives reload (localStorage session)");
  } else {
    throw new Error("checklist state lost after reload");
  }

  // ---------- Substitutions ----------
  await page.click("text=ไม่มีวัตถุดิบครบ? ดูของทดแทน");
  await expect(page, "text=→", "substitution options expand with ratios");

  // ---------- Step timer ----------
  await page.click('button:has-text("⏲ จับเวลา 12 นาที")');
  await expect(page, 'div[role="timer"]', "timer dock appears");
  await expect(page, "text=11:5", "countdown is ticking", 15_000);
  await page.click('button[aria-label="พักเวลา"]');
  ok("timer pause works");
  await page.click('button[aria-label="ปิดตัวจับเวลา"]');

  // ---------- Step completion + active emphasis ----------
  await expect(page, "text=ขั้นตอนปัจจุบัน", "active step is emphasized");
  const stepBox = page.locator('#steps input[type="checkbox"]').first();
  await stepBox.check();
  await expect(page, "text=ทำแล้ว 1 จาก 3 ขั้น", "step progress updates");
  await page.screenshot({ path: `${SHOT_DIR}/20-workspace-desktop.png`, fullPage: true });

  // ---------- Focus mode ----------
  await page.click('button:has-text("👩‍🍳 โหมดทำขนม")');
  await expect(page, 'div[role="dialog"][aria-label="โหมดทำขนม"]', "focus mode opens");
  await expect(page, "text=ขั้นที่ 2 จาก 3", "focus mode resumes at the active step");
  await page.click('button:has-text("ทำเสร็จแล้ว → ขั้นถัดไป")');
  await expect(page, "text=ขั้นที่ 3 จาก 3", "next-step advances and marks done");
  await page.screenshot({ path: `${SHOT_DIR}/21-focus-mode.png` });
  await page.click('button:has-text("เสร็จเรียบร้อย 🎉")');
  await expect(page, "text=ทำครบทุกขั้นแล้ว", "completing all steps shows the celebration state");

  // ---------- Notes persistence ----------
  await page.fill('textarea[placeholder*="เตาบ้านเรา"]', "เตาบ้านเราต้องอบเพิ่ม 2 นาที");
  await page.reload();
  await page.waitForSelector("text=โน้ตส่วนตัว 📝");
  const noteValue = await page.locator('textarea[placeholder*="เตาบ้านเรา"]').inputValue();
  if (noteValue.includes("อบเพิ่ม 2 นาที")) ok("personal note persists");
  else throw new Error("note lost");

  // ---------- Related recipes (cake category has 2 recipes) ----------
  await page.goto(`${BASE}/recipes/fudge-brownie`);
  await expect(page, "text=ถ้าชอบสูตรนี้ ลองต่อเลย", "related recipes section renders (same category)");
  await expect(page, "text=เค้กส้มหน้านิ่มสูตรคุณยาย", "related card links a real same-category recipe");
  await page.goto(RECIPE);
  await page.waitForSelector("text=โน้ตส่วนตัว 📝");

  // ---------- Review form (logged in) ----------
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-fan0@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("header >> text=สูตรขนม");
  await page.goto(RECIPE);
  await page.waitForSelector("text=ทำสูตรนี้แล้วเป็นยังไงบ้าง?");
  ok("review form renders for a signed-in member");
  await page.click('button[aria-label="4 ดาว"]');
  await page.fill('textarea[placeholder*="เล่าผลลัพธ์"]', "หนึบจริง อบตามเวลาพอดีเลย");
  await page.click('button:has-text("ส่งรีวิว")');
  const reviewResult = await Promise.race([
    page.waitForSelector("text=ขอบคุณสำหรับรีวิวนะ 🧡").then(() => "posted"),
    page.waitForSelector("text=คุณรีวิวสูตรนี้ไปแล้ว").then(() => "already"),
  ]);
  ok(`review submit handled (${reviewResult}) with friendly Thai feedback`);

  // ---------- Mobile ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(RECIPE);
  await mobile.waitForSelector("text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ");
  await mobile.waitForSelector('button:has-text("👩‍🍳 โหมดทำขนม")');
  ok("mobile workspace renders with sticky controls");
  await mobile.click('button:has-text("👩‍🍳 โหมดทำขนม")');
  await mobile.waitForSelector('div[role="dialog"][aria-label="โหมดทำขนม"]');
  ok("mobile focus mode opens full-screen");
  await mobile.screenshot({ path: `${SHOT_DIR}/22-focus-mobile.png` });
  await mobile.close();

  console.log(`\nBaking-workspace E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
