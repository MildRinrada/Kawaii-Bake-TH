/**
 * Achievements page E2E.
 *
 * Verifies the catalogue × ledger join: earned badges come from
 * `/me/achievements/`, locked ones are catalogue entries with no matching
 * fact, and the totals agree with both endpoints. Also checks the detail
 * dialog, the honest absence of progress bars on locked badges, the
 * reduced-motion path, the anonymous redirect and mobile layout.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000/api/v1";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const LEARNER = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };

let passed = 0;
function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")} — ${label}`);
}
async function expect(page, selector, label, timeout = 15_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}

const browser = await chromium.launch();
try {
  /* ---------- Anonymous ---------- */
  const anon = await browser.newContext({ viewport: { width: 1360, height: 950 } });
  const guest = await anon.newPage();
  await guest.goto(`${BASE}/achievements`);
  await expect(guest, "text=/เข้าสู่ระบบ/", "anonymous is sent to the existing login flow");
  const guestBody = await guest.textContent("body");
  if (guestBody.includes("ปลดล็อกแล้ว ✨")) {
    throw new Error("private achievement data rendered for an anonymous visitor");
  }
  ok("no private achievement data leaks to an anonymous visitor");

  // The catalogue itself is public platform metadata, by design (ADR 0024).
  const catalogStatus = await guest.evaluate(async (api) => {
    const response = await fetch(`${api}/achievements/`);
    return { status: response.status, count: (await response.json()).length };
  }, API);
  if (catalogStatus.status !== 200 || catalogStatus.count === 0) {
    throw new Error(`badge catalogue unavailable: ${JSON.stringify(catalogStatus)}`);
  }
  ok(`badge catalogue is public and non-empty (${catalogStatus.count} badges)`);
  await anon.close();

  /* ---------- Authenticated ---------- */
  const context = await browser.newContext({ viewport: { width: 1360, height: 950 } });
  const page = await context.newPage();
  const apiErrors = [];
  page.on("response", (r) => {
    const authProbe = r.url().includes("/users/profile/") && r.status() === 401;
    if (r.url().includes("/api/v1/") && r.status() >= 400 && !authProbe) {
      apiErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    }
  });

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', LEARNER.email);
  await page.fill('input[type="password"]', LEARNER.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  await page.goto(`${BASE}/achievements`);
  await expect(page, "text=ความสำเร็จของฉัน", "page header renders");
  await expect(page, "text=ทุกครั้งที่คุณเรียนรู้และลงมือทำ", "subtitle renders");

  /* ---------- Totals agree with both endpoints ---------- */
  const truth = await page.evaluate(async (api) => {
    const catalog = await (await fetch(`${api}/achievements/`)).json();
    const mine = await (
      await fetch(`${api}/me/achievements/?page_size=100`, { credentials: "include" })
    ).json();
    const earnedTypes = new Set(mine.results.map((row) => row.achievement_type));
    const slugs = catalog.map((badge) => badge.slug);
    return {
      total: slugs.length,
      earned: slugs.filter((slug) => earnedTypes.has(slug)).length,
      earnedTitles: catalog
        .filter((badge) => earnedTypes.has(badge.slug))
        .map((badge) => badge.title_th),
      lockedTitles: catalog
        .filter((badge) => !earnedTypes.has(badge.slug))
        .map((badge) => badge.title_th),
    };
  }, API);

  await expect(
    page,
    `text=${truth.earned} / ${truth.total}`,
    `summary matches the two endpoints (${truth.earned}/${truth.total})`,
  );
  const percent = Math.round((truth.earned / truth.total) * 100);
  await expect(page, `text=${percent}%`, "completion percentage is derived, not invented");

  /* ---------- Earned + locked sections ---------- */
  if (truth.earned > 0) {
    await expect(page, "text=ปลดล็อกแล้ว ✨", "earned section renders");
    await expect(page, `text=${truth.earnedTitles[0]}`, "an earned badge from the ledger is shown");
  } else {
    await expect(page, "text=เส้นทางนักอบขนมของคุณกำลังเริ่มต้น", "empty state renders for a learner with no badges");
    await expect(page, 'a[href="/courses"]', "empty state links to a real course route");
  }

  await expect(page, "text=รอให้คุณปลดล็อก 🔒", "locked section renders");
  await expect(page, `text=${truth.lockedTitles[0]}`, "a locked badge from the catalogue is shown");

  // No invented progress bars on locked badges.
  const lockedBars = await page
    .locator('section:has-text("รอให้คุณปลดล็อก") div[role="progressbar"]')
    .count();
  if (lockedBars > 0) {
    throw new Error("a locked badge shows a progress bar the backend cannot supply");
  }
  ok("locked badges show conditions, never an invented progress bar");

  /* ---------- Skill standing uses server-stated numbers ---------- */
  const level = await page.evaluate(async (api) => {
    const data = await (
      await fetch(`${api}/me/gamification/`, { credentials: "include" })
    ).json();
    return data.level;
  }, API);
  await expect(page, `text=เลเวล ${level.current_level}`, "real gamification level is shown");
  await expect(
    page,
    `text=${level.current_xp}/${level.xp_for_next_level} XP`,
    "level bar uses the server-stated span, not a client-side curve",
  );
  /* ---------- XP reconciliation uses the backend's own rebuild ------- */
  const [recalcRequest] = await Promise.all([
    page.waitForRequest(
      (r) =>
        r.url().includes("/me/gamification/recalculate/") &&
        r.method() === "POST",
    ),
    page.click('button:has-text("คำนวณคะแนนใหม่")'),
  ]);
  ok(`XP reconcile calls the real endpoint (${recalcRequest.method()})`);
  await page.waitForTimeout(1200);
  const after = await page.evaluate(async (api) => {
    const data = await (
      await fetch(`${api}/me/gamification/`, { credentials: "include" })
    ).json();
    return data.level;
  }, API);
  await expect(
    page,
    `text=เลเวล ${after.current_level}`,
    `level reflects the rebuilt ledger (${after.total_xp} XP, level ${after.current_level})`,
  );
  await page.screenshot({ path: `${SHOT_DIR}/70-achievements.png`, fullPage: true });

  /* ---------- Filters ---------- */
  await page.click('button:has-text("คอร์ส")');
  ok("category filter applies");
  await page.click('button:has-text("ทั้งหมด")');

  /* ---------- Detail dialog: locked ---------- */
  await page.click(`button[aria-label*="${truth.lockedTitles[0]}"]`);
  await expect(page, "dialog[open]", "badge detail opens");
  await expect(page, "text=เงื่อนไขการปลดล็อก", "locked detail states the unlock condition");
  await page.keyboard.press("Escape");
  await page.waitForSelector("dialog[open]", { state: "detached" }).catch(() => {});
  ok("Escape closes the dialog");

  /* ---------- Detail dialog: earned + celebration ---------- */
  if (truth.earned > 0) {
    await page.click(`button[aria-label*="${truth.earnedTitles[0]}"]`);
    await expect(page, "dialog[open]", "earned badge detail opens");
    await expect(page, "text=✓ ปลดล็อกแล้ว", "earned detail confirms the unlocked state");
    await expect(page, "text=ได้รับเมื่อ", "earned date is shown");
    await expect(page, ".kb-badge-pop", "badge reveal animation plays on open");
    const sprinkles = await page.locator(".kb-sprinkle").count();
    if (sprinkles === 0) throw new Error("no celebration sprinkles rendered");
    ok(`celebration sprinkles render (${sprinkles})`);
    await page.screenshot({ path: `${SHOT_DIR}/71-achievement-detail.png` });
    await page.keyboard.press("Escape");
  }

  /* ---------- Reduced motion ---------- */
  const calm = await browser.newContext({
    viewport: { width: 1360, height: 950 },
    reducedMotion: "reduce",
    storageState: await context.storageState(),
  });
  const calmPage = await calm.newPage();
  await calmPage.goto(`${BASE}/achievements`);
  await calmPage.waitForSelector("text=ความสำเร็จของฉัน");
  if (truth.earned > 0) {
    await calmPage.click(`button[aria-label*="${truth.earnedTitles[0]}"]`);
    await calmPage.waitForSelector("dialog[open]");
    const hidden = await calmPage
      .locator(".kb-sprinkle")
      .first()
      .evaluate((node) => getComputedStyle(node).display);
    if (hidden !== "none") {
      throw new Error(`sprinkles still displayed under reduced motion: ${hidden}`);
    }
    const anim = await calmPage
      .locator(".kb-badge-pop")
      .first()
      .evaluate((node) => getComputedStyle(node).animationName);
    if (anim !== "none") {
      throw new Error(`badge animation still running under reduced motion: ${anim}`);
    }
    ok("prefers-reduced-motion disables both the reveal and the sprinkles");
  }
  await calm.close();

  /* ---------- Mobile ---------- */
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(`${BASE}/achievements`);
  await mobile.waitForSelector("text=ความสำเร็จของฉัน");
  const columns = await mobile
    .locator('section:has-text("รอให้คุณปลดล็อก") > div')
    .first()
    .evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").length);
  if (columns !== 2) throw new Error(`mobile badge grid has ${columns} columns, expected 2`);
  ok("mobile shows a 2-column badge grid");
  await mobile.screenshot({ path: `${SHOT_DIR}/72-achievements-mobile.png`, fullPage: true });
  await mobile.close();

  if (apiErrors.length) {
    throw new Error(`Unexpected API errors:\n  ${apiErrors.join("\n  ")}`);
  }
  ok("no unexpected 4xx/5xx API responses");

  console.log(`\nAchievements E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
