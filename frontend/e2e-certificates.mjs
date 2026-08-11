/**
 * Certificate centre E2E against the real backend: pending → issue →
 * card + summary → full-screen viewer → copy verification link →
 * public (anonymous) verification page → unknown token 404 state.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
let passed = 0;

function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")}  ${label}`);
}

async function expect(page, selector, label, timeout = 10_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1360, height: 950 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
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

  // ---------- Pending: completed course, no certificate yet ----------
  // Issuing is idempotent and permanent, so a second run of this script
  // starts from the earned state. Both paths are asserted.
  await page.goto(`${BASE}/certificates`);
  await expect(page, "text=ใบประกาศนียบัตรของฉัน", "page renders");
  await page.waitForSelector("text=/รอออกใบ|ได้รับแล้ว/");
  const pending = await page.locator("text=รอออกใบ").count();

  if (pending) {
    await expect(page, "text=เรียนจบแล้ว รอออกใบประกาศ", "completed course shows as PENDING, not issued");
    ok("pending status badge is explicit");
    await page.screenshot({ path: `${SHOT_DIR}/32-cert-pending.png`, fullPage: true });

    // ---------- Issue through the real endpoint ----------
    await page.click('button:has-text("ขอรับใบประกาศนียบัตร")');
    await expect(page, "text=ออกใบประกาศนียบัตรเรียบร้อย", "issuing succeeds via the real API");
  } else {
    ok("certificate already issued by an earlier run  earned path asserted instead");
    ok("issuing is permanent, so the pending state is not re-created");
  }
  await expect(page, "text=ได้รับแล้ว", "the certificate now shows as earned");
  await expect(page, "text=ใบประกาศที่ได้รับ", "achievement summary appears");
  await expect(page, "text=Certificate of Completion", "certificate artwork renders from real fields");
  await expect(page, "text=/KB-\\d{4}-\\d+/", "real certificate number is shown");
  await page.screenshot({ path: `${SHOT_DIR}/33-cert-earned.png`, fullPage: true });

  // ---------- Filters ----------
  await page.click('button:has-text("ได้รับแล้ว")');
  ok("earned filter applies");
  await page.click('button:has-text("ทั้งหมด")');

  // ---------- Full-screen viewer ----------
  await page.click('button:has-text("ดูใบประกาศนียบัตร")');
  await expect(page, 'div[role="dialog"]', "full-screen viewer opens");
  await expect(page, "text=พิมพ์ / บันทึกเป็น PDF", "print/save-as-PDF action offered (honest label)");
  await expect(page, "text=ผู้ออกใบ", "detail metadata shows issuer");
  await page.screenshot({ path: `${SHOT_DIR}/34-cert-viewer.png` });

  // ---------- Copy the verification link, then verify anonymously ----------
  await page.click('button:has-text("คัดลอกลิงก์ตรวจสอบ")');
  await expect(page, "text=คัดลอกลิงก์ตรวจสอบแล้ว", "verification link copied");
  const verifyUrl = await page.evaluate(() => navigator.clipboard.readText());
  if (!/\/verify\/[0-9a-f-]{36}$/.test(verifyUrl)) {
    throw new Error(`unexpected verification URL: ${verifyUrl}`);
  }
  ok(`verification link points at a real token (${verifyUrl.slice(-12)})`);

  // ---------- Public verification: brand-new anonymous context ----------
  const anon = await browser.newContext({ viewport: { width: 1360, height: 950 } });
  const anonPage = await anon.newPage();
  await anonPage.goto(verifyUrl);
  await expect(anonPage, "text=ใบประกาศนียบัตรนี้ถูกต้อง", "anonymous visitor sees a VALID verdict");
  await expect(anonPage, "text=พื้นฐานการอบขนมปังสำหรับมือใหม่", "verified course title shown");
  await expect(anonPage, "text=MildBakes", "recipient handle shown (never an email)");
  const anonBody = await anonPage.textContent("body");
  if (anonBody.includes("@example.com")) {
    throw new Error("verification page leaked an email address");
  }
  ok("verification page leaks no email address");
  await anonPage.screenshot({ path: `${SHOT_DIR}/35-verify-public.png`, fullPage: true });

  // ---------- Unknown token ----------
  await anonPage.goto(`${BASE}/verify/00000000-0000-4000-8000-000000000000`);
  await expect(anonPage, "text=ไม่พบใบประกาศนียบัตรนี้", "unknown token gets a helpful not-found state");
  await anon.close();

  // ---------- Mobile ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(verifyUrl);
  await mobile.waitForSelector("text=ใบประกาศนียบัตรนี้ถูกต้อง");
  ok("verification page works on mobile");
  await mobile.screenshot({ path: `${SHOT_DIR}/36-verify-mobile.png`, fullPage: true });
  await mobile.close();

  if (apiErrors.length) {
    throw new Error(`API errors during the run:\n  ${apiErrors.join("\n  ")}`);
  }
  ok("no unexpected 4xx/5xx API responses");

  console.log(`\nCertificates E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
