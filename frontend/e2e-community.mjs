/**
 * Community posts & recipe creation E2E.
 *
 * Anonymous: sees Community in the nav, can read the public feed, is
 * offered sign-in instead of a composer, and cannot reach the creation
 * routes.
 *
 * Authenticated: composes a post with text + image + an attached recipe
 * picked from the real selector, publishes it, sees it in the feed and
 * on the attached recipe's page, edits and deletes it — and deleting the
 * post leaves the recipe untouched.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000/api/v1";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const LEARNER = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };
const STAMP = Date.now() % 100000;
const CAPTION = `วันนี้ลองอบขนมปังครั้งแรก อร่อยมาก ${STAMP}`;

// A real 1x1 JPEG so the server's Pillow actually decodes it.
const JPEG_1X1 =
  "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a" +
  "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA" +
  "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==";

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
let postUrl = null;
try {
  /* ================= ANONYMOUS ================= */
  const anon = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const guest = await anon.newPage();

  await guest.goto(BASE);
  await expect(guest, 'header a[href="/community"]', "Community appears in the main navigation");
  await expect(guest, "text=จากครัวของชุมชน", "home has a community section");
  await expect(guest, "text=เข้าสู่ระบบเพื่อโพสต์", "anonymous home shows a sign-in CTA, not a composer");
  const guestHome = await guest.textContent("body");
  if (guestHome.includes("เขียนโพสต์…")) {
    throw new Error("the authenticated composer rendered for an anonymous visitor");
  }
  ok("no authenticated composer leaks to an anonymous visitor");
  await expect(guest, 'a[href="/recipes/create"]', "home recipe section has its own + เพิ่มสูตรอาหาร CTA");

  await guest.goto(`${BASE}/community`);
  await expect(guest, "text=ชุมชนคนรักการอบขนม", "anonymous can open the community feed");
  await expect(guest, "text=เข้าสู่ระบบเพื่อสร้างโพสต์", "feed offers sign-in instead of composing");
  await expect(guest, 'button[aria-pressed="false"]', "category filter chips render");
  if (await guest.locator("text=มีอะไรอยากแบ่งปันเกี่ยวกับการทำขนม?").count()) {
    throw new Error("the authenticated composer rendered on the feed for a guest");
  }
  ok("no composer on the feed for an anonymous visitor");

  // Filters are real server-side reads, not client-side slicing.
  const [filterRequest] = await Promise.all([
    guest.waitForRequest((r) => r.url().includes("/gallery/") && r.url().includes("category=")),
    guest.locator('div[role="group"] button').nth(1).click(),
  ]);
  ok(`category chip filters server-side (${filterRequest.url().split("?")[1].slice(0, 40)}…)`);
  await guest.goto(`${BASE}/community`);
  await guest.screenshot({ path: `${SHOT_DIR}/62-community-anon.png`, fullPage: true });

  await guest.goto(`${BASE}/community/create`);
  await expect(guest, "text=/เข้าสู่ระบบ/", "anonymous cannot reach the post composer");
  await guest.goto(`${BASE}/recipes/create`);
  await expect(guest, "text=/เข้าสู่ระบบ/", "anonymous cannot reach recipe creation");
  await anon.close();

  /* ================= AUTHENTICATED ================= */
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
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

  await page.goto(BASE);
  await expect(page, "text=เขียนโพสต์…", "home shows the composer for a signed-in user");

  /* ---- The inline composer publishes without leaving the feed ---- */
  await page.goto(`${BASE}/community`);
  await expect(page, "text=มีอะไรอยากแบ่งปันเกี่ยวกับการทำขนม?", "feed shows the collapsed composer");
  await page.click('button:has-text("มีอะไรอยากแบ่งปันเกี่ยวกับการทำขนม?")');
  await expect(page, "#post-caption", "composer expands in place");
  const inlineCaption = `โพสต์จากคอมโพสเซอร์ในฟีด ${STAMP}`;
  await page.fill("#post-caption", inlineCaption);
  await page.click('button[type="submit"]:has-text("เผยแพร่โพสต์")');
  await expect(page, "text=เผยแพร่โพสต์แล้ว", "inline composer publishes");
  if (!page.url().endsWith("/community")) {
    throw new Error(`inline publish navigated away to ${page.url()}`);
  }
  ok("publishing inline never leaves the feed");
  await expect(page, `text=${inlineCaption}`, "the new post is prepended to the feed immediately");

  // Clean it up through the detail page's owner controls.
  await page.click(`li:has-text("${inlineCaption}") a:has-text("เปิดโพสต์")`);
  await page.waitForURL("**/community/posts/**");
  await page.click('button:has-text("ลบโพสต์")');
  await page.locator('div[role="dialog"] button:has-text("ลบโพสต์")').click();
  await page.waitForURL("**/community", { timeout: 15_000 });
  ok("inline-composed post deleted — no residue");

  await page.goto(`${BASE}/community/create`);
  await expect(page, "text=สร้างโพสต์", "the full-page composer still exists");

  /* ---- Compose: text + image + recipe attachment ---- */
  await page.fill("#post-caption", CAPTION);
  await page.setInputFiles('input[aria-label="เลือกรูปภาพ"]', {
    name: "bake.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from(JPEG_1X1, "base64"),
  });
  await expect(page, 'img[src^="blob:"]', "picked image previews locally before upload");

  await page.click('button:has-text("แนบสูตร")');
  await expect(page, 'dialog[aria-label="เลือกสูตรที่จะแนบ"]', "recipe selector opens");

  // Drafts must not be offerable: the backend only accepts a reference to
  // a publicly visible recipe, so the selector reads the public feed.
  // The title is read live — hard-coding one broke the moment that recipe
  // was published.
  const hidden = await page.evaluate(async (api) => {
    const mine = await (
      await fetch(`${api}/recipes/?scope=mine&page_size=100`, {
        credentials: "include",
      })
    ).json();
    const draft = mine.results.find((row) => row.status !== "published");
    return draft ? draft.title : null;
  }, API);
  const absentTerm = hidden ?? "ขนมที่ไม่มีอยู่จริงเลยสักสูตร";
  await page.fill('input[aria-label="ค้นหาสูตร"]', absentTerm);
  await page.waitForTimeout(1200);
  await expect(
    page,
    "text=/ไม่พบสูตรที่ตรงกับ/",
    hidden
      ? `a draft recipe is not offerable as an attachment (${hidden})`
      : "no draft to test with — an unmatched search shows the empty state",
  );

  await page.fill('input[aria-label="ค้นหาสูตร"]', "คุกกี้");
  await page.waitForTimeout(1000);
  const firstResult = page.locator('dialog[aria-label="เลือกสูตรที่จะแนบ"] li button').first();
  const attachedTitle = (await firstResult.textContent()).trim().split("\n")[0];
  await firstResult.click();
  await expect(page, "text=โพสต์นี้แนบสูตร", "attachment renders as a reference card, not as the post");
  ok(`recipe attached by search, never by id (${attachedTitle.slice(0, 20)}…)`);
  await expect(page, "text=แนบสูตร", "composer toolbar offers photo and recipe actions");
  await page.screenshot({ path: `${SHOT_DIR}/63-community-compose.png`, fullPage: true });

  /* ---- Publish ---- */
  await page.click('button[type="submit"]:has-text("เผยแพร่โพสต์")');
  await expect(page, "text=เผยแพร่โพสต์แล้ว", "post published through the real API");
  await page.waitForURL("**/community/posts/**", { timeout: 15_000 });
  postUrl = page.url();
  ok(`redirected to the new post (${postUrl.split("/").pop()})`);
  await expect(page, `text=${CAPTION}`, "post detail shows the caption");
  await expect(page, 'img[src*="localhost:8000"]', "the uploaded image is served from the API origin");
  await expect(page, "text=โพสต์นี้แนบสูตร", "detail shows the attached recipe reference");
  await expect(page, "text=ระบบคอมเมนต์และบันทึกโพสต์ยังไม่เปิดใช้งาน", "missing interactions are stated, not faked");
  await page.screenshot({ path: `${SHOT_DIR}/64-community-post.png`, fullPage: true });

  /* ---- It appears in the feed ---- */
  await page.goto(`${BASE}/community`);
  await expect(page, `text=${CAPTION}`, "the post appears in the community feed");
  await expect(page, "text=แชร์สูตร", "a post with a recipe carries the derived kind badge");
  // The rich attachment card needs fields the feed payload lacks; the page
  // enriches them from the public recipe list in one read.
  await expect(page, 'a[aria-label^="ดูสูตร"]', "attachment renders as a rich recipe card in the feed");
  await expect(page, "text=นักอบขนมในฟีดนี้", "desktop sidebar lists real bakers from the feed");

  /* ---- And on the attached recipe's page ---- */
  const recipeLink = await page
    .locator('a[aria-label^="ดูสูตร"]')
    .first()
    .getAttribute("href");
  await page.goto(`${BASE}${recipeLink}`);
  await expect(page, "text=โพสต์จากชุมชนเกี่ยวกับสูตรนี้", "recipe detail has a community section");
  await expect(page, `text=${CAPTION}`, "the attached post shows on the recipe page");
  await expect(page, "text=แชร์ประสบการณ์เกี่ยวกับสูตรนี้", "recipe detail offers the contextual share CTA");
  await page.screenshot({ path: `${SHOT_DIR}/65-recipe-community.png`, fullPage: true });

  /* ---- The contextual shortcut pre-attaches the recipe ---- */
  await page.click('a:has-text("แชร์ประสบการณ์เกี่ยวกับสูตรนี้")');
  await page.waitForURL("**/community/create?recipe=**");
  await expect(page, "text=โพสต์นี้แนบสูตร", "recipe arrives pre-attached from the recipe page");

  /* ---- Edit and delete own post; the recipe survives ---- */
  await page.goto(postUrl);
  await page.click('button:has-text("แก้ไขข้อความ")');
  await page.fill("#edit-caption", `${CAPTION} (แก้ไขแล้ว)`);
  await page.click('button:has-text("บันทึก")');
  await expect(page, "text=แก้ไขโพสต์แล้ว", "owner can edit their own post");
  await expect(page, "text=(แก้ไขแล้ว)", "the edit is read back from the server");

  await page.click('button:has-text("ลบโพสต์")');
  await expect(page, "text=ลบโพสต์นี้?", "delete asks for confirmation");
  await expect(page, "text=สูตรที่แนบไว้จะไม่ถูกลบ", "the dialog states the recipe is not deleted");
  await page.locator('div[role="dialog"] button:has-text("ลบโพสต์")').click();
  await page.waitForURL("**/community", { timeout: 15_000 });
  ok("owner can delete their own post");
  postUrl = null;

  await page.goto(`${BASE}${recipeLink}`);
  await page.waitForSelector("h1");
  ok("the attached recipe still exists after its post was deleted");

  /* ---- Recipe creation is a separate, structured flow ---- */
  await page.goto(`${BASE}/recipes`);
  await expect(page, 'a[href="/recipes/create"]', "recipe list has + เพิ่มสูตรอาหาร");
  const recipeListBody = await page.textContent("body");
  if (recipeListBody.includes("+ สร้างโพสต์")) {
    throw new Error("post creation is competing with recipe creation on the recipe list");
  }
  ok("the recipe list does not offer post creation");
  await page.click('a[href="/recipes/create"]');
  await page.waitForURL("**/recipes/create");
  await expect(page, "text=เพิ่มสูตรอาหาร", "recipe creation page renders");
  await expect(page, "text=วัตถุดิบ", "it is a structured recipe form, not a social composer");
  await expect(page, "text=ไปสร้างโพสต์แทน", "it points social intent at the community composer");
  await page.screenshot({ path: `${SHOT_DIR}/66-recipe-create.png`, fullPage: true });

  /* ---- Mobile ---- */
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(`${BASE}/community`);
  await mobile.waitForSelector("text=ชุมชนคนรักการอบขนม");
  if (await mobile.locator("aside").isVisible().catch(() => false)) {
    throw new Error("the desktop sidebar is visible on mobile");
  }
  ok("sidebar is hidden on mobile, feed stays single-column");
  ok("community feed works on mobile");
  await mobile.screenshot({ path: `${SHOT_DIR}/67-community-mobile.png`, fullPage: true });
  await mobile.close();

  if (apiErrors.length) {
    throw new Error(`Unexpected API errors:\n  ${apiErrors.join("\n  ")}`);
  }
  ok("no unexpected 4xx/5xx API responses");

  console.log(`\nCommunity E2E: ${passed}/${passed} passed`);
} finally {
  if (postUrl) console.log(`\n!! leftover post: ${postUrl}`);
  await browser.close();
}
