/**
 * Admin recipe create/edit E2E — a full round trip against the real API:
 * create a draft → verify it exists via the list → edit every kind of
 * field (scalars, categories, ingredient rows, step rows + reorder) →
 * confirm the changes came back from the server → delete it again, so
 * the script leaves no residue and can be re-run.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const STAFF = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };
const TITLE = `สูตรทดสอบผู้ดูแล ${Date.now() % 100000}`;

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
let createdSlug = null;
try {
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
  await page.fill('input[type="email"]', STAFF.email);
  await page.fill('input[type="password"]', STAFF.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  /* ---------- Reach the form from the list ---------- */
  await page.goto(`${BASE}/admin/recipes`);
  await expect(page, 'a[href="/admin/recipes/new"]', "list page offers a create button");
  await page.click('a[href="/admin/recipes/new"]');
  await page.waitForURL("**/admin/recipes/new");
  await expect(page, "text=ข้อมูลหลัก", "create form renders");
  await expect(page, "text=ความพร้อมก่อนเผยแพร่", "publish-readiness checklist renders");

  /* ---------- Fill it in ---------- */
  await page.fill('input[aria-label="ชื่อวัตถุดิบรายการที่ 1"]', "แป้งเค้ก");
  await page.fill('input[aria-label="ปริมาณรายการที่ 1"]', "250");
  await page.selectOption('select[aria-label="หน่วยรายการที่ 1"]', "g");
  await page.click('button:has-text("+ เพิ่มวัตถุดิบ")');
  await page.fill('input[aria-label="ชื่อวัตถุดิบรายการที่ 2"]', "น้ำตาลทราย");
  await page.fill('input[aria-label="ปริมาณรายการที่ 2"]', "120");
  await page.selectOption('select[aria-label="หน่วยรายการที่ 2"]', "g");

  await page.fill('textarea[aria-label="เนื้อหาขั้นตอนที่ 1"]', "ร่อนแป้งแล้วพักไว้");
  await page.click('button:has-text("+ เพิ่มขั้นตอน")');
  await page.fill('textarea[aria-label="เนื้อหาขั้นตอนที่ 2"]', "อบที่ 170 องศา 25 นาที");

  // Title/summary live in labelled Field wrappers.
  const titleInput = page.locator("form input").first();
  await titleInput.fill(TITLE);
  await page.locator("form textarea").first().fill("สูตรสำหรับทดสอบระบบผู้ดูแล");

  // One category chip.
  await page.locator('button[aria-pressed="false"]').first().click();
  ok("form accepts scalars, categories, ingredient rows and step rows");
  await page.screenshot({ path: `${SHOT_DIR}/58-admin-recipe-new.png`, fullPage: true });

  /* ---------- Create ---------- */
  await page.click('button[type="submit"]:has-text("สร้างเป็นฉบับร่าง")');
  await expect(page, "text=สร้างสูตรใหม่เป็นฉบับร่างแล้ว", "POST /recipes/ created the draft");
  await page.waitForURL("**/admin/recipes/**/edit", { timeout: 15_000 });
  createdSlug = decodeURIComponent(
    page.url().split("/admin/recipes/")[1].replace("/edit", ""),
  );
  ok(`redirected to the edit page of the new recipe (${createdSlug})`);

  /* ---------- It really exists in the list ---------- */
  await page.goto(`${BASE}/admin/recipes`);
  await page.fill('input[aria-label="ค้นหาสูตร"]', TITLE);
  await page.waitForTimeout(1000);
  await expect(page, `text=${TITLE}`, "the new recipe is returned by the server-side list");
  await expect(page, "text=ฉบับร่าง", "it was created as a DRAFT, as the backend dictates");

  /* ---------- Edit ---------- */
  await page.goto(`${BASE}/admin/recipes/${encodeURIComponent(createdSlug)}/edit`);
  await expect(page, "text=แก้ไขสูตร", "edit page loads the existing recipe");
  const loadedIngredient = await page
    .locator('input[aria-label="ชื่อวัตถุดิบรายการที่ 2"]')
    .inputValue();
  if (loadedIngredient !== "น้ำตาลทราย") {
    throw new Error(`ingredient rows did not round-trip: got "${loadedIngredient}"`);
  }
  ok("existing ingredient rows are loaded back into the form");

  const loadedStep = await page
    .locator('textarea[aria-label="เนื้อหาขั้นตอนที่ 2"]')
    .inputValue();
  if (!loadedStep.includes("170")) {
    throw new Error(`step rows did not round-trip: got "${loadedStep}"`);
  }
  ok("existing step rows are loaded back into the form");

  // Change a scalar, add an ingredient, reorder the steps.
  await page.locator("form textarea").first().fill("แก้ไขคำโปรยแล้ว");
  await page.click('button:has-text("+ เพิ่มวัตถุดิบ")');
  await page.fill('input[aria-label="ชื่อวัตถุดิบรายการที่ 3"]', "เนยจืด");
  await page.fill('input[aria-label="ปริมาณรายการที่ 3"]', "80");
  await page.click('button[aria-label="เลื่อนขั้นตอนที่ 2 ขึ้น"]');
  await page.click('button[type="submit"]:has-text("บันทึกการแก้ไข")');
  await expect(page, "text=บันทึกการแก้ไขแล้ว", "PATCH /recipes/{slug}/ saved the edit");

  /* ---------- Verify the edit came back from the server ---------- */
  await page.reload();
  await page.waitForSelector("text=แก้ไขสูตร");
  const summaryAfter = await page.locator("form textarea").first().inputValue();
  if (summaryAfter !== "แก้ไขคำโปรยแล้ว") {
    throw new Error(`summary did not persist: "${summaryAfter}"`);
  }
  ok("edited summary persisted server-side");

  const thirdIngredient = await page
    .locator('input[aria-label="ชื่อวัตถุดิบรายการที่ 3"]')
    .inputValue();
  if (thirdIngredient !== "เนยจืด") {
    throw new Error(`added ingredient did not persist: "${thirdIngredient}"`);
  }
  ok("added ingredient persisted (collection replace worked)");

  const firstStep = await page
    .locator('textarea[aria-label="เนื้อหาขั้นตอนที่ 1"]')
    .inputValue();
  if (!firstStep.includes("170")) {
    throw new Error(`step reorder did not persist: first step is "${firstStep}"`);
  }
  ok("step reorder persisted server-side");

  /* ---------- Cover image: the separate multipart PATCH ---------- */
  const PNG_1X1 =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
  await page.setInputFiles('input[aria-label="เลือกรูปหน้าปก"]', {
    name: "cover.png",
    mimeType: "image/png",
    buffer: Buffer.from(PNG_1X1, "base64"),
  });
  await page.click('button[type="submit"]:has-text("บันทึกการแก้ไข")');
  await expect(page, "text=บันทึกการแก้ไขแล้ว", "cover image saved via the multipart PATCH");
  await page.reload();
  await page.waitForSelector("text=แก้ไขสูตร");
  const cover = page.locator('img[src*="localhost:8000"]').first();
  await cover.waitFor({ state: "visible", timeout: 15_000 });
  ok("cover image persisted and is served back from the API origin");
  await page.screenshot({ path: `${SHOT_DIR}/59-admin-recipe-edit.png`, fullPage: true });

  /* ---------- Validation error surfaces ---------- */
  await page.locator("form input").first().fill("ก");
  await page.click('button[type="submit"]:has-text("บันทึกการแก้ไข")');
  await expect(page, '[role="alert"]', "backend validation error is surfaced on the form");
  await page.locator("form input").first().fill(TITLE);

  /* ---------- Delete (confirm dialog + real DELETE) ---------- */
  await page.click('button:has-text("ลบสูตรนี้ถาวร")');
  await expect(page, "text=ลบสูตรนี้ถาวร?", "delete asks for confirmation");
  await page.locator('dialog[open] button:has-text("ลบถาวร")').click();
  await page.waitForURL("**/admin/recipes", { timeout: 15_000 });
  ok("DELETE /recipes/{slug}/ removed the recipe and returned to the list");
  createdSlug = null;

  const expected400 = apiErrors.filter(
    (line) => line.startsWith("400 PATCH") && line.includes("/recipes/"),
  );
  const unexpected = apiErrors.filter((line) => !expected400.includes(line));
  if (expected400.length !== 1) {
    throw new Error(
      `expected exactly one deliberate 400 from the short-title save, saw ${expected400.length}`,
    );
  }
  ok("the only 4xx was the deliberate validation test");
  if (unexpected.length) {
    throw new Error(`Unexpected API errors:\n  ${unexpected.join("\n  ")}`);
  }
  ok("no other unexpected 4xx/5xx API responses");

  console.log(`\nAdmin recipe CRUD E2E: ${passed}/${passed} passed`);
} finally {
  if (createdSlug) {
    console.log(`\n!! leftover recipe not deleted: ${createdSlug}`);
  }
  await browser.close();
}
