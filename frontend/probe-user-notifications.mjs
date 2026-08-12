/** Probe: the user-facing notification center renders campaign icon + CTA. */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
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
  // Admin inbox: a campaign whose kind draws the row, plus the CTA
  // "ดูสูตรใหม่" → /recipes. (The composer's emoji field is gone: the
  // announcement kind picks the glyph and colour now - ADR 0036.)
  const adminCtx = await browser.newContext();
  const admin = await adminCtx.newPage();
  await signIn(admin, STAFF);
  await admin.goto(`${BASE}/notifications`);
  // {{user_name}} resolves to the profile display name at delivery.
  await admin.waitForSelector("text=สวัสดี Rinrada Laiad", { timeout: 15_000 });
  const item = admin.locator("li", { hasText: "สวัสดี Rinrada Laiad" }).first();
  const glyph = await item.evaluate((row) => {
    const bubble = row.querySelector("span[aria-hidden] span");
    return {
      mask: bubble?.style.maskImage ?? "",
      badge: row.innerText.includes("ประกาศจากทีมงาน"),
      emoji: /\p{Extended_Pictographic}/u.test(row.innerText),
    };
  });
  console.log("admin row glyph:", JSON.stringify(glyph));
  if (!glyph.mask.includes("/icons/ui/")) {
    throw new Error("the announcement row has no line glyph");
  }
  if (glyph.emoji) {
    throw new Error("an emoji is back in the notification row");
  }
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
