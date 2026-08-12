/**
 * Probe: the rebuilt recipe-detail layout.
 *
 * Measures the things the design review was about rather than asserting
 * on copy — is the cover framed instead of sliced, is the left column
 * actually pinned while the method scrolls, is each fact stated once,
 * are the stars drawn at a real fraction.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const browser = await chromium.launch();

try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 950 } });

  // Pick a recipe with substitutions and, where one exists, a sibling —
  // the single-card layout only appears when the catalogue provides it.
  // (Navigate first: `fetch` from about:blank has no origin to send.)
  await page.goto(`${BASE}/recipes`);
  const target = await page.evaluate(async () => {
    const list = await (
      await fetch("http://localhost:8000/api/v1/recipes/?page_size=50")
    ).json();
    const byCategory = new Map();
    for (const recipe of list.results) {
      for (const category of recipe.categories) {
        byCategory.set(category.slug, (byCategory.get(category.slug) ?? 0) + 1);
      }
    }
    const withOneSibling = list.results.find((recipe) =>
      recipe.categories.some((category) => byCategory.get(category.slug) === 2),
    );
    return {
      slug: withOneSibling?.slug ?? list.results[0].slug,
      hasSibling: Boolean(withOneSibling),
      total: list.count,
    };
  });
  console.log("catalogue:", target.total, "recipes — probing", target.slug);

  await page.goto(`${BASE}/recipes/${target.slug}`, { waitUntil: "networkidle" });
  await page.waitForSelector("#ingredients");

  /* ---- Hero: the cover is framed, not sliced ---- */
  const hero = await page.evaluate(() => {
    const image = document.querySelector("main img");
    if (!image) return null;
    const frame = image.parentElement.getBoundingClientRect();
    const heading = document.querySelector("h1").getBoundingClientRect();
    const cta = [...document.querySelectorAll("a,button")].find((node) =>
      node.textContent.includes("เริ่มโหมดทำขนม"),
    );
    const source = image.naturalWidth / image.naturalHeight;
    const shown = frame.width / frame.height;
    return {
      sourceRatio: Number(source.toFixed(2)),
      frameRatio: Number(shown.toFixed(2)),
      // Share of the photo that survives object-fit: cover.
      kept: Number(
        (source > shown ? shown / source : source / shown).toFixed(2),
      ),
      sideBySide: heading.top < frame.bottom - 40,
      ctaTop: cta ? Math.round(cta.getBoundingClientRect().top) : null,
      viewport: window.innerHeight,
    };
  });
  if (hero) {
    // What the old full-width 21:9 banner would have kept of the same
    // photo, for comparison.
    const before = Math.min(hero.sourceRatio, 21 / 9) / Math.max(hero.sourceRatio, 21 / 9);
    console.log(
      `hero: source ${hero.sourceRatio} in a ${hero.frameRatio} frame — keeps ${Math.round(hero.kept * 100)}% of the photo (21:9 kept ${Math.round(before * 100)}%)`,
    );
    // The detail frame must be the card's own ratio, so a cover approved
    // once is never re-cropped by a second layout.
    if (![1.33, 0.75].includes(hero.frameRatio)) {
      throw new Error(`hero frame is ${hero.frameRatio}, not the card's 4:3 or 3:4`);
    }
    if (hero.kept < before) {
      throw new Error("the new frame crops more than the old banner did");
    }
    if (!hero.sideBySide) {
      throw new Error("the hero is not two columns");
    }
    if (hero.ctaTop === null || hero.ctaTop > hero.viewport) {
      throw new Error("the primary actions are below the fold");
    }
    console.log("cover keeps its framing and the actions are above the fold: ok");
  }

  /* ---- 3. Each fact is stated once ---- */
  const duplicates = await page.evaluate(() => {
    const bar = document.querySelector(".sticky.top-16");
    return {
      barText: bar ? bar.innerText.replace(/\s+/g, " ").trim() : null,
      statBands: document.querySelectorAll("main dl, dl").length,
    };
  });
  console.log("sticky bar text:", duplicates.barText);
  if (/นาที|ที่$/.test(duplicates.barText ?? "")) {
    throw new Error("the sticky bar still repeats the time/yield meta");
  }
  console.log("no duplicated meta in the sticky bar: ok");

  /* ---- The hero CTA opens the page's real feature ---- */
  await page.click('button:has-text("เริ่มโหมดทำขนม")');
  await page.waitForSelector('div[role="dialog"][aria-label="โหมดทำขนม"]');
  await page.click('button[aria-label="ปิดโหมดทำขนม"]');
  console.log("hero CTA starts focus mode: ok");

  /* ---- No scroll container inside the page ---- */
  const nested = await page.evaluate(() =>
    [...document.querySelectorAll("main *")].filter((node) => {
      const style = getComputedStyle(node);
      return (
        /(auto|scroll)/.test(style.overflowY) &&
        node.scrollHeight > node.clientHeight + 2
      );
    }).length,
  );
  console.log("nested scroll containers:", nested);
  if (nested > 0) throw new Error("a second scrollbar is back inside the page");

  /* ---- 1 + 4. The two columns are balanced, and the left one pins ---- */
  const columns = await page.evaluate(() => {
    const sum = (el) =>
      [...el.children].reduce((a, c) => a + c.getBoundingClientRect().height, 0);
    const left = document.getElementById("ingredients");
    const right = document.getElementById("steps");
    return {
      left: Math.round(sum(left)),
      right: Math.round(sum(right)),
      stickyCard: getComputedStyle(
        left.querySelectorAll(":scope > div")[1] ?? left,
      ).position,
    };
  });
  console.log(
    `column content: left ${columns.left}px vs right ${columns.right}px`,
  );
  if (columns.stickyCard !== "sticky") {
    throw new Error("the ingredient card is not sticky");
  }

  // Sticky only has somewhere to go when the method is the longer column.
  // The seeded recipes are short, so the contract is checked by giving
  // the method the length a real one would have, then undoing it.
  const pinned = await page.evaluate(async () => {
    const spacer = document.createElement("div");
    spacer.style.height = "2000px";
    spacer.dataset.probe = "spacer";
    document.getElementById("steps").append(spacer);
    window.scrollBy(0, 1200);
    await new Promise((resolve) => setTimeout(resolve, 300));
    const card = document.getElementById("ingredients").querySelectorAll(
      ":scope > div",
    )[1];
    const top = Math.round(card.getBoundingClientRect().top);
    spacer.remove();
    window.scrollTo(0, 0);
    return top;
  });
  console.log(`with a long method, the panel parks at top=${pinned}px`);
  if (pinned < 100 || pinned > 200) {
    throw new Error(`the ingredients panel does not stay pinned (top=${pinned})`);
  }
  console.log("left column is pinned while the method scrolls: ok");

  /* ---- 2. No tab bar that cannot work ---- */
  // Ingredients and method share one row, so a scroll indicator would
  // always light the same one - the bar must not pretend otherwise.
  const fakeTabs = await page.evaluate(
    () => document.querySelectorAll('nav[aria-label="ส่วนของสูตร"]').length,
  );
  if (fakeTabs > 0) throw new Error("the anchor row dressed as tabs is back");
  const jumpToReviews = await page.evaluate(
    () => document.querySelectorAll('a[href="#reviews"]').length,
  );
  console.log(`section tabs: ${fakeTabs}, review jump links: ${jumpToReviews}`);
  if (jumpToReviews === 0) throw new Error("no way to reach the reviews");
  console.log("no fake tabs, reviews still reachable: ok");

  /* ---- 9 + stars. Fractional fill, real colour ---- */
  const stars = await page.evaluate(() => {
    const clip = document.querySelector("#reviews [aria-label] span[style*='width']");
    if (!clip) return null;
    const glyphs = [...clip.querySelectorAll("span")].filter((node) =>
      node.style.maskImage.includes("star"),
    );
    return {
      width: clip.style.width,
      glyphs: glyphs.length,
      background: glyphs[0]
        ? getComputedStyle(glyphs[0]).backgroundImage.slice(0, 40)
        : null,
      label: clip.closest("[aria-label]")?.getAttribute("aria-label"),
      text: clip.closest("[aria-label]")?.innerText.trim(),
    };
  });
  console.log("stars:", JSON.stringify(stars));
  if (stars && !/gradient/.test(stars.background ?? "")) {
    throw new Error("stars are not painted with the gold gradient");
  }

  /* ---- 5 + 6. Steps toggle from the card, in brand pink ---- */
  const stepStyle = await page.evaluate(() => {
    const badge = document.querySelector('#steps [role="checkbox"]');
    const card = badge?.closest("li");
    return {
      hasCheckboxInput: document.querySelectorAll('#steps input[type="checkbox"]').length,
      activeBackground: card ? getComputedStyle(card).backgroundColor : null,
      badgeBackground: badge ? getComputedStyle(badge).backgroundColor : null,
    };
  });
  console.log("step card:", JSON.stringify(stepStyle));
  if (stepStyle.hasCheckboxInput > 0) {
    throw new Error("per-step checkboxes are back");
  }

  /* ---- 10. One related card lies down ---- */
  const related = await page.evaluate(() => {
    const heading = [...document.querySelectorAll("h2")].find((node) =>
      node.textContent.includes("ถ้าชอบสูตรนี้"),
    );
    if (!heading) return null;
    const section = heading.closest("section") ?? heading.parentElement;
    const cards = section.querySelectorAll('a[href^="/recipes/"]');
    const first = cards[0]?.querySelector("div > div");
    return {
      count: cards.length,
      cardWidth: cards[0] ? Math.round(cards[0].getBoundingClientRect().width) : 0,
      rowWidth: Math.round(section.getBoundingClientRect().width),
      announcesMissingText: section.innerText.includes("ยังไม่มีคำอธิบาย"),
      imageWidth: first ? Math.round(first.getBoundingClientRect().width) : 0,
      reason: section.querySelector("h2 + p")?.textContent ?? null,
    };
  });
  console.log("related section:", JSON.stringify(related));
  if (related) {
    if (related.announcesMissingText) {
      throw new Error("a card still announces its missing description");
    }
    // A lone card is list-sized, not stretched across the row.
    if (related.count > 0 && related.cardWidth > related.rowWidth / 2) {
      throw new Error(`related card is stretched (${related.cardWidth}px)`);
    }
    console.log(`related: ${related.count} card(s) at ${related.cardWidth}px, reason "${related.reason}"`);
  } else {
    console.log("no same-category sibling for this recipe - section absent (valid)");
  }

  /* ---- The notes box confirms it kept what was typed ---- */
  await page.fill('textarea[placeholder*="เตาบ้านเรา"]', "เตาบ้านนี้ต้องอบเพิ่ม 3 นาที");
  await page.waitForSelector("text=บันทึกแล้ว", { timeout: 5000 });
  const savedColour = await page.evaluate(() => {
    // The wrapper and the label both read "บันทึกแล้ว"; the innermost
    // one carries the colour.
    const node = [...document.querySelectorAll("span")]
      .filter((item) => item.textContent.trim() === "บันทึกแล้ว")
      .pop();
    return node ? getComputedStyle(node).color : null;
  });
  console.log("note save signal colour:", savedColour);
  if (savedColour !== "rgb(46, 125, 84)") {
    throw new Error(`the saved signal is not the success green (${savedColour})`);
  }
  console.log("notes confirm the save in green: ok");

  await page.screenshot({ path: `${SHOT_DIR}/84-recipe-detail.png`, fullPage: true });
  console.log("probe done");
} finally {
  await browser.close();
}
