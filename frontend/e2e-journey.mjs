/**
 * Phase 16 browser E2E: the full user journey against the real backend,
 * desktop then mobile. Run with both servers up (Django :8000, Next :3000).
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
let passed = 0;

function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")}  ${label}`);
}

async function expect(page, selectorOrText, label, timeout = 10_000) {
  await page.waitForSelector(selectorOrText, { timeout });
  ok(label);
}

const browser = await chromium.launch();
try {
  // ---------- Desktop journey ----------
  const page = await browser.newPage({ viewport: { width: 1360, height: 850 } });

  await page.goto(`${BASE}/`);
  await expect(page, "text=อบขนมให้อร่อย", "home hero renders");
  await expect(page, "text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ", "home shows real recipes from API");
  await page.screenshot({ path: `${SHOT_DIR}/01-home-desktop.png`, fullPage: true });

  // login
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await expect(page, "text=MildBakes", "login succeeds  header shows the user");

  // recipes → detail
  await page.goto(`${BASE}/recipes`);
  await expect(page, "text=สูตรขนม", "recipes page renders");
  await page.click("text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ");
  await expect(page, "text=ส่วนผสม", "recipe detail shows ingredients");
  await expect(page, "text=วิธีทำ", "recipe detail shows steps");
  await expect(page, "text=อร่อยมาก ทำตามแล้วสำเร็จ! 🍪", "reviews render with Thai + emoji");
  await page.screenshot({ path: `${SHOT_DIR}/02-recipe-detail.png`, fullPage: true });

  // favorite
  await page.click("text=บันทึกเข้ารายการโปรด");
  await expect(page, "text=อยู่ในรายการโปรด", "favorite toggles on");
  await page.goto(`${BASE}/favorites`);
  await expect(page, "text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ", "favorites page lists the saved recipe");

  // courses → detail → enroll
  await page.goto(`${BASE}/courses`);
  await expect(page, "text=พื้นฐานการอบขนมปังสำหรับมือใหม่", "courses page lists real courses");
  await page.click("text=พื้นฐานการอบขนมปังสำหรับมือใหม่");
  await expect(page, "text=บทเรียนในคอร์ส", "course detail shows syllabus");
  // Enrolment is permanent and idempotent, so a re-run starts enrolled.
  // Both states are asserted rather than assuming a fresh account.
  if (await page.locator('button:has-text("ลงทะเบียนเรียน")').count()) {
    await page.click('button:has-text("ลงทะเบียนเรียน")');
    await expect(page, "text=การเรียนของฉัน", "enrollment succeeds  progress card appears");
  } else {
    await expect(page, "text=การเรียนของฉัน", "already enrolled  the progress card is shown instead");
  }
  await page.screenshot({ path: `${SHOT_DIR}/03-course-detail.png`, fullPage: true });

  // lesson → complete
  await page.click("text=รู้จักแป้งและยีสต์");
  await expect(page, "text=โปรตีนในแป้งคือหัวใจของกลูเตน", "lesson content renders (enrolled gate open)");
  if (await page.locator("text=ทำเครื่องหมายว่าเรียนจบ").count()) {
    await page.click("text=ทำเครื่องหมายว่าเรียนจบ");
    await expect(page, 'button:has-text("เรียนจบแล้ว ✓")', "lesson completes");
  } else {
    await expect(page, 'button:has-text("เรียนจบแล้ว ✓")', "lesson was already completed by an earlier run");
  }
  await page.screenshot({ path: `${SHOT_DIR}/04-lesson.png`, fullPage: true });

  // back to course → progress reflects
  await page.goto(`${BASE}/courses/bread-basics`);
  // Real counts, not a fixed fraction: other suites move this learner on.
  await expect(page, "text=/เรียนแล้ว \\d+ จาก \\d+ บทเรียน/", "course progress shows real lesson counts");

  // profile
  await page.goto(`${BASE}/profile`);
  await expect(page, "text=@MildBakes", "profile renders");
  await expect(page, "text=ความครบถ้วนของโปรไฟล์", "profile completion meter renders");

  // assistant
  await page.goto(`${BASE}/assistant`);
  await page.click("text=เริ่มบทสนทนาแรก");
  await page.fill("textarea", "สวัสดี ทำไมคุกกี้ถึงแข็ง?");
  await page.click('button:has-text("ส่ง")');
  await expect(page, "text=ผู้ช่วยจำลอง", "assistant replies (mock provider) in Thai");
  await page.screenshot({ path: `${SHOT_DIR}/05-assistant.png`, fullPage: true });

  // notifications
  await page.goto(`${BASE}/notifications`);
  await expect(page, "text=การแจ้งเตือน", "notifications page renders");

  // teacher got an enrollment notification  verify via second session
  const teacher = await browser.newPage({ viewport: { width: 1360, height: 850 } });
  await teacher.goto(`${BASE}/login`);
  await teacher.fill('input[type="email"]', "p16-teacher@example.com");
  await teacher.fill('input[type="password"]', "Rhubarb!Tart2024");
  await teacher.click('button[type="submit"]');
  await teacher.waitForSelector("text=ChefMaprang");
  await teacher.goto(`${BASE}/notifications`);
  await expect(teacher, "text=MildBakes", "teacher sees the enrollment notification");
  await teacher.close();

  // ---------- Mobile pass ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${BASE}/`);
  await expect(mobile, "text=อบขนมให้อร่อย", "mobile home renders");
  await mobile.click('button[aria-label="เปิดเมนู"]');
  await expect(mobile, '#mobile-nav >> text=คอร์สเรียน', "mobile menu opens with nav");
  await mobile.screenshot({ path: `${SHOT_DIR}/06-mobile-home-menu.png`, fullPage: false });
  await mobile.click('#mobile-nav >> text=สูตรขนม');
  await expect(mobile, "text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ", "mobile recipes grid renders");
  await mobile.screenshot({ path: `${SHOT_DIR}/07-mobile-recipes.png`, fullPage: true });
  await mobile.close();

  console.log(`\nPhase 16 browser E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
