/**
 * Assistant page browser E2E: the conversation list must load (this is
 * the regression that shipped a 405  listing lives under /me/), a new
 * conversation appears in it, and a Thai question gets a reply.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
let passed = 0;

function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")}  ${label}`);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });

  // Fail loudly on any API error response the page triggers.
  const failures = [];
  page.on("response", (response) => {
    const url = response.url();
    // 401 on the profile mirror is the designed "anonymous" signal
    // (ADR 0007)  every page load makes it before sign-in.
    const authProbe = url.includes("/users/profile/") && response.status() === 401;
    if (url.includes("/api/v1/") && response.status() >= 400 && !authProbe) {
      failures.push(`${response.status()} ${response.request().method()} ${url}`);
    }
  });

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");

  await page.goto(`${BASE}/assistant`);
  await page.waitForSelector("text=ผู้ช่วย AI");
  ok("assistant page renders");

  // The conversation list must resolve  no error state in the sidebar.
  await page.waitForTimeout(1500);
  if (await page.locator("text=Method \"GET\" not allowed").count()) {
    throw new Error("conversation list still 405s");
  }
  if (await page.locator("text=เกิดข้อผิดพลาด").count()) {
    throw new Error("conversation list rendered an error state");
  }
  ok("conversation list loads without an error state");

  await page.click('button:has-text("+ บทสนทนาใหม่")');
  await page.waitForSelector("text=พิมพ์คำถามแรกของคุณด้านล่างได้เลย");
  ok("new conversation opens the chat pane");

  // It must also appear in the sidebar list (proves the list endpoint works)
  await page.waitForSelector('button:has-text("บทสนทนา #")');
  ok("the new conversation shows in the sidebar list");

  await page.fill('textarea[aria-label="ข้อความถึงผู้ช่วย"]', "ทำไมเค้กถึงยุบตรงกลาง?");
  await page.click('button:has-text("ส่ง")');
  await page.waitForSelector("text=ทำไมเค้กถึงยุบตรงกลาง?");
  ok("the question appears as a user bubble");
  await page.waitForSelector("text=ผู้ช่วยจำลอง");
  ok("the assistant replies in Thai");
  await page.screenshot({ path: `${SHOT_DIR}/31-assistant.png`, fullPage: true });

  if (failures.length) {
    throw new Error(`API errors during the run:\n  ${failures.join("\n  ")}`);
  }
  ok("no 4xx/5xx API responses during the whole flow");

  console.log(`\nAssistant E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
