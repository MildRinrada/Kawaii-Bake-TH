/**
 * Recipe list (smart baking library) browser E2E: header count, grouped
 * search suggestions, ingredient search, quick categories, multi-select
 * filters + active summary, sort, saved hearts seeded from real
 * favorites, no-results recovery, mobile filter sheet.
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
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });

  // ---------- Header + catalog ----------
  await page.goto(`${BASE}/recipes`);
  await expect(page, "text=/ทั้งหมด \\d+ สูตร/", "header shows total recipe count");
  await expect(page, 'button:has-text("Cookies")', "quick category row renders");
  await expect(page, "text=เรียงตาม", "sort control renders");

  // Time + pantry now live behind a disclosure so the recipes sit
  // higher on the page; opening it must reveal the same real filters.
  await expect(page, "text=ตัวกรองเพิ่มเติม", "extra filters are folded away by default");
  if (await page.locator("text=มีวัตถุดิบ:").first().isVisible()) {
    throw new Error("pantry row is visible before opening the disclosure");
  }
  await page.click("summary:has-text('ตัวกรองเพิ่มเติม')");
  await expect(page, "text=มีวัตถุดิบ:", "pantry filter row renders once expanded");

  // Empty categories stay visible but stop being controls.
  const emptyCategories = await page.evaluate(async () => {
    const rows = await (
      await fetch("http://localhost:8000/api/v1/recipe-categories/")
    ).json();
    return rows.filter((row) => row.recipe_count === 0).map((row) => row.name);
  });
  if (emptyCategories.length) {
    const tile = page.locator(
      `button:has-text("${emptyCategories[0]}")`,
    ).first();
    if (!(await tile.isDisabled())) {
      throw new Error(`empty category "${emptyCategories[0]}" is still clickable`);
    }
    ok(`empty categories (${emptyCategories.join(", ")}) render dimmed and disabled`);
  } else {
    ok("every category has recipes, so none needs the disabled treatment");
  }

  // ---------- Grouped search suggestions ----------
  await page.fill('input[aria-label="ค้นหาสูตรขนม"]', "คุกกี้");
  await expect(page, "text=สูตรขนม >> nth=0", "suggestion panel opens");
  await expect(page, 'p:has-text("สูตรขนม") ~ button', "recipe suggestions appear");
  await expect(page, 'button:has-text("หาสูตรที่ใช้ “คุกกี้” เป็นวัตถุดิบ")', "ingredient search action offered");
  await page.screenshot({ path: `${SHOT_DIR}/23-search-suggest.png` });

  // Recipe suggestion navigates straight to the detail.
  // Which recipe ranks first depends on live search relevance, so read the
  // suggestion's own label and assert the page we land on matches it 
  // hard-coding a slug here made this fail whenever the catalog changed.
  const suggestion = page.locator('p:has-text("สูตรขนม") ~ button').first();
  const suggested = (await suggestion.textContent()).trim();
  await suggestion.click();
  await page.waitForURL(/\/recipes\/[^/?]+$/);
  const landedOn = (await page.locator("h1").first().textContent()).trim();
  if (!suggested.startsWith(landedOn) && !landedOn.startsWith(suggested)) {
    throw new Error(`suggestion "${suggested}" opened "${landedOn}"`);
  }
  ok(`recipe suggestion deep-links to its own detail page (${landedOn})`);
  await page.goBack();

  // ---------- Ingredient search ----------
  await page.fill('input[aria-label="ค้นหาสูตรขนม"]', "เนย");
  await page.click('button:has-text("หาสูตรที่ใช้ “เนย” เป็นวัตถุดิบ")');
  await page.waitForURL("**ingredient=**");
  await expect(page, "text=/เนย/", "ingredient filter chip appears in summary");
  await expect(page, "text=คุกกี้ช็อกโกแลตชิพนุ่มหนึบ", "ingredient filter finds recipes using เนย");

  // ---------- Multi-select filters + summary ----------
  await page.click('button:has-text("ง่าย") >> nth=0');
  await page.click('button:has-text("ปานกลาง") >> nth=0');
  await expect(page, "text=กำลังกรอง:", "active filter summary appears");
  await page.waitForURL("**difficulty=easy%2Cmedium**");
  ok("difficulty is multi-select (easy,medium in URL)");
  await page.click("text=ล้างทั้งหมด");
  await page.waitForURL(`${BASE}/recipes`);
  ok("clear-all resets to the full catalog");

  // ---------- Cards line up regardless of missing optional text ----------
  const cardHeights = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('a[href^="/recipes/"] > div')];
    return cards.slice(0, 3).map((card) => Math.round(card.getBoundingClientRect().height));
  });
  if (new Set(cardHeights).size > 1) {
    throw new Error(`recipe cards in one row differ in height: ${cardHeights}`);
  }
  ok(`cards in a row share one height (${cardHeights[0]}px) even with a blank summary`);

  // ---------- Sort ----------
  await page.selectOption("select", "quickest");
  await page.waitForURL("**ordering=quickest**");
  ok("sort control drives the ordering param");
  await page.selectOption("select", "newest");

  // ---------- No-results recovery ----------
  await page.fill('input[aria-label="ค้นหาสูตรขนม"]', "มัทฉะซาวร์โดว์");
  await page.press('input[aria-label="ค้นหาสูตรขนม"]', "Enter");
  await expect(page, "text=ไม่พบสูตรที่ตรงกับ", "no-results state explains the miss");
  await expect(page, "text=หรือลองสูตรเหล่านี้ดูก่อน", "no-results offers real alternative recipes");
  await expect(page, 'button:has-text("ล้างตัวกรองทั้งหมด")', "recovery action offered");
  await page.screenshot({ path: `${SHOT_DIR}/24-no-results.png`, fullPage: true });
  await page.click('button:has-text("ล้างตัวกรองทั้งหมด")');

  // ---------- Saved hearts seeded from real favorites ----------
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");
  await page.goto(`${BASE}/recipes`);
  await expect(page, 'button[aria-pressed="true"][aria-label*="นำ"]', "already-favorited card shows a filled heart on load");
  // A full toggle round trip, so the run leaves the account's favourites
  // exactly as it found them. Starting from whichever state the first card
  // is in keeps this working once every recipe has been saved.
  const heart = page.locator('button[aria-label*="รายการโปรด"]').first();
  const heartLabel = await heart.getAttribute("aria-label");
  const startedSaved = (await heart.getAttribute("aria-pressed")) === "true";

  await heart.click();
  await expect(
    page,
    startedSaved ? "text=นำออกจากรายการโปรดแล้ว" : "text=บันทึกเข้ารายการโปรดแล้ว",
    "toggling the heart from the card confirms via toast",
  );
  await heart
    .and(page.locator(`[aria-pressed="${startedSaved ? "false" : "true"}"]`))
    .waitFor({ timeout: 10_000 });
  ok(`heart toggled without opening the recipe (${heartLabel?.slice(0, 30)}…)`);

  await heart.click();
  await heart
    .and(page.locator(`[aria-pressed="${startedSaved}"]`))
    .waitFor({ timeout: 10_000 });
  ok("toggled back  the account's favourites are unchanged by this run");
  await page.screenshot({ path: `${SHOT_DIR}/25-recipes-authed.png`, fullPage: true });

  // ---------- Mobile: sheet + horizontal categories ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${BASE}/recipes`);
  await mobile.waitForSelector('h1:has-text("สูตรขนม")');
  await mobile.click('button:has-text("ตัวกรอง")');
  await expect(mobile, 'div[role="dialog"][aria-label="ตัวกรองสูตร"]', "mobile bottom-sheet filter opens");
  await mobile.click('div[role="dialog"] button:has-text("ง่าย")');
  await expect(mobile, 'button:has-text("ดูผลลัพธ์")', "sheet shows apply-with-count action");
  await mobile.screenshot({ path: `${SHOT_DIR}/26-mobile-filter-sheet.png` });
  await mobile.click('button:has-text("ดูผลลัพธ์")');
  await expect(mobile, "text=กำลังกรอง:", "applied filter shows in summary on mobile");
  await mobile.close();

  console.log(`\nRecipe-list E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
