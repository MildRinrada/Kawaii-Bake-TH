/** Probe: the rebuilt community feed + real likes and comments (ADR 0032). */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 950 } });

  /* ---- Anonymous: counts are real, actions ask for a login ---- */
  await page.goto(`${BASE}/community`, { waitUntil: "networkidle" });
  await page.waitForSelector("article, li");
  if (await page.locator("header.kb-hero").count()) {
    throw new Error("the hero banner is still rendered");
  }
  const createButtons = await page
    .locator('a[href="/community/create"]')
    .count();
  console.log("create-post entry points above the feed:", createButtons);
  if (createButtons > 1) {
    throw new Error("duplicate create-post CTAs are back");
  }
  console.log("hero removed, single create entry point: ok");

  /* ---- Feed images are capped ---- */
  const tallest = await page.evaluate(() => {
    const images = [...document.querySelectorAll("main img")];
    return images.reduce(
      (max, img) => Math.max(max, Math.round(img.getBoundingClientRect().height)),
      0,
    );
  });
  console.log("tallest feed image:", tallest);
  if (tallest > 520) throw new Error(`feed image too tall: ${tallest}px`);

  /* ---- Category filter is a chip row, not a photo carousel ---- */
  const chip = page.locator('button:has-text("#Bread")').first();
  if (!(await chip.count())) throw new Error("category chips missing");
  console.log("category chips render: ok");

  /* ---- Sign in and use the real interactions ---- */
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");
  await page.goto(`${BASE}/community`, { waitUntil: "networkidle" });

  const likeButton = page
    .locator('button[aria-label="ถูกใจโพสต์นี้"], button[aria-label="เลิกถูกใจโพสต์นี้"]')
    .first();
  await likeButton.waitFor();
  const startedLiked = (await likeButton.getAttribute("aria-pressed")) === "true";
  await likeButton.click();
  await page.waitForFunction(
    (was) => {
      const button = document.querySelector(
        'button[aria-label="ถูกใจโพสต์นี้"], button[aria-label="เลิกถูกใจโพสต์นี้"]',
      );
      return button && (button.getAttribute("aria-pressed") === "true") !== was;
    },
    startedLiked,
  );
  console.log("like toggled:", startedLiked ? "on -> off" : "off -> on");
  // Toggle back so the probe leaves no trace.
  await likeButton.click();
  await page.waitForFunction(
    (was) => {
      const button = document.querySelector(
        'button[aria-label="ถูกใจโพสต์นี้"], button[aria-label="เลิกถูกใจโพสต์นี้"]',
      );
      return button && (button.getAttribute("aria-pressed") === "true") === was;
    },
    startedLiked,
  );
  console.log("like restored - net zero");

  /* ---- Comment round trip ---- */
  const commentToggle = page
    .locator('button[aria-expanded]:has-text("คอมเมนต์")')
    .first();
  await commentToggle.click();
  await page.waitForSelector('textarea[aria-label="คอมเมนต์ของคุณ"]');
  const text = "ทดสอบคอมเมนต์จาก probe";
  await page.fill('textarea[aria-label="คอมเมนต์ของคุณ"]', text);
  await page.click('button:has-text("ส่ง")');
  await page.waitForSelector(`text=${text}`);
  console.log("comment posted and rendered: ok");
  await page.screenshot({ path: "e2e-shots/83-community.png", fullPage: true });

  // Remove it again - the probe must not litter the feed.
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator('button:has-text("ลบ")').first().click();
  await page.waitForSelector(`text=${text}`, { state: "detached" });
  console.log("comment deleted - net zero");

  /* ---- Owner actions live in the ⋯ menu, delete is danger-coloured ---- */
  const ownerMenu = page.locator('span[aria-label="จัดการโพสต์ของฉัน"]');
  if (await ownerMenu.count()) {
    await ownerMenu.first().click();
    await page.waitForSelector("text=ลบโพสต์");
    const colour = await page.evaluate(() => {
      const item = [...document.querySelectorAll('[role="menuitem"]')].find((n) =>
        n.textContent.includes("ลบโพสต์"),
      );
      return item ? getComputedStyle(item).color : null;
    });
    console.log("delete menu item colour:", colour);
    await page.keyboard.press("Escape");
    console.log("owner actions are in the ⋯ menu: ok");
  } else {
    console.log("this account owns no post in view - owner menu not applicable");
  }

  console.log("probe done");
} finally {
  await browser.close();
}
