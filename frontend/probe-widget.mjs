/** Probe: the floating assistant chat widget - lifecycle, persistence rules, mobile. */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const API = "http://localhost:8000/api/v1";

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 900 });

  const conversationCount = () =>
    page.evaluate(async (api) => {
      const response = await fetch(`${api}/me/assistant/conversations/`, {
        credentials: "include",
      });
      return (await response.json()).count;
    }, API);

  /* ---- Anonymous: no widget ---- */
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  if (await page.locator('button[aria-label="เปิดผู้ช่วย AI"]').count()) {
    throw new Error("widget visible to an anonymous visitor");
  }
  console.log("anonymous: widget hidden");

  /* ---- Login ---- */
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");

  await page.goto(`${BASE}/recipes`, { waitUntil: "networkidle" });
  await page.waitForSelector('button[aria-label="เปิดผู้ช่วย AI"]');
  console.log("authenticated: floating button present");

  /* ---- Opening must not persist anything ---- */
  const before = await conversationCount();
  await page.click('button[aria-label="เปิดผู้ช่วย AI"]');
  await page.waitForSelector("text=มีอะไรให้ช่วยเรื่องการอบขนมไหม");
  await page.screenshot({ path: "e2e-shots/71-widget-empty.png" });
  if ((await conversationCount()) !== before) {
    throw new Error("opening the widget created a conversation");
  }
  console.log("open widget: no conversation persisted");

  /* ---- Shell-mounted: the open panel survives navigation ---- */
  await page.click('header nav a[href="/courses"]');
  await page.waitForURL("**/courses");
  await page.waitForSelector('section[aria-label="ผู้ช่วย AI"]');
  console.log("panel state survives in-app navigation");

  /* ---- First message creates exactly one conversation ---- */
  await page.fill(
    'textarea[aria-label="ข้อความถึงผู้ช่วย"]',
    "ทำไมเค้กถึงยุบตรงกลาง?",
  );
  await page.keyboard.press("Enter");
  await page.waitForSelector("text=ทำไมเค้กถึงยุบตรงกลาง?");
  await page.waitForFunction(() => {
    const dialog = document.querySelector('section[aria-label="ผู้ช่วย AI"]');
    return (
      dialog && dialog.querySelectorAll(".whitespace-pre-wrap").length >= 3
    );
  });
  console.log("assistant replied to the first message");
  await page.screenshot({ path: "e2e-shots/72-widget-chat.png" });
  if ((await conversationCount()) !== before + 1) {
    throw new Error("first send did not persist exactly one conversation");
  }
  console.log("first send: exactly one conversation created");

  /* ---- Second message reuses it ---- */
  await page.fill(
    'textarea[aria-label="ข้อความถึงผู้ช่วย"]',
    "ควรใช้เนยชนิดไหนทำครัวซองต์?",
  );
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => {
    const dialog = document.querySelector('section[aria-label="ผู้ช่วย AI"]');
    return (
      dialog && dialog.querySelectorAll(".whitespace-pre-wrap").length >= 5
    );
  });
  if ((await conversationCount()) !== before + 1) {
    throw new Error("second send created another conversation");
  }
  console.log("second send: same conversation");

  /* ---- Kebab menu goes to the full history ---- */
  await page.click('section[aria-label="ผู้ช่วย AI"] >> text=⋮');
  await page.click("text=ดูประวัติการสนทนา");
  await page.waitForURL("**/assistant");
  await page.waitForSelector("text=ผู้ช่วย AI");
  console.log("kebab menu navigates to /assistant history");
  await page.screenshot({
    path: "e2e-shots/73-widget-history.png",
    fullPage: true,
  });

  /* ---- Refresh = fresh empty chat; mobile fits the viewport ---- */
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.click('button[aria-label="เปิดผู้ช่วย AI"]');
  await page.waitForSelector("text=มีอะไรให้ช่วยเรื่องการอบขนมไหม");
  const box = await page
    .locator('section[aria-label="ผู้ช่วย AI"]')
    .boundingBox();
  if (!box || box.x < 0 || box.x + box.width > 390) {
    throw new Error(`mobile panel overflows: ${JSON.stringify(box)}`);
  }
  console.log("refresh resets to an empty chat; mobile panel fits");
  await page.screenshot({ path: "e2e-shots/74-widget-mobile.png" });

  console.log("probe done");
} finally {
  await browser.close();
}
