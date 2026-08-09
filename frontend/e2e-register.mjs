/**
 * Registration UX browser E2E: inline validation, live username check,
 * strength meter, show/hide toggle, and the full sign-up → signed-in
 * journey against the real backend.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const HANDLE = `neko${Date.now().toString(36)}`;
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
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await page.goto(`${BASE}/register`);
  await expect(page, "text=สมัครแล้วได้อะไร", "value proposition shows above the button");

  // Inline email validation
  await page.fill('input[type="email"]', "not-an-email");
  await page.press('input[type="email"]', "Tab");
  await expect(page, "text=รูปแบบอีเมลไม่ถูกต้อง", "invalid email flagged inline on blur");
  await page.fill('input[type="email"]', `${HANDLE}@example.com`);

  // Live username availability — taken handle first (MildBakes exists)
  const usernameInput = page.locator('input[autocomplete="username"]');
  await usernameInput.fill("MildBakes");
  await expect(page, "text=ชื่อนี้ถูกใช้แล้ว", "taken username reported live (case-insensitive)");
  await usernameInput.fill(HANDLE);
  await expect(page, `text=✓ ใช้ชื่อ @${HANDLE} ได้`, "free username confirmed live");

  // Username format rule
  await usernameInput.fill("ab");
  await usernameInput.press("Tab");
  await expect(page, "text=ต้องยาวอย่างน้อย 3 ตัวอักษร", "short username flagged inline");
  await usernameInput.fill(HANDLE);

  // Password strength meter
  const passwordInput = page.locator('input[autocomplete="new-password"]');
  await passwordInput.fill("short");
  await expect(page, "text=รหัสผ่านต้องยาวอย่างน้อย 10 ตัวอักษร", "weak password guidance shows");
  await passwordInput.fill("1234567890123");
  await expect(page, "text=รหัสผ่านต้องไม่เป็นตัวเลขล้วน", "numeric-only password guidance shows");
  await passwordInput.fill("Butter!Croissant9");
  await expect(page, "text=รหัสผ่านแข็งแรงมาก", "strong password confirmed by meter");

  // Show/hide toggle
  await page.click('button[aria-label="แสดงรหัสผ่าน"]');
  await expect(
    page,
    'input[autocomplete="new-password"][type="text"]',
    "show-password toggle reveals the typed password",
  );
  await page.click('button[aria-label="ซ่อนรหัสผ่าน"]');
  await page.screenshot({ path: `${SHOT_DIR}/09-register-filled.png`, fullPage: true });

  // Submit → auto-login → signed-in home
  await page.click('button[type="submit"]');
  await expect(page, "text=ยินดีต้อนรับสู่ KawaiiBake", "success toast appears");
  await expect(page, `text=${HANDLE}`, "header shows the new account — registered AND signed in");
  await page.screenshot({ path: `${SHOT_DIR}/10-register-success.png`, fullPage: false });

  // Friendly server error: duplicate email via a fresh session
  const dup = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await dup.goto(`${BASE}/register`);
  await dup.fill('input[type="email"]', `${HANDLE}@example.com`);
  await dup.locator('input[autocomplete="username"]').fill(`${HANDLE}2x`);
  await dup.locator('input[autocomplete="new-password"]').fill("Butter!Croissant9");
  await dup.click('button[type="submit"]');
  await expect(dup, "text=อีเมลนี้มีบัญชีอยู่แล้ว", "duplicate email answered in friendly Thai");
  await dup.screenshot({ path: `${SHOT_DIR}/11-register-dup-email.png`, fullPage: false });
  await dup.close();

  console.log(`\nRegistration E2E: ${passed}/${passed} passed (handle: ${HANDLE})`);
} finally {
  await browser.close();
}
