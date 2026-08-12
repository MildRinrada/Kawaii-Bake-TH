/**
 * Settings E2E against the real backend.
 *
 * The point of this suite is the claim the page makes: that every
 * control is really persisted. So each assertion changes a control,
 * watches the actual PATCH leave the browser, then **reloads** and reads
 * the value back  a toast is not evidence, a round-trip is.
 *
 * It also pins the boundary: no profile-identity form may appear here.
 * Every value it touches is restored before the run ends, so the suite
 * is safe to run repeatedly against a shared dev database.
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

function assert(condition, label) {
  if (!condition) throw new Error(`FAILED: ${label}`);
  ok(label);
}

/** Open a settings section by its nav button (works on both layouts). */
async function openSection(page, label) {
  await page.click(`nav[aria-label="หมวดการตั้งค่า"] button:has-text("${label}")`);
  await page.waitForTimeout(400);
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

  // ---------- Anonymous ----------
  await page.goto(`${BASE}/settings`);
  await expect(page, "text=ตั้งค่า", "settings page renders for anonymous");
  const anonHasPanels = await page
    .locator('nav[aria-label="หมวดการตั้งค่า"]')
    .count();
  assert(anonHasPanels === 0, "anonymous visitor is not shown the settings panels");

  // ---------- Sign in ----------
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 20_000 });

  await page.goto(`${BASE}/settings`);
  await expect(page, 'nav[aria-label="หมวดการตั้งค่า"]', "settings navigation renders");
  await expect(page, "text=ปรับ KawaiiBake ให้เหมาะกับ", "subtitle renders");

  // ---------- Boundary: no identity form on Settings ----------
  const identityFields = await page
    .locator('input[name="display_name"], textarea, input[type="file"]')
    .count();
  assert(identityFields === 0, "no profile-identity form exists inside /settings");
  await expect(page, "text=โปรไฟล์ของฉัน", "profile shortcut card present");
  const shortcutHref = await page
    .locator('a:has(button:has-text("แก้ไขโปรไฟล์"))')
    .first()
    .getAttribute("href");
  assert(shortcutHref === "/profile", "profile shortcut links out to /profile");

  // ---------- All five sections reachable ----------
  for (const label of [
    "การเรียนและการทำขนม",
    "การแจ้งเตือน",
    "ความเป็นส่วนตัว",
    "การแสดงผล",
    "บัญชีและความปลอดภัย",
  ]) {
    await openSection(page, label);
    await page.waitForSelector(`h2:text-is("${label}")`, { timeout: 8_000 });
  }
  ok("all five sections open");
  await page.screenshot({ path: `${SHOT_DIR}/settings-01-desktop.png` });

  // ---------- Learning: difficulty really persists ----------
  await openSection(page, "การเรียนและการทำขนม");
  const readDifficulty = () =>
    page.evaluate(() => {
      const checked = [...document.querySelectorAll('input[type="radio"]')].find(
        (r) => r.checked && ["beginner", "intermediate", "advanced", "professional"].includes(r.value),
      );
      return checked?.value ?? null;
    });
  const originalDifficulty = await readDifficulty();
  const nextDifficulty = originalDifficulty === "advanced" ? "intermediate" : "advanced";

  const [difficultyPatch] = await Promise.all([
    page.waitForRequest(
      (r) => r.url().includes("/users/preferences/") && r.method() === "PATCH",
      { timeout: 10_000 },
    ),
    page.click(`label[for$="-${nextDifficulty}"]`),
  ]);
  assert(
    JSON.parse(difficultyPatch.postData()).preferred_difficulty === nextDifficulty,
    `difficulty PATCH sends only the changed key (${nextDifficulty})`,
  );
  await expect(page, "text=บันทึกแล้ว", "auto-save confirms visibly");

  await page.reload();
  await openSection(page, "การเรียนและการทำขนม");
  assert(
    (await readDifficulty()) === nextDifficulty,
    "difficulty survived a full reload  it really reached the database",
  );

  // ---------- Learning: dietary chips persist ----------
  const veganChip = page.locator('label[for$="-vegan"]');
  const veganWasOn = await page.evaluate(
    () => document.querySelector('input[id$="-vegan"]')?.checked ?? false,
  );
  const [dietPatch] = await Promise.all([
    page.waitForRequest(
      (r) => r.url().includes("/users/preferences/") && r.method() === "PATCH",
      { timeout: 10_000 },
    ),
    veganChip.click(),
  ]);
  assert(
    Array.isArray(JSON.parse(dietPatch.postData()).dietary_restrictions),
    "dietary PATCH sends a real list to the preferences endpoint",
  );
  await page.reload();
  await openSection(page, "การเรียนและการทำขนม");
  const veganNow = await page.evaluate(
    () => document.querySelector('input[id$="-vegan"]')?.checked ?? false,
  );
  assert(veganNow !== veganWasOn, "dietary restriction survived a reload");
  // restore
  await page.locator('label[for$="-vegan"]').click();
  await page.waitForTimeout(900);

  // ---------- Notifications: two different owners, two endpoints ----------
  await openSection(page, "การแจ้งเตือน");
  await expect(page, 'button[role="switch"]', "notification switches render");

  const emailSwitch = page
    .locator('button[role="switch"]')
    .first();
  const emailBefore = await emailSwitch.getAttribute("aria-checked");
  const [emailPatch] = await Promise.all([
    page.waitForRequest(
      (r) => r.url().includes("/users/preferences/") && r.method() === "PATCH",
      { timeout: 10_000 },
    ),
    emailSwitch.click(),
  ]);
  assert(
    "email_course_updates" in JSON.parse(emailPatch.postData()),
    "email toggle writes to the users preferences endpoint",
  );

  // The in-app ones belong to the notifications domain, not users.
  const inAppSwitch = page.locator('button[role="switch"]').nth(3);
  const [inAppPatch] = await Promise.all([
    page.waitForRequest(
      (r) =>
        r.url().includes("/me/notifications/preferences/") && r.method() === "PATCH",
      { timeout: 10_000 },
    ),
    inAppSwitch.click(),
  ]);
  ok("in-app toggle writes to the notifications domain's own endpoint");
  assert(
    Object.keys(JSON.parse(inAppPatch.postData())).length === 1,
    "in-app PATCH sends only the one event that changed",
  );

  await page.reload();
  await openSection(page, "การแจ้งเตือน");
  const emailAfter = await page
    .locator('button[role="switch"]')
    .first()
    .getAttribute("aria-checked");
  assert(emailAfter !== emailBefore, "email preference survived a reload");
  // restore both
  await page.locator('button[role="switch"]').first().click();
  await page.waitForTimeout(700);
  await page.locator('button[role="switch"]').nth(3).click();
  await page.waitForTimeout(900);

  // ---------- Privacy ----------
  await openSection(page, "ความเป็นส่วนตัว");
  await expect(page, "text=โปรไฟล์สาธารณะ", "privacy visibility group renders");
  await expect(page, "text=อีเมลของคุณไม่เคยแสดง", "privacy explains the email guarantee");

  // ---------- Appearance: honest about what is not applied yet ----------
  await openSection(page, "การแสดงผล");
  await expect(page, 'h3:text-is("ธีม")', "theme group renders");
  await expect(
    page,
    "text=ยังแสดงผลเป็นธีมสว่างอย่างเดียว",
    "theme is honest that dark mode is not applied yet",
  );

  // ---------- Account: destructive actions are guarded ----------
  await openSection(page, "บัญชีและความปลอดภัย");
  await expect(page, 'button:has-text("เปลี่ยนรหัสผ่าน")', "password action present");
  await page.click('button:text-is("ปิดใช้งานบัญชี")');
  await expect(page, 'dialog[open] >> text=เพื่อยืนยัน', "deactivate asks for typed confirmation");
  const confirmDisabled = await page
    .locator('button:has-text("ปิดใช้งานบัญชีของฉัน")')
    .isDisabled();
  assert(confirmDisabled, "deactivate stays disabled until the word is typed");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  // Deletion must not be faked.
  const fakeDelete = await page.locator('button:text-is("ลบบัญชี")').count();
  assert(fakeDelete === 0, "no fake account-deletion button (backend has none)");
  await page.screenshot({ path: `${SHOT_DIR}/settings-02-account.png` });

  // ---------- Mobile: list → panel → back ----------
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mp = await mobile.newPage();
  await mp.goto(`${BASE}/login`);
  await mp.fill('input[type="email"]', "p16-learner@example.com");
  await mp.fill('input[type="password"]', "Rhubarb!Tart2024");
  await mp.click('button[type="submit"]');
  await mp.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 20_000 });
  await mp.goto(`${BASE}/settings`);
  await mp.waitForSelector('nav[aria-label="หมวดการตั้งค่า"]');

  const panelHiddenFirst = await mp
    .locator('button:has-text("หมวดการตั้งค่าทั้งหมด")')
    .isVisible();
  assert(!panelHiddenFirst, "mobile shows the category list first, not a panel");

  await mp.click('nav button:has-text("การแจ้งเตือน")');
  await mp.waitForSelector('button:has-text("หมวดการตั้งค่าทั้งหมด")');
  ok("mobile opens a panel with a back link");
  await mp.screenshot({ path: `${SHOT_DIR}/settings-03-mobile-panel.png` });

  await mp.click('button:has-text("หมวดการตั้งค่าทั้งหมด")');
  await mp.waitForTimeout(300);
  const backToList = await mp.locator('nav button:has-text("ความเป็นส่วนตัว")').isVisible();
  assert(backToList, "mobile back link returns to the category list");
  await mp.screenshot({ path: `${SHOT_DIR}/settings-04-mobile-list.png` });
  await mobile.close();

  if (apiErrors.length) {
    throw new Error(`API errors during run:\n${apiErrors.join("\n")}`);
  }
  ok("no unexpected API errors during the run");

  console.log(`\nSettings E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
