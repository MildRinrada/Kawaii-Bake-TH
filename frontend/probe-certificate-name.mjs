/**
 * Probe: the legal name moved from sign-up to certificate issuance.
 *
 * Registration used to demand ชื่อจริง/นามสกุล from everyone so that the
 * minority who claim a certificate would have a name to print. The name
 * is now asked for once, where it is the point of the request. This walks
 * the whole path with a brand-new account and no mocking: sign up (three
 * fields), finish a course, ask for the certificate, get asked for a
 * name, and check the credential prints the name that was typed - and
 * that the account remembers it afterwards.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const API = process.env.API_BASE_URL ?? "http://localhost:8000/api/v1";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const HANDLE = `certless${Date.now().toString(36)}`;
const PASSWORD = "Butter!Croissant9";
const COURSE = process.env.COURSE_SLUG ?? "bread-basics";
// Sign-in and sign-up share one page behind the slider.
const SIGNUP = 'form[aria-label="สมัครสมาชิก"]';
const SIGNIN = 'form[aria-label="เข้าสู่ระบบ"]';
const FIRST = "ณิชกานต์";
const LAST = "ตั้งจิต";

let passed = 0;
const ok = (label) => console.log(`  ok ${String(++passed).padStart(2, "0")}  ${label}`);

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 950 } });

  /* ---- Sign up through the real form: three fields, no name ---- */
  await page.goto(`${BASE}/register`);
  await page.fill(`${SIGNUP} input[type="email"]`, `${HANDLE}@example.com`);
  await page.locator(`${SIGNUP} input[autocomplete="username"]`).fill(HANDLE);
  await page.locator(`${SIGNUP} input[autocomplete="new-password"]`).fill(PASSWORD);
  await page.check(`${SIGNUP} input[type="checkbox"]`);
  await page.click(`${SIGNUP} button[type="submit"]`);
  await page.waitForURL("**/register/sent**", { timeout: 15_000 });
  ok(`signed up as @${HANDLE} without giving a legal name`);

  await page.goto(`${BASE}/login`);
  await page.fill(`${SIGNIN} input[type="email"]`, `${HANDLE}@example.com`);
  await page.fill(`${SIGNIN} input[type="password"]`, PASSWORD);
  await page.click(`${SIGNIN} button[type="submit"]`);
  await page.waitForSelector(`text=${HANDLE}`, { timeout: 15_000 });
  ok("signed in");

  /* ---- Finish a course through the real endpoints ---- */
  const finished = await page.evaluate(
    async ({ api, course }) => {
      const csrf = () =>
        document.cookie
          .split("; ")
          .find((part) => part.startsWith("csrftoken="))
          ?.slice("csrftoken=".length) ?? "";
      await fetch(`${api}/auth/csrf/`, { credentials: "include" });
      const post = (path) =>
        fetch(`${api}${path}`, {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRFToken": csrf(), "Content-Type": "application/json" },
        });

      const enroll = await post(`/courses/${course}/enroll/`);
      const syllabus = await (
        await fetch(`${api}/courses/${course}/lessons/`, {
          credentials: "include",
        })
      ).json();
      const lessons = syllabus.results ?? syllabus;
      const codes = [];
      for (const lesson of lessons) {
        codes.push((await post(`/lessons/${lesson.id}/complete/`)).status);
      }
      return { enroll: enroll.status, lessons: lessons.length, codes };
    },
    { api: API, course: COURSE },
  );
  if (!finished.lessons || finished.codes.some((code) => code >= 400)) {
    throw new Error(`could not finish ${COURSE}: ${JSON.stringify(finished)}`);
  }
  ok(`finished ${COURSE} (${finished.lessons} lessons, enroll ${finished.enroll})`);

  /* ---- The certificate asks for the name registration did not ---- */
  await page.goto(`${BASE}/certificates`);
  await page.waitForSelector("text=รอออกใบ");
  ok("the completed course shows as pending, not issued");

  await page.click('button:has-text("ขอรับใบประกาศนียบัตร")');
  await page.waitForSelector("text=ชื่อที่จะพิมพ์บนใบประกาศ");
  const dialog = await page.evaluate(() => {
    const given = document.querySelector('input[autocomplete="given-name"]');
    const family = document.querySelector('input[autocomplete="family-name"]');
    const submit = [...document.querySelectorAll("dialog button")].find(
      (button) => button.textContent.includes("ออกใบประกาศ"),
    );
    return {
      hasGiven: Boolean(given),
      hasFamily: Boolean(family),
      submitDisabled: submit?.disabled ?? null,
    };
  });
  if (!dialog.hasGiven || !dialog.hasFamily) {
    throw new Error("the name dialog does not offer both name fields");
  }
  if (dialog.submitDisabled !== true) {
    throw new Error("the dialog issues a certificate with an empty name");
  }
  ok("issuing asks for the name, and will not proceed without one");
  await page.screenshot({ path: `${SHOT_DIR}/85-certificate-name.png` });

  await page.fill('input[autocomplete="given-name"]', FIRST);
  await page.fill('input[autocomplete="family-name"]', LAST);
  await page.click('dialog button:has-text("ออกใบประกาศ")');
  await page.waitForSelector("text=ออกใบประกาศนียบัตรเรียบร้อย");
  await page.waitForSelector("text=ได้รับแล้ว");
  ok("the certificate is issued once the name is given");

  /* ---- What was printed, and what the account kept ---- */
  const record = await page.evaluate(
    async (api) => {
      const certificates = await (
        await fetch(`${api}/me/certificates/`, { credentials: "include" })
      ).json();
      const profile = await (
        await fetch(`${api}/users/profile/`, { credentials: "include" })
      ).json();
      return {
        printed: certificates.results[0]?.student_name,
        number: certificates.results[0]?.certificate_number,
        stored: `${profile.first_name} ${profile.last_name}`.trim(),
      };
    },
    API,
  );
  if (record.printed !== `${FIRST} ${LAST}`) {
    throw new Error(`certificate prints "${record.printed}", not the typed name`);
  }
  ok(`printed name is the typed one, not the handle (${record.number})`);
  if (record.stored !== `${FIRST} ${LAST}`) {
    throw new Error(`the account did not keep the name (${record.stored})`);
  }
  ok("the account kept the name, so the next certificate will not ask");

  await page.click('button:has-text("ดูใบประกาศนียบัตร")');
  await page.waitForSelector(`text=${FIRST} ${LAST}`);
  ok("the rendered certificate shows the name");

  console.log(`\nCertificate-name probe: ${passed}/${passed} passed (@${HANDLE})`);
} finally {
  await browser.close();
}
