/** Probe: the user-facing notification center renders campaign icon + CTA. */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const STAFF = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };
const LEARNER = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };

async function signIn(page, { email, password }) {
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), {
    timeout: 15_000,
  });
}

const browser = await chromium.launch();
try {
  // Admin inbox: campaign with icon 🧁 + CTA "ดูสูตรใหม่" → /recipes.
  const adminCtx = await browser.newContext();
  const admin = await adminCtx.newPage();
  await signIn(admin, STAFF);
  await admin.goto(`${BASE}/notifications`);
  // {{user_name}} resolves to the profile display name at delivery.
  await admin.waitForSelector("text=สวัสดี Rinrada Laiad", { timeout: 15_000 });
  const item = admin.locator("li", { hasText: "สวัสดี Rinrada Laiad" }).first();
  console.log("admin icon 🧁:", (await item.textContent())?.includes("🧁"));
  const cta = item.locator('a:has-text("ดูสูตรใหม่")');
  console.log(
    "admin cta:",
    (await cta.count()) > 0,
    "| href:",
    await cta.getAttribute("href"),
  );
  await admin.screenshot({
    path: "e2e-shots/61-user-notification-center.png",
    fullPage: true,
  });
  await adminCtx.close();
  console.log("probe done");
} finally {
  await browser.close();
}
