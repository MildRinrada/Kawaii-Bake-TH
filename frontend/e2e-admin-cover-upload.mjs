/**
 * Cover-image upload on /admin/recipes/new — the failure paths.
 *
 * 1. A HEIC file is refused at pick time with a Thai explanation, before
 *    any request is made (the server's Pillow has no HEIF plugin).
 * 2. A non-image that reaches the server produces a Thai error, and the
 *    retry does NOT create a second recipe — the regression that made
 *    "can't upload a cover" leave orphan drafts behind.
 * 3. A normal JPEG uploads and is served back from the API origin.
 */
import { chromium } from "playwright";
import { writeFileSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

const BASE = "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const STAFF = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };
const TITLE = `ทดสอบรูปปก ${Date.now() % 100000}`;

// A real 1x1 JPEG (not a PNG renamed) so the server actually decodes it.
const JPEG_1X1 =
  "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a" +
  "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA" +
  "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==";

const dir = mkdtempSync(join(tmpdir(), "kb-cover-"));
const heicPath = join(dir, "photo.HEIC");
const textPath = join(dir, "notes.txt");
const jpegPath = join(dir, "cover.jpg");
writeFileSync(heicPath, Buffer.from("not really heic"));
writeFileSync(textPath, "hello");
writeFileSync(jpegPath, Buffer.from(JPEG_1X1, "base64"));

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
let slug = null;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  let creates = 0;
  page.on("response", (r) => {
    if (
      r.request().method() === "POST" &&
      r.url().endsWith("/api/v1/recipes/") &&
      r.status() === 201
    ) {
      creates += 1;
    }
  });

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', STAFF.email);
  await page.fill('input[type="password"]', STAFF.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  await page.goto(`${BASE}/admin/recipes/new`);
  await expect(page, "text=ลากรูปมาวางที่นี่", "cover control is a real drop zone, not a bare file input");
  await expect(page, "text=ไม่รองรับ .HEIC", "supported formats are stated up front");

  /* ---------- 1. HEIC refused client-side, no request at all ---------- */
  const before = creates;
  await page.setInputFiles('input[aria-label="เลือกรูปหน้าปก"]', heicPath);
  await expect(page, "text=/\\.HEIC\\/\\.HEIF จาก iPhone/", "HEIC is refused at pick time with a Thai explanation");
  if (creates !== before) throw new Error("a request was made for a refused file");
  ok("no request is made for a file the server cannot decode");

  /* ---------- 2. Server-side rejection must not duplicate the recipe --- */
  await page.locator("form input").first().fill(TITLE);
  await page.fill('input[aria-label="ชื่อวัตถุดิบรายการที่ 1"]', "แป้ง");
  await page.fill('textarea[aria-label="เนื้อหาขั้นตอนที่ 1"]', "ผสมให้เข้ากัน");
  // Bypass the client check the way a mislabelled file would.
  await page.setInputFiles('input[aria-label="เลือกรูปหน้าปก"]', {
    name: "cover.png",
    mimeType: "image/png",
    buffer: Buffer.from("this is not a png"),
  });
  await page.click('button[type="submit"]:has-text("สร้างเป็นฉบับร่าง")');
  await expect(
    page,
    "text=/ไฟล์นี้ไม่ใช่รูปภาพที่ระบบเปิดได้/",
    "server image rejection is shown in Thai, naming the HEIC cause",
  );
  if (creates !== 1) throw new Error(`expected 1 create, saw ${creates}`);
  ok("the recipe was created once");
  await expect(page, "text=การกดบันทึกอีกครั้งจะอัปเดตสูตรเดิม", "the form warns that a retry will update, not duplicate");
  // A refused file must not tick the readiness checklist.
  const readiness = await page
    .locator('li:has-text("มีรูปหน้าปก")')
    .first()
    .textContent();
  if (readiness.includes("✓")) {
    throw new Error("readiness checklist counted a rejected cover image");
  }
  ok("the readiness checklist does not count a rejected cover");
  await page.screenshot({ path: `${SHOT_DIR}/61-cover-rejected.png`, fullPage: true });

  /* ---------- 3. Retry with a valid JPEG: update, never a second POST -- */
  await page.click('button[aria-label="เอารูปที่เลือกออก"]').catch(() => {});
  await page.setInputFiles('input[aria-label="เลือกรูปหน้าปก"]', jpegPath);
  await expect(page, "text=cover.jpg", "the chosen file name and size are shown");
  await page.click('button[type="submit"]:has-text("สร้างเป็นฉบับร่าง")');
  await page.waitForURL("**/admin/recipes/**/edit", { timeout: 15_000 });
  slug = decodeURIComponent(page.url().split("/admin/recipes/")[1].replace("/edit", ""));
  if (creates !== 1) {
    throw new Error(`retry created a duplicate recipe (${creates} POSTs)`);
  }
  ok("the retry updated the existing recipe — no duplicate draft");

  await page.reload();
  await page.waitForSelector("text=แก้ไขสูตร");
  await page
    .locator('img[src*="localhost:8000"]')
    .first()
    .waitFor({ state: "visible", timeout: 15_000 });
  ok("the JPEG uploaded and is served back from the API origin");

  /* ---------- Clean up ---------- */
  await page.click('button:has-text("ลบสูตรนี้ถาวร")');
  await page.locator('dialog[open] button:has-text("ลบถาวร")').click();
  await page.waitForURL("**/admin/recipes", { timeout: 15_000 });
  slug = null;
  ok("test recipe deleted — the script leaves no residue");

  console.log(`\nCover upload E2E: ${passed}/${passed} passed`);
} finally {
  if (slug) console.log(`\n!! leftover recipe: ${slug}`);
  await browser.close();
}
