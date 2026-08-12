/**
 * Homepage browser E2E: hero + search deep-link, skill discovery,
 * featured course, recommendation feed, categories, community preview,
 * structured footer, and the authenticated continue-learning strip.
 * Desktop then mobile, against the real backend.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
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
  // ---------- Desktop, anonymous ----------
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  await page.goto(`${BASE}/`);
  await expect(page, "text=อบขนมให้อร่อย", "hero renders");
  await expect(page, 'input[aria-label="ค้นหาสูตรขนมและเทคนิค"]', "hero has integrated search");
  await expect(page, "text=เริ่มจากระดับไหนดี?", "skill discovery section renders");
  await expect(page, "text=คอร์สเด่นประจำสัปดาห์", "featured course section renders");
  await expect(page, "text=กำลังเป็นที่นิยม", "anonymous recommendation feed renders");
  await expect(page, "text=สำรวจตามหมวดขนม", "category explorer renders");
  await expect(page, "text=จากครัวของชุมชน", "community preview renders");
  // Behaviour, not seed order: the newest-3 window shifts whenever
  // anyone posts a thread, so assert the cards link to the board
  // instead of pinning a specific seed title.
  await expect(page, 'a[href^="/threads/"]', "community shows real questions linking to the board");
  await expect(page, 'nav[aria-label="เมนูเรียนรู้"]', "structured footer renders");
  await page.screenshot({ path: `${SHOT_DIR}/12-home-anon-desktop.png`, fullPage: true });

  // Hero search deep-links into /recipes
  await page.fill('input[aria-label="ค้นหาสูตรขนมและเทคนิค"]', "คุกกี้");
  await page.press('input[aria-label="ค้นหาสูตรขนมและเทคนิค"]', "Enter");
  await page.waitForURL("**/recipes?search=**");
  await expect(page, "text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ", "hero search lands on filtered recipes");
  await expect(page, 'button[aria-pressed]', "recipes page shows filter chips");

  // Category filter via URL param
  await page.goto(`${BASE}/`);
  await page.click("text=เริ่มต้นได้เลย >> nth=0");
  await page.waitForURL("**/courses?difficulty=beginner");
  await expect(page, "text=พื้นฐานการอบขนมปังสำหรับมือใหม่", "skill tile deep-links to beginner courses");
  await page.screenshot({ path: `${SHOT_DIR}/13-courses-filtered.png`, fullPage: false });

  // ---------- Desktop, signed in ----------
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");
  await page.goto(`${BASE}/`);
  await expect(page, "text=เรียนต่อจากที่ค้างไว้", "continue-learning strip appears for a student");
  // Real lesson counts, but not a hard-coded fraction: the learner's
  // progress moves whenever another suite completes a lesson.
  await expect(page, "text=/เรียนแล้ว \\d+ จาก \\d+ บทเรียน/", "progress card shows real lesson counts");
  // The section hides itself when the engine returns nothing  which it
  // legitimately does once an account has favourited most of the small
  // published catalogue. Assert against what the API actually returns.
  const recommended = await page.evaluate(async () => {
    const response = await fetch(
      "http://localhost:8000/api/v1/recommendations/recipes/?page_size=3",
      { credentials: "include" },
    );
    return (await response.json()).count;
  });
  // Scoped to the section heading (`h2`)  the nav also carries a
  // "แนะนำสำหรับคุณ" link to /recommendations, which a bare text locator
  // matches too.
  const sectionHeading = page.locator("h2", { hasText: "แนะนำสำหรับคุณ" });
  if (recommended > 0) {
    await sectionHeading.waitFor({ state: "visible", timeout: 15_000 });
    ok("recommendation feed becomes personal");
  } else {
    // The page runs its own fetch of the same endpoint; give it a beat to
    // resolve and render null before asserting the section is absent 
    // otherwise this races the component's in-flight request.
    await page.waitForTimeout(1000);
    if (await sectionHeading.count()) {
      throw new Error("recommendation section rendered with no recommendations");
    }
    ok("engine returned nothing, so the recommendation section is correctly absent");
  }

  // The community section shows work and sends people to /community; it
  // is deliberately not a second place to post.
  await expect(page, "text=จากครัวของชุมชน", "home has a community section");
  if (await page.locator("text=เขียนโพสต์…").count()) {
    throw new Error("the home page is hosting a post composer again");
  }
  await expect(page, 'a[href="/community"]', "community section links to the community");
  await expect(page, 'a[href="/recipes/create"]', "recipe section keeps its own creation CTA");
  await page.screenshot({ path: `${SHOT_DIR}/14-home-authed-desktop.png`, fullPage: true });

  // ---------- Mobile ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${BASE}/`);
  await expect(mobile, "text=อบขนมให้อร่อย", "mobile hero renders");
  await expect(mobile, 'input[aria-label="ค้นหาสูตรขนมและเทคนิค"]', "mobile search present");
  await expect(mobile, "text=สำรวจตามหมวดขนม", "mobile category explorer renders");
  await mobile.screenshot({ path: `${SHOT_DIR}/15-home-mobile.png`, fullPage: true });
  await mobile.close();

  console.log(`\nHomepage E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
