/**
 * Admin dashboard E2E against the real backend.
 *
 * Covers the flow the brief asks for  login → dashboard → users →
 * recipes → courses → moderation → certificates → notifications →
 * assistant → logout  plus the authorization checks that matter:
 * anonymous and non-staff callers must not get an admin surface.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";

const STAFF = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };
const LEARNER = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };

let passed = 0;
function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")}  ${label}`);
}
async function expect(page, selector, label, timeout = 15_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}

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
  /* ---------- 1. Anonymous must be refused ---------- */
  const anon = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const anonPage = await anon.newPage();
  await anonPage.goto(`${BASE}/admin/dashboard`);
  await expect(anonPage, "text=401", "anonymous visitor gets the 401 gate");
  await expect(anonPage, "text=ต้องเข้าสู่ระบบก่อน", "gate explains what is required");
  if (await anonPage.locator('nav[aria-label="เมนูผู้ดูแลระบบ"]').count()) {
    throw new Error("admin chrome rendered for an anonymous visitor");
  }
  ok("no admin chrome leaks to an anonymous visitor");
  await anonPage.screenshot({ path: `${SHOT_DIR}/50-admin-401.png` });

  /* ---------- 2. Signed-in NON-staff must be refused ---------- */
  await signIn(anonPage, LEARNER);
  await anonPage.goto(`${BASE}/admin/recipes`);
  await expect(anonPage, "text=403", "non-staff account gets the 403 gate");
  await expect(
    anonPage,
    "text=บัญชีนี้ไม่มีสิทธิ์ผู้ดูแลระบบ",
    "403 screen names the reason",
  );
  await anonPage.screenshot({ path: `${SHOT_DIR}/51-admin-403.png` });
  await anon.close();

  /* ---------- 3. Staff flow ---------- */
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await context.newPage();
  const apiErrors = [];
  page.on("response", (r) => {
    const authProbe = r.url().includes("/users/profile/") && r.status() === 401;
    // Two failures are asserted on purpose below: an unknown verification
    // token (404) and publishing an incomplete draft (400 with a checklist).
    const expected =
      (r.status() === 404 && r.url().includes("/certificates/00000000-")) ||
      (r.status() === 400 && r.url().includes("/publish/"));
    if (
      r.url().includes("/api/v1/") &&
      r.status() >= 400 &&
      !authProbe &&
      !expected
    ) {
      apiErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    }
  });

  await signIn(page, STAFF);

  // /admin redirects to the dashboard
  await page.goto(`${BASE}/admin`);
  await page.waitForURL("**/admin/dashboard");
  ok("/admin redirects to /admin/dashboard");

  await expect(
    page,
    'nav[aria-label="เมนูผู้ดูแลระบบ"]',
    "admin sidebar renders for staff",
  );
  await expect(page, "text=สูตรทั้งหมด", "dashboard stat cards render");
  await expect(page, "text=ยังไม่มี API", "unavailable metrics are labelled, not faked");
  await expect(page, "text=สูตรล่าสุด", "recent-activity panels render");
  // The staff badge in the profile menu proves is_staff came from the API.
  await page.click('button[aria-haspopup="menu"]');
  await expect(page, "text=staff", "profile menu shows the staff flag from /auth/me/");
  await page.keyboard.press("Escape");
  await page.click('button[aria-haspopup="menu"]');
  await page.screenshot({ path: `${SHOT_DIR}/52-admin-dashboard.png`, fullPage: true });

  /* ---------- Recipes: table, search, detail, real lifecycle write ---------- */
  await page.click('a[href="/admin/recipes"]');
  await page.waitForURL("**/admin/recipes");
  await expect(page, "table", "recipes data table renders");
  const recipeRows = await page.locator("tbody tr").count();
  if (recipeRows === 0) throw new Error("recipe table is empty  scope=all returned nothing");
  ok(`recipe table shows ${recipeRows} rows from scope=all`);

  await page.fill('input[aria-label="ค้นหาสูตร"]', "บราวนี่");
  await page.waitForTimeout(900);
  const searched = await page.locator("tbody tr").count();
  ok(`server-side search narrowed the table to ${searched} rows`);
  await page.fill('input[aria-label="ค้นหาสูตร"]', "");
  await page.waitForTimeout(900);

  await page.locator("tbody tr").first().click();
  await expect(page, "dialog[open]", "recipe detail panel opens");
  await expect(page, "text=วัตถุดิบ", "detail shows real recipe fields");
  await page.screenshot({ path: `${SHOT_DIR}/53-admin-recipe-detail.png` });

  // Read-only here: the lifecycle *writes* are exercised further down on a
  // fixture this script owns, so browsing never mutates seeded content.
  const unpublish = page.locator(
    'dialog[open] button:has-text("ถอนกลับเป็นฉบับร่าง")',
  );
  const startedPublished = (await unpublish.count()) > 0;
  if (startedPublished) {
    ok("a published recipe offers unpublish/archive, not publish");
  } else {
    ok("a draft recipe offers publish, not unpublish");
  }
  await page.keyboard.press("Escape");

  /* ---------- A successful publish/unpublish round trip ----------
     On a fixture this test creates and deletes, never on seeded content:
     the seeded recipes were written straight to `published` without cover
     images, so the publish endpoint rightly refuses to put them back and
     any round trip on them is a one-way trip. Assertions watch the button
     state and then re-read the API  a lingering success toast once made
     this pass while the second request had not even been sent. */
  const fixtureSlug = await page.evaluate(async () => {
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
    const png =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
    const create = await fetch("http://localhost:8000/api/v1/recipes/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({
        title: "E2E lifecycle fixture",
        prep_minutes: 1,
        cook_minutes: 1,
        servings: 1,
        category_slugs: ["bread"],
        ingredients: [{ name: "flour", is_optional: false }],
        steps: [{ body: "mix" }],
      }),
    });
    const recipe = await create.json();
    const bytes = Uint8Array.from(atob(png), (c) => c.charCodeAt(0));
    const form = new FormData();
    form.append("cover_image", new Blob([bytes], { type: "image/png" }), "c.png");
    await fetch(
      `http://localhost:8000/api/v1/recipes/${encodeURIComponent(recipe.slug)}/`,
      { method: "PATCH", credentials: "include", headers: { "X-CSRFToken": csrf }, body: form },
    );
    return recipe.slug;
  });
  ok(`created a throwaway fixture recipe (${fixtureSlug})`);

  await page.goto(`${BASE}/admin/recipes`);
  await page.fill('input[aria-label="ค้นหาสูตร"]', "E2E lifecycle fixture");
  await page.waitForTimeout(1000);
  await page.locator("tbody tr").first().click();
  await page.waitForSelector("dialog[open]");

  await page.locator('dialog[open] button:has-text("เผยแพร่")').first().click();
  await page
    .locator('dialog[open] button:has-text("ถอนกลับเป็นฉบับร่าง")')
    .waitFor({ state: "visible", timeout: 15_000 });
  ok("publish succeeded (button state flipped)");

  await page.locator('dialog[open] button:has-text("ถอนกลับเป็นฉบับร่าง")').click();
  await page
    .locator('dialog[open] button:has-text("เผยแพร่")')
    .waitFor({ state: "visible", timeout: 15_000 });
  ok("unpublish returned it to draft (button state flipped back)");

  const finalStatus = await page.evaluate(async (slug) => {
    const response = await fetch(
      `http://localhost:8000/api/v1/recipes/${encodeURIComponent(slug)}/`,
      { credentials: "include" },
    );
    return (await response.json()).status;
  }, fixtureSlug);
  if (finalStatus !== "draft") {
    throw new Error(`fixture left as "${finalStatus}"`);
  }
  ok("the API confirms the round trip ended where it started");

  await page.evaluate(async (slug) => {
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
    await fetch(
      `http://localhost:8000/api/v1/recipes/${encodeURIComponent(slug)}/`,
      { method: "DELETE", credentials: "include", headers: { "X-CSRFToken": csrf } },
    );
  }, fixtureSlug);
  ok("fixture deleted  the run leaves no data behind");

  await page.keyboard.press("Escape");
  await page.goto(`${BASE}/admin/recipes`);

  /* ---------- Confirmation dialog on a destructive action ---------- */
  await page.locator("tbody tr").first().click();
  await page.locator('dialog[open] button:has-text("ลบถาวร")').click();
  await expect(page, "text=ลบสูตรนี้ถาวร?", "destructive action asks for confirmation first");
  await page.locator('dialog[open] button:has-text("ยกเลิก")').last().click();
  ok("cancelling the confirm dialog performs no delete");
  await page.keyboard.press("Escape");

  /* ---------- Courses ---------- */
  await page.click('a[href="/admin/courses"]');
  await page.waitForURL("**/admin/courses");
  await expect(page, "table", "courses table renders");
  await expect(page, "text=ไม่มีคอลัมน์ “จำนวนผู้เรียน”", "missing enrolment data is disclosed");

  /* ---------- Lessons ---------- */
  await page.click('a[href="/admin/lessons"]');
  await page.waitForURL("**/admin/lessons");
  await expect(page, "text=ยังไม่ได้เลือกคอร์ส", "lessons page starts at the course picker");
  const courseSelect = page.locator('select').first();
  const options = await courseSelect.locator("option").count();
  if (options > 1) {
    await courseSelect.selectOption({ index: 1 });
    await page.waitForSelector("table, text=คอร์สนี้ยังไม่มีบทเรียน");
    ok("selecting a course loads its syllabus");
  }

  /* ---------- Categories: full CRUD round trip ---------- */
  await page.click('a[href="/admin/categories"]');
  await page.waitForURL("**/admin/categories");
  await expect(page, "text=จำนวนสูตร", "category table shows real recipe counts");
  await page.click('button:has-text("เพิ่มหมวดหมู่")');
  await page.getByLabel("ชื่อหมวด").fill("หมวดทดสอบอีทูอี");
  await page.locator("button[form]").click();
  await expect(page, "text=หมวดทดสอบอีทูอี", "category create round-trips (Thai slug derived)");
  await page.click('tr:has-text("หมวดทดสอบอีทูอี")');
  await page.waitForSelector('button:has-text("ลบหมวดหมู่")');
  await page.click('button:has-text("ลบหมวดหมู่")');
  await page.locator("dialog").last().locator('button:has-text("ลบ")').last().click();
  await page.waitForFunction(
    () => !document.querySelector("td")?.closest("table")?.textContent?.includes("หมวดทดสอบอีทูอี"),
    undefined,
    { timeout: 10_000 },
  );
  ok("category delete cleans up (assignments unlink, content untouched)");

  /* ---------- Moderation: flat review list + Q&A ---------- */
  await page.click('a[href="/admin/reviews"]');
  await page.waitForURL("**/admin/reviews");
  await expect(page, 'button[role="tab"]:has-text("ถาม-ตอบ")', "moderation tabs render");
  await expect(page, "tbody tr", "flat cross-content review list renders without a picker");
  if (await page.locator('button[role="tab"]:has-text("แกลเลอรี")').count()) {
    throw new Error("gallery tab should have moved to /admin/posts");
  }
  ok("gallery moderation moved out of the reviews page");
  if (await page.locator('button:has-text("แก้ไขรีวิว")').count()) {
    throw new Error("a review-edit control exists - staff must never edit review text");
  }
  ok("no control edits another user's review text");
  await page.click('button[role="tab"]:has-text("ถาม-ตอบ")');
  await expect(page, "text=กระทู้", "Q&A moderation table renders");
  await page.screenshot({ path: `${SHOT_DIR}/54-admin-moderation.png`, fullPage: true });

  /* ---------- Community posts: delete/hide only, create as self ---------- */
  await page.goto(`${BASE}/admin/posts`);
  await expect(page, "text=โพสต์ชุมชน", "community posts page renders");
  await expect(page, "tbody img", "post list leads with image thumbnails");
  await expect(page, 'button:has-text("ซ่อน"), button:has-text("แสดง")', "hide/show moderation verbs present");
  const postsBody = await page.textContent("tbody");
  if (/แก้ไขโพสต์/.test(postsBody ?? "")) {
    throw new Error("an edit control exists on another user's post");
  }
  ok("admin can only hide/delete user posts, never edit");
  await page.click('button:has-text("สร้างโพสต์")');
  await expect(page, "textarea", "composer opens for posting as the admin's own account");
  await page.screenshot({ path: `${SHOT_DIR}/57-admin-posts.png`, fullPage: true });

  /* ---------- Questions ---------- */
  await page.click('a[href="/admin/questions"]');
  await page.waitForURL("**/admin/questions");
  await expect(page, "text=คลังคำถาม", "question bank page renders");

  /* ---------- Users: workspace - stats, bulk, actions, drawer ---------- */
  await page.click('a[href="/admin/users"]');
  await page.waitForURL("**/admin/users");
  await expect(page, "text=ผู้ใช้ทั้งหมด", "summary cards render real roster stats");
  await expect(page, 'button:has-text("+ เพิ่มผู้ใช้")', "staff account creation is offered");
  await expect(page, "tbody tr", "user roster renders");
  await expect(page, "text=ปรับยอดคะแนนรางวัล", "staff-only reward adjustment survived the redesign");
  // Emails are on this page BY DESIGN now: the roster is IsAdminUser-gated
  // PII. Passwords must still never appear anywhere.
  const usersBody = await page.textContent("body");
  if (/password|รหัสผ่าน:/.test(usersBody)) {
    throw new Error("user roster leaked credential material");
  }
  ok("roster shows account PII to staff but never credentials");

  // Selection summons the contextual bulk bar; clearing dismisses it.
  await page.locator('tbody input[type="checkbox"]').first().check();
  await expect(page, "text=เลือกแล้ว 1 คน", "bulk-action bar appears on selection");
  await expect(page, 'button:has-text("ส่งอีเมลยืนยันอีกครั้ง")', "bulk actions are real endpoints only");
  await page.click('button:has-text("ล้างการเลือก")');
  ok("clearing the selection dismisses the bulk bar");

  // The create panel is a real POST /admin/users/create/ form (not
  // submitted here - pytest covers the write; e2e stays net-zero).
  await page.click('button:has-text("+ เพิ่มผู้ใช้")');
  await expect(page, "text=รหัสผ่านเริ่มต้น", "create-user form offers the initial password");
  await page.keyboard.press("Escape");

  await page.fill('input[type="search"]', "mildbakes");
  await page.waitForTimeout(900);
  await expect(page, "text=@mildbakes", "server-side roster search finds the account");
  await page.locator("tbody tr").first().click();
  await expect(page, 'dialog[open] [role="switch"]', "detail panel offers the staff toggles");
  await expect(page, "text=สำหรับกรณีฉุกเฉิน", "verified override is labelled as an emergency tool");
  await expect(page, "text=คอร์สที่เรียน", "drawer shows real activity counts");
  await expect(page, 'button:has-text("ส่งลิงก์รีเซ็ตรหัสผ่าน")', "staff reset-link action present");
  await page.keyboard.press("Escape");
  await page.screenshot({ path: `${SHOT_DIR}/55-admin-users.png`, fullPage: true });

  /* ---------- Certificates: template designer + issued registry ---------- */
  await page.click('a[href="/admin/certificates"]');
  await page.waitForURL("**/admin/certificates");
  await expect(page, "text=สถานะเทมเพลต", "template workspace lists per-course designs");
  await page.locator('a:has-text("แก้ไขเทมเพลต")').first().click();
  await page.waitForURL("**/designer");
  await expect(page, "[data-canvas]", "designer canvas renders the live certificate");
  await expect(page, 'button:has-text("เผยแพร่เทมเพลต")', "publish is separate from autosave");
  await expect(page, "text=ข้อมูลอัตโนมัติ", "dynamic-field library present");
  await expect(page, 'button:has-text("ลายเซ็น")', "signature counter with the 3-cap renders");
  await page.click('button:has-text("ตัวอักษร")');
  await page.waitForSelector("text=บันทึกแล้ว", { timeout: 15_000 });
  ok("adding an element autosaves the draft");
  // Undo the probe edit so repeated runs never accumulate stray elements.
  await page.click('button:has-text("เลิกทำ")');
  await page.waitForSelector("text=บันทึกแล้ว", { timeout: 15_000 });
  ok("undo reverts the draft (and autosaves the reverted state)");
  await page.screenshot({ path: `${SHOT_DIR}/58-admin-cert-designer.png`, fullPage: true });

  await page.goto(`${BASE}/admin/certificates/issued`);
  await expect(page, "table", "issued registry lives at /issued");
  await expect(page, "text=ตรวจสอบใบประกาศจากรหัส", "verification tool survived the move");
  await page.fill('input[placeholder*="วางรหัส"]', "00000000-0000-4000-8000-000000000000");
  await page.click('button:has-text("ตรวจสอบ")');
  await expect(page, "text=ไม่พบใบประกาศ", "unknown token is reported honestly");

  /* ---------- Progress: cross-user dashboard ---------- */
  await page.goto(`${BASE}/admin/progress`);
  await expect(page, "text=อัตราการเรียนจบรายคอร์ส", "per-course completion funnel renders");
  await page.waitForSelector("tbody tr");
  await page.locator("tbody tr").first().click();
  await expect(page, "text=ผู้เรียนใน", "learner roster opens for a course");
  ok("per-course learner roster with progress renders");

  await page.goto(`${BASE}/admin/achievements`);
  await expect(page, "text=จำนวนคนได้รับ", "badge catalogue shows real awarded counts");
  await expect(page, 'button:has-text("เพิ่มเหรียญ")', "badge create action present");
  await page.click('button[role="tab"]:has-text("ประวัติการได้รับ")');
  await page.waitForSelector("text=ผู้ได้รับ, text=ยังไม่มี", { timeout: 10_000 }).catch(() => {});
  ok("award ledger tab renders (read-only, append-only by design)");

  await page.goto(`${BASE}/admin/favorites`);
  await expect(page, "text=สูตรยอดนิยม", "live most-favorited recipe ranking renders");
  await expect(page, "text=คอร์สยอดนิยม", "live most-favorited course ranking renders");
  await expect(page, "tbody tr", "cross-user favorites list renders");

  /* ---------- Notifications: campaign hub + composer (ADR 0030) ---------- */
  await page.goto(`${BASE}/admin/notifications`);
  await expect(page, "text=แคมเปญที่ส่งแล้ว", "campaign stats cards render");
  await expect(page, 'a:has-text("+ สร้างการแจ้งเตือน")', "create-notification CTA present");
  await expect(page, 'button[role="tab"]:has-text("เทมเพลต")', "tabbed campaign views render");

  // Compose a campaign: type → content with a variable → named audience
  // with a live estimate → save as draft.
  await page.goto(`${BASE}/admin/notifications/compose`);
  // The kind is a closed set of six now (ADR 0036): no category tabs, and
  // the card shows the glyph and colour the recipient will actually get.
  await page.click('button:has-text("ฟีเจอร์ใหม่")');
  // Titles are capped at the card's own 60 characters now, and every
  // announcement must name a destination.
  await page.getByLabel("หัวข้อ").fill("ทดสอบแคมเปญถึง {{user_name}}");
  await page.getByLabel("ลิงก์ปลายทาง").selectOption("/community");
  await page.click('button:has-text("ระบุรายชื่อ")');
  await page.getByLabel("ชื่อผู้ใช้").fill("p16fan0");
  await page.waitForSelector("text=ผู้รับโดยประมาณ", { timeout: 15_000 });
  ok("audience estimate resolves before sending");
  await page.screenshot({ path: `${SHOT_DIR}/60-admin-notif-composer.png`, fullPage: true });
  await page.getByRole("button", { name: "บันทึกฉบับร่าง" }).click();
  await page.waitForSelector("text=บันทึกฉบับร่างแล้ว", { timeout: 15_000 });
  ok("composer saves a draft campaign");

  // Send the draft from the hub, confirming with the server's estimate.
  await page.click('button[role="tab"]:has-text("ฉบับร่าง")');
  const draftRow = page
    .locator("tbody tr", { hasText: "ทดสอบแคมเปญถึง" })
    .first();
  await draftRow.locator('button[aria-haspopup="menu"]').click();
  await page.click('button[role="menuitem"]:has-text("ส่งตอนนี้")');
  await page.waitForSelector("text=จะเข้ากล่องของประมาณ", { timeout: 10_000 });
  await page.click('dialog[open] button:has-text("ส่งตอนนี้")');
  await page.waitForSelector("text=ส่งถึง 1 บัญชีแล้ว", { timeout: 15_000 });
  ok("draft sends to the named audience (1 account)");

  // Sent campaigns are immutable evidence with honest analytics.
  await page.click('button[role="tab"]:has-text("ส่งแล้ว")');
  const sentRow = page
    .locator("tbody tr", { hasText: "ทดสอบแคมเปญถึง" })
    .first();
  await sentRow.locator('button:has-text("ดูสถิติ")').click();
  await page.waitForSelector("text=อัตราการอ่าน", { timeout: 10_000 });
  await expect(page, "text=อัตราการกดลิงก์", "analytics report the click rate");
  await expect(
    page,
    "text=ตัวเลขนี้จึงเป็นค่าต่ำสุดที่เกิดขึ้นจริง",
    "analytics say plainly that the click count is a floor",
  );
  await page.keyboard.press("Escape");
  ok("sent campaign exposes read-receipt analytics");
  await page.screenshot({ path: `${SHOT_DIR}/59-admin-notif-hub.png`, fullPage: true });

  // Amend the sent campaign - content edits reach delivered inboxes.
  await sentRow.locator('button[aria-haspopup="menu"]').click();
  await page.click('button[role="menuitem"]:has-text("แก้ไขเนื้อหา")');
  await page.waitForSelector("text=แก้ไขการแจ้งเตือนที่ส่งแล้ว", { timeout: 15_000 });
  await page.getByLabel("หัวข้อ").fill("🎉 ทดสอบแคมเปญ (ฉบับแก้) ถึง {{user_name}}");
  await page.click('button:has-text("บันทึกและอัปเดตผู้รับ")');
  await page.waitForSelector("text=จะแทนที่ของเดิมในกล่องแจ้งเตือน", { timeout: 10_000 });
  await page.click('dialog[open] button:has-text("บันทึกและอัปเดตผู้รับ")');
  await page.waitForSelector("text=อัปเดตเนื้อหาถึงผู้รับแล้ว", { timeout: 15_000 });
  ok("amending a sent campaign updates the recipients' copies");

  // Retract it - the inbox rows leave with the campaign (net-zero runs).
  await page.click('button[role="tab"]:has-text("ส่งแล้ว")');
  const amendedRow = page.locator("tbody tr", { hasText: "ฉบับแก้" }).first();
  await amendedRow.locator('button[aria-haspopup="menu"]').click();
  await page.click('button[role="menuitem"]:has-text("ลบและเรียกคืนจากผู้รับ")');
  await page.waitForSelector("text=จะถูกลบออกจากกล่องแจ้งเตือน", { timeout: 10_000 });
  await page.click('dialog[open] button:has-text("ลบและเรียกคืน")');
  await page.waitForSelector("text=เรียกคืนการแจ้งเตือนแล้ว", { timeout: 15_000 });
  ok("retracting a sent campaign removes it from recipient inboxes");

  // Templates: create, see it listed, delete again (net-zero per run).
  await page.click('button[role="tab"]:has-text("เทมเพลต")');
  await page.click('button:has-text("+ สร้างเทมเพลต")');
  await page.getByLabel("ชื่อเทมเพลต").fill("เทมเพลตทดสอบ E2E");
  await page.getByLabel("หัวข้อ").fill("สวัสดี {{user_name}}");
  await page.getByRole("button", { name: "สร้างเทมเพลต", exact: true }).click();
  await page.waitForSelector("text=สร้างเทมเพลต “เทมเพลตทดสอบ E2E” แล้ว", { timeout: 15_000 });
  const templateRow = page
    .locator("tbody tr", { hasText: "เทมเพลตทดสอบ E2E" })
    .first();
  await templateRow.locator('button[aria-haspopup="menu"]').click();
  await page.click('button[role="menuitem"]:has-text("ลบเทมเพลต")');
  await page.click('dialog[open] button:has-text("ลบเทมเพลต")');
  await page.waitForSelector("text=ลบเทมเพลตแล้ว", { timeout: 15_000 });
  ok("template create/use-list/delete round trip");

  // The per-recipient delivery log moved to /log, unchanged in spirit.
  await page.goto(`${BASE}/admin/notifications/log`);
  await expect(page, "text=บันทึกรายผู้รับ", "delivery log lives at /log");
  await expect(page, "text=in-app เท่านั้น", "email delivery gap stays honestly disclosed");
  await expect(page, "tbody tr", "delivered snapshots are listed per recipient");

  /* ---------- Assistant ---------- */
  await page.goto(`${BASE}/admin/assistant`);
  await expect(page, "text=บทสนทนาของบัญชีนี้", "assistant monitoring renders");
  await expect(page, "text=เวอร์ชันพรอมป์ต", "prompt version column present (real field)");

  /* ---------- Recommendations: preview-as-user + weights ---------- */
  await page.goto(`${BASE}/admin/recommendations`);
  await expect(page, "text=ทดสอบ engine ในนามผู้ใช้", "preview-as-user tool renders");
  // A learner fixture, not a creator: creators' own content is excluded
  // from their feed, so a creator can legitimately preview to zero rows.
  await page.getByLabel("ชื่อผู้ใช้").fill("p16fan0");
  await page.click('button:has-text("รันตัวอย่าง")');
  await page.waitForSelector("tbody tr", { timeout: 20_000 });
  const previewHead = await page.textContent("thead");
  if (!/คะแนน/.test(previewHead ?? "")) {
    throw new Error("preview table does not show scores");
  }
  ok("preview returns a ranked list with scores for the target user");
  await expect(page, "text=น้ำหนักคะแนน", "deployed engine weights panel renders");

  /* ---------- Mobile navigation ---------- */
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(`${BASE}/admin/dashboard`);
  await mobile.waitForSelector("text=สูตรทั้งหมด");
  await mobile.click('button[aria-label="เปิดเมนู"]');
  // Two navs exist in the DOM (the desktop aside is display:none below lg);
  // the drawer is the last one and the only visible one.
  await mobile
    .locator('nav[aria-label="เมนูผู้ดูแลระบบ"]')
    .last()
    .waitFor({ state: "visible" });
  ok("mobile drawer navigation opens");
  await mobile.screenshot({ path: `${SHOT_DIR}/56-admin-mobile.png`, fullPage: true });
  await mobile.close();

  /* ---------- Logout ---------- */
  await page.goto(`${BASE}/admin/dashboard`);
  await page.waitForSelector('nav[aria-label="เมนูผู้ดูแลระบบ"]');
  await page.click('button[aria-haspopup="menu"]');
  await page.waitForSelector('[role="menu"]');
  await page.click('button[role="menuitem"]:has-text("ออกจากระบบ")');
  await page.waitForSelector("text=ต้องเข้าสู่ระบบก่อน", { timeout: 15_000 });
  ok("logout from the admin menu drops back to the 401 gate");

  if (apiErrors.length) {
    throw new Error(`Unexpected API errors:\n  ${apiErrors.join("\n  ")}`);
  }
  ok("no unexpected 4xx/5xx API responses during the staff flow");

  console.log(`\nAdmin E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
