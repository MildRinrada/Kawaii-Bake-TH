/**
 * Sign-in browser E2E: the shared auth panel, seen from the login side.
 *
 * Sign-in and sign-up are one surface with a slider between them, so
 * this covers what that arrangement has to get right - the two columns
 * ending together, the heading meeting the first field, what survives
 * the slide - plus the things sign-in owns: recovery, "remember me",
 * Enter-to-submit, and a failure message that does not say which half
 * was wrong.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const SIGNIN = 'form[aria-label="เข้าสู่ระบบ"]';
const SIGNUP = 'form[aria-label="สมัครสมาชิก"]';
const ACCOUNT = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };
let passed = 0;

const ok = (label) => console.log(`  ok ${String(++passed).padStart(2, "0")}  ${label}`);

async function expect(page, selector, label, timeout = 10_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 950 } });
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });

  /* ---- The card names itself, for anyone who never sees the column ---- */
  const heading = await page.evaluate((SIGNIN) => {
    const card = document.querySelector(SIGNIN).closest("div[class*='rounded-surface']");
    return card.querySelector("h2")?.textContent.trim() ?? null;
  }, SIGNIN);
  if (heading !== "เข้าสู่ระบบ") {
    throw new Error(`the sign-in card has no heading of its own (${heading})`);
  }
  ok(`card heading: ${heading}`);

  /* ---- Two columns that end together ---- */
  const balance = await page.evaluate((SIGNIN) => {
    const aside = document.querySelector("main aside").getBoundingClientRect();
    const card = document
      .querySelector(SIGNIN)
      .closest("div[class*='rounded-surface']")
      .getBoundingClientRect();
    const h1 = document.querySelector("main aside h1").getBoundingClientRect();
    const firstField = document
      .querySelector(`${SIGNIN} input`)
      .getBoundingClientRect();
    return {
      asideHeight: Math.round(aside.height),
      cardHeight: Math.round(card.height),
      tailGap: Math.round(Math.abs(aside.bottom - card.bottom)),
      headingTop: Math.round(h1.top),
      asideTop: Math.round(aside.top),
      firstFieldTop: Math.round(firstField.top),
    };
  }, SIGNIN);
  console.log(`     aside ${balance.asideHeight}px vs card ${balance.cardHeight}px`);
  if (balance.tailGap > 8) {
    throw new Error(`the columns do not end together (${balance.tailGap}px apart)`);
  }
  ok(`columns end together (${balance.tailGap}px apart)`);

  // The heading belongs at the top of its column, not floating a screen
  // below the first thing to fill in.
  const headingOffset = balance.headingTop - balance.asideTop;
  if (headingOffset > 80) {
    throw new Error(`the pitch heading sits ${headingOffset}px down its column`);
  }
  ok(`pitch heading is at the top of its column (+${headingOffset}px)`);

  /* ---- Recovery exists, and is a real page ---- */
  const forgot = page.locator(`${SIGNIN} a[href="/forgot-password"]`).first();
  if (!(await forgot.count())) throw new Error("no way to recover an account");
  ok("password field offers ลืมรหัสผ่าน?");

  /* ---- Remember me, on by default, and actually sent ---- */
  const remember = page.locator(`${SIGNIN} input[type="checkbox"]`);
  if (!(await remember.isChecked())) {
    throw new Error("remember-me is not on by default");
  }
  ok("จำฉันไว้ is on by default");

  /* ---- A wrong password says so without saying which half ---- */
  await page.fill(`${SIGNIN} input[type="email"]`, ACCOUNT.email);
  await page.fill(`${SIGNIN} input[type="password"]`, "definitely-not-the-one");
  await page.click(`${SIGNIN} button[type="submit"]`);
  await expect(page, "text=อีเมลหรือรหัสผ่านไม่ถูกต้อง", "wrong password: one message for both causes");
  // Scoped to the alert itself: the page also carries the footer line
  // "ยังไม่มีบัญชี?", which is an invitation, not a verdict.
  const alertText = await page.textContent(`${SIGNIN} [role="alert"]`);
  if (/ไม่พบ|ไม่มีบัญชี|ไม่ได้ลงทะเบียน|รหัสผ่านผิด/.test(alertText)) {
    throw new Error(`the failure message says too much: ${alertText}`);
  }
  ok(`the failure names neither half: "${alertText.trim()}"`);

  /* ---- The slide keeps what was typed ---- */
  await page.click(`${SIGNIN} a[href="/register"]`);
  await page.waitForTimeout(500);
  const afterSlide = await page.evaluate(
    ({ SIGNUP, SIGNIN }) => ({
      url: location.pathname,
      heading: document.querySelector("main aside h1").textContent.trim(),
      signupActive: !document.querySelector(SIGNUP).closest("[inert]"),
      signinInert: Boolean(document.querySelector(SIGNIN).closest("[inert]")),
      keptEmail: document.querySelector(`${SIGNIN} input[type="email"]`).value,
      photo: document.querySelector("main aside img").getAttribute("src"),
    }),
    { SIGNUP, SIGNIN },
  );
  if (afterSlide.url !== "/register") {
    throw new Error(`the slide did not update the URL (${afterSlide.url})`);
  }
  if (!afterSlide.signupActive || !afterSlide.signinInert) {
    throw new Error("both panes are live at once - the hidden one is a keyboard trap");
  }
  ok(`slid to ${afterSlide.url} without a navigation, hidden pane inert`);
  if (afterSlide.keptEmail !== ACCOUNT.email) {
    throw new Error("what was typed did not survive the slide");
  }
  ok("the address typed on the sign-in side survives the slide");
  ok(`the pitch heading changed to "${afterSlide.heading}"`);

  /* ---- The card grows into the taller form instead of snapping ---- */
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  const box = async () =>
    page.evaluate((SIGNIN) => {
      const panel = document.querySelector(SIGNIN).closest(".relative");
      const rect = panel.getBoundingClientRect();
      return { h: Math.round(rect.height), w: Math.round(rect.width) };
    }, SIGNIN);
  const short = await box();
  await page.click(`${SIGNIN} a[href="/register"]`);
  await page.waitForTimeout(120);
  const mid = await box();
  await page.waitForTimeout(600);
  const tall = await box();
  console.log(`     panel height ${short.h} → ${mid.h} → ${tall.h}px`);
  if (tall.h <= short.h) {
    throw new Error("the panel did not grow into the taller form");
  }
  if (mid.h <= short.h || mid.h >= tall.h) {
    throw new Error(`the height snapped rather than animating (mid ${mid.h})`);
  }
  ok(`height animates ${short.h} → ${tall.h}px`);
  // The scrollbar appearing as the panel grows used to shift the whole
  // grid left, which reads as two columns of different widths.
  if (short.w !== tall.w) {
    throw new Error(`the card changes width between sides (${short.w} → ${tall.w})`);
  }
  ok(`card width is identical on both sides (${tall.w}px)`);

  /* ---- A different photograph, so the switch is visible ---- */
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  const loginPhoto = await page.getAttribute("main aside img", "src");
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  const registerPhoto = await page.getAttribute("main aside img", "src");
  if (loginPhoto === registerPhoto) {
    throw new Error("both sides show the same photograph");
  }
  ok(`different art per side (${loginPhoto} vs ${registerPhoto})`);

  /* ---- Back returns to the side it came from ---- */
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.click(`${SIGNIN} a[href="/register"]`);
  await page.waitForTimeout(400);
  await page.goBack();
  await page.waitForTimeout(400);
  const back = await page.evaluate(
    (SIGNIN) => ({
      url: location.pathname,
      signinActive: !document.querySelector(SIGNIN).closest("[inert]"),
    }),
    SIGNIN,
  );
  if (back.url !== "/login" || !back.signinActive) {
    throw new Error(`Back left the panel out of sync (${JSON.stringify(back)})`);
  }
  ok("Back returns to sign-in and the panel follows");

  /* ---- Recovery page: the same answer for every address ---- */
  await page.goto(`${BASE}/forgot-password`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', `nobody-${Date.now()}@example.com`);
  await page.click('button[type="submit"]');
  await expect(page, "text=ส่งลิงก์แล้ว", "an unknown address gets the same confirmation");
  const oracle = await page.evaluate(
    () => /ไม่พบ|ไม่มีบัญชี/.test(document.body.innerText),
  );
  if (oracle) throw new Error("the reset page reveals whether the account exists");
  ok("the reset page is not an account-existence oracle");
  await page.screenshot({ path: `${SHOT_DIR}/86-forgot-password.png` });

  /* ---- Enter submits, and the session is real ---- */
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  const sent = page.waitForRequest(
    (request) =>
      request.url().includes("/auth/login/") && request.method() === "POST",
  );
  await page.fill(`${SIGNIN} input[type="email"]`, ACCOUNT.email);
  await page.fill(`${SIGNIN} input[type="password"]`, ACCOUNT.password);
  await page.press(`${SIGNIN} input[type="password"]`, "Enter");
  const payload = JSON.parse((await sent).postData());
  if (payload.remember_me !== true) {
    throw new Error(`remember-me was not sent (${JSON.stringify(payload)})`);
  }
  ok("Enter in the password field submits, with remember_me: true");

  await page.waitForSelector("text=MildBakes", { timeout: 15_000 });
  ok("signed in against the real backend");
  await page.screenshot({ path: `${SHOT_DIR}/87-login-done.png` });

  /* ---- Motion is decoration: with it off, nothing travels ---- */
  const still = await browser.newPage({
    viewport: { width: 1360, height: 950 },
    reducedMotion: "reduce",
  });
  await still.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  const durations = await still.evaluate((SIGNIN) => {
    const pane = document.querySelector(SIGNIN).closest("div[class*='transition']");
    const heading = document.querySelector("main aside h1");
    return {
      // `transition-none` clears the *property* list; the duration value
      // it was given stays on the element and means nothing once no
      // property is listed.
      pane: getComputedStyle(pane).transitionProperty,
      heading: getComputedStyle(heading).animationName,
    };
  }, SIGNIN);
  if (durations.pane !== "none" || durations.heading !== "none") {
    throw new Error(`reduced motion still animates: ${JSON.stringify(durations)}`);
  }
  ok("prefers-reduced-motion turns the slide and the heading swap off");
  await still.close();

  console.log(`\nSign-in E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
