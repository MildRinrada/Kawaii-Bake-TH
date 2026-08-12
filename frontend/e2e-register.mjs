/**
 * Registration UX browser E2E against the real backend.
 *
 * The form now asks for three things - email, handle, password - plus
 * consent. The legal name moved to certificate issuance, so this file
 * asserts its *absence* as deliberately as it used to assert its
 * presence. Also covered: the rules being readable before they can be
 * broken, the gated submit naming what it waits for, the split layout,
 * and the sign-up → check-your-email journey (registration still does
 * NOT sign the account in).
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const HANDLE = `neko${Date.now().toString(36)}`;
const PASSWORD = "Butter!Croissant9";
// Sign-in shares this page behind the slider, so "the form" is ambiguous.
const SIGNUP = 'form[aria-label="สมัครสมาชิก"]';
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
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await page.goto(`${BASE}/register`);

  /* ---- 11. Split layout, 6. the pitch before the fields ---- */
  const layout = await page.evaluate((SIGNUP) => {
    const aside = document.querySelector("main aside");
    const form = document.querySelector(SIGNUP);
    if (!aside || !form) return null;
    const a = aside.getBoundingClientRect();
    const f = form.getBoundingClientRect();
    return {
      sideBySide: a.right <= f.left + 1,
      benefits: aside.querySelectorAll("li").length,
      asideTop: Math.round(a.top),
      formTop: Math.round(f.top),
    };
  }, SIGNUP);
  if (!layout?.sideBySide) throw new Error("register is not a split layout");
  if (layout.benefits !== 3) {
    throw new Error(`expected 3 benefit bullets, got ${layout.benefits}`);
  }
  ok("desktop: pitch column beside the form, three benefit bullets");

  /* ---- 10. A way back that is a link, not decoration ---- */
  const home = await page.evaluate(() => {
    const links = [...document.querySelectorAll("header a")];
    return links.map((a) => a.getAttribute("href"));
  });
  if (!home.includes("/")) throw new Error("no link home in the auth header");
  ok(`auth header links home (${home.length} link(s))`);

  /* ---- 1. The legal name is not asked for here any more ---- */
  const nameFields = await page.evaluate(
    () =>
      document.querySelectorAll(
        'input[autocomplete="given-name"], input[autocomplete="family-name"]',
      ).length,
  );
  if (nameFields > 0) throw new Error("sign-up is asking for a legal name again");
  const fieldCount = await page.evaluate(
    (SIGNUP) => document.querySelectorAll(`${SIGNUP} input`).length,
    SIGNUP,
  );
  ok(`no legal-name fields; the form is ${fieldCount} inputs incl. consent`);

  /* ---- 3. The password rules are readable before typing ---- */
  const rulesUpFront = await page.evaluate(
    (SIGNUP) =>
      [...document.querySelectorAll(`${SIGNUP} li`)].map((li) =>
        li.textContent.trim(),
      ),
    SIGNUP,
  );
  for (const rule of ["ยาวอย่างน้อย 8 ตัวอักษร", "ไม่ใช่ตัวเลขล้วน"]) {
    if (!rulesUpFront.some((text) => text.includes(rule))) {
      throw new Error(`password rule not shown up front: ${rule}`);
    }
  }
  ok(`password rules visible on an untouched form (${rulesUpFront.length})`);

  /* ---- 8. The submit is gated, and says what it is waiting for ---- */
  const gated = await page.evaluate((SIGNUP) => {
    const button = document.querySelector(`${SIGNUP} button[type="submit"]`);
    return { disabled: button.disabled, hint: button.parentElement.innerText };
  }, SIGNUP);
  if (!gated.disabled) throw new Error("submit is live on an empty form");
  // On an *empty* form the list would be every field, which says nothing;
  // it appears further down, once it can point at something. (It is the
  // same check from the other side: a list here would be the bug.)
  if (/เหลืออีก/.test(gated.hint)) {
    throw new Error("the empty form lists every field as 'missing'");
  }
  ok("submit disabled on an empty form, with no list-of-everything");

  /* ---- 4. Inline validation ---- */
  await page.fill(`${SIGNUP} input[type="email"]`, "not-an-email");
  await page.press(`${SIGNUP} input[type="email"]`, "Tab");
  await expect(page, "text=รูปแบบอีเมลไม่ถูกต้อง", "invalid email flagged inline on blur");
  await page.fill(`${SIGNUP} input[type="email"]`, `${HANDLE}@example.com`);

  const usernameInput = page.locator(`${SIGNUP} input[autocomplete="username"]`);
  await usernameInput.fill("MildBakes");
  await expect(page, "text=ชื่อนี้ถูกใช้แล้ว", "taken username reported live (case-insensitive)");
  await usernameInput.fill(HANDLE);
  await expect(page, `text=ใช้ชื่อ @${HANDLE} ได้`, "free username confirmed live");

  await usernameInput.fill("ab");
  await usernameInput.press("Tab");
  await expect(page, "text=ต้องยาวอย่างน้อย 3 ตัวอักษร", "short username flagged inline");
  await usernameInput.fill(HANDLE);

  /* ---- 3. The ticks track what was typed ---- */
  const passwordInput = page.locator(`${SIGNUP} input[autocomplete="new-password"]`);
  await passwordInput.fill("1234567890123");
  await page.waitForTimeout(400);
  const numericVerdict = await page.evaluate((SIGNUP) => {
    const item = [...document.querySelectorAll(`${SIGNUP} li`)].find((li) =>
      li.textContent.includes("ไม่ใช่ตัวเลขล้วน"),
    );
    return getComputedStyle(item).color;
  }, SIGNUP);
  if (numericVerdict === "rgb(46, 125, 84)") {
    throw new Error("an all-numeric password is ticked as acceptable");
  }
  ok("all-numeric password leaves its rule unticked");

  // A password echoing the handle is what Django's similarity validator
  // refuses; the form says so before the server has to.
  await passwordInput.fill(`${HANDLE}${HANDLE}`);
  await page.waitForTimeout(400);
  const identityVerdict = await page.evaluate((SIGNUP) => {
    const item = [...document.querySelectorAll(`${SIGNUP} li`)].find((li) =>
      li.textContent.includes("ไม่ซ้ำกับชื่อผู้ใช้"),
    );
    return getComputedStyle(item).color;
  }, SIGNUP);
  if (identityVerdict === "rgb(46, 125, 84)") {
    throw new Error("a password containing the handle is ticked as acceptable");
  }
  ok("password that echoes the handle leaves its rule unticked");

  await passwordInput.fill(PASSWORD);
  await expect(page, "text=รหัสผ่านแข็งแรงมาก", "strong password confirmed by meter");
  await page.waitForTimeout(400);
  const ticked = await page.evaluate(
    (SIGNUP) =>
      [...document.querySelectorAll(`${SIGNUP} li`)].filter(
        (li) => getComputedStyle(li).color === "rgb(46, 125, 84)",
      ).length,
    SIGNUP,
  );
  if (ticked !== 3) throw new Error(`expected 3 green rules, got ${ticked}`);
  ok("every rule ticks green for an acceptable password");

  /* ---- 12. The eye is a real target ---- */
  const eye = await page.evaluate((SIGNUP) => {
    const button = document.querySelector(
      `${SIGNUP} button[aria-label="แสดงรหัสผ่าน"]`,
    );
    const box = button.getBoundingClientRect();
    return { w: Math.round(box.width), h: Math.round(box.height) };
  }, SIGNUP);
  if (eye.w < 40 || eye.h < 40) {
    throw new Error(`password toggle is ${eye.w}x${eye.h}, under 40x40`);
  }
  ok(`show/hide target is ${eye.w}x${eye.h}`);
  await page.click(`${SIGNUP} button[aria-label="แสดงรหัสผ่าน"]`);
  await expect(
    page,
    'input[autocomplete="new-password"][type="text"]',
    "show-password toggle reveals the typed password",
  );
  await page.click(`${SIGNUP} button[aria-label="ซ่อนรหัสผ่าน"]`);

  /* ---- 8. Consent is the last thing holding the button ---- */
  const beforeConsent = await page.evaluate((SIGNUP) => {
    const button = document.querySelector(`${SIGNUP} button[type="submit"]`);
    return { disabled: button.disabled, hint: button.parentElement.innerText };
  }, SIGNUP);
  if (!beforeConsent.disabled || !/ข้อตกลง/.test(beforeConsent.hint)) {
    throw new Error("consent does not gate the submit");
  }
  ok("with the fields filled, only consent still gates the button");

  const termsHref = await page
    .locator('a[href*="/legal?doc=terms"]')
    .getAttribute("href");
  if (!termsHref) throw new Error("terms link missing from consent line");
  ok("consent line links to /legal");
  await page.check(`${SIGNUP} input[type="checkbox"]`);
  const live = await page.evaluate(
    (SIGNUP) =>
      !document.querySelector(`${SIGNUP} button[type="submit"]`).disabled,
    SIGNUP,
  );
  if (!live) throw new Error("submit stayed disabled on a complete form");
  ok("submit unlocks once the form is complete");
  await page.screenshot({ path: `${SHOT_DIR}/09-register-filled.png`, fullPage: true });

  /* ---- 6. On a phone the pitch is above the form, not beside it ---- */
  await page.setViewportSize({ width: 390, height: 844 });
  const stacked = await page.evaluate((SIGNUP) => {
    const aside = document.querySelector("main aside").getBoundingClientRect();
    const form = document.querySelector(SIGNUP).getBoundingClientRect();
    return aside.bottom <= form.top + 1;
  }, SIGNUP);
  if (!stacked) throw new Error("the pitch does not stack above the form on mobile");
  ok("mobile: the reasons to sign up come before the fields");
  await page.setViewportSize({ width: 1360, height: 900 });

  /* ---- The journey: no auto-login, inbox is the next stop ---- */
  await page.click(`${SIGNUP} button[type="submit"]`);
  await page.waitForURL("**/register/sent**", { timeout: 15_000 });
  await expect(page, "text=เช็คอีเมลของคุณ", "lands on the check-your-email screen");
  await expect(page, `text=${HANDLE}@example.com`, "screen names the exact inbox");
  await expect(page, 'a[href="/login"]', "offers the path to sign in after confirming");
  const headerShowsUser = await page.locator(`header >> text=${HANDLE}`).count();
  if (headerShowsUser > 0) throw new Error("registration must not sign the user in");
  ok("registration does NOT start a session");
  await page.screenshot({ path: `${SHOT_DIR}/10-register-success.png`, fullPage: false });

  // The verified flag renders the one-time banner on /login
  await page.goto(`${BASE}/login?verified=1`);
  await expect(page, "text=ยืนยันอีเมลเรียบร้อยแล้ว", "login shows the just-verified banner");

  /* ---- Friendly server error: duplicate email ---- */
  // Uses the permanent fixture account (not the handle just created) so
  // this stays one attempt behind the shared-IP registration throttle.
  const dup = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await dup.goto(`${BASE}/register`);
  await dup.fill(`${SIGNUP} input[type="email"]`, "p16-learner@example.com");
  await dup.locator(`${SIGNUP} input[autocomplete="username"]`).fill(`${HANDLE}2x`);
  await dup.locator(`${SIGNUP} input[autocomplete="new-password"]`).fill(PASSWORD);
  await dup.check(`${SIGNUP} input[type="checkbox"]`);
  await dup.click(`${SIGNUP} button[type="submit"]`);
  await expect(dup, "text=อีเมลนี้มีบัญชีอยู่แล้ว", "duplicate email answered in friendly Thai");
  await dup.screenshot({ path: `${SHOT_DIR}/11-register-dup-email.png`, fullPage: false });
  await dup.close();

  console.log(`\nRegistration E2E: ${passed}/${passed} passed (handle: ${HANDLE})`);
} finally {
  await browser.close();
}
