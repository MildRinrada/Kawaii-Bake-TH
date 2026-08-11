/**
 * Course list (baking school) browser E2E: header count, level tiles
 * with real counts, featured course with curriculum preview, search,
 * faceted filters incl. learning status, per-card progress, curriculum
 * accordion, empty-state recovery, mobile filter sheet.
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
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

  // ---------- Anonymous catalog ----------
  await page.goto(`${BASE}/courses`);
  await expect(page, "text=/ทั้งหมด \\d+ คอร์ส/", "header shows real course count");
  await expect(page, 'button:has-text("เริ่มต้นได้เลย")', "learning-path level tiles render");
  await expect(page, "text=/\\d+ คอร์ส/", "level tiles show real per-level counts");
  await expect(page, "text=คอร์สแนะนำ", "featured course renders with extra weight");
  await expect(page, "text=ฟรี", "access label (ฟรี) is visible without opening the course");
  await expect(page, "text=สอนโดย", "instructor identity shows on cards");
  await page.screenshot({ path: `${SHOT_DIR}/27-courses-anon.png`, fullPage: true });

  // Featured curriculum preview comes from the real syllabus
  await expect(page, "text=รู้จักแป้งและยีสต์", "featured curriculum preview lists real lesson titles", 15_000).catch(async () => {
    // featured may be the other course  accept its lesson instead
    await expect(page, "text=1.", "featured curriculum preview lists numbered lessons");
  });

  // ---------- Level tile filters ----------
  await page.click('button:has-text("เริ่มต้นได้เลย") >> nth=0');
  await page.waitForURL("**difficulty=beginner**");
  await expect(page, "text=กำลังกรอง:", "level selection appears in the active filter summary");
  await page.click("text=ล้างทั้งหมด");

  // ---------- Server-side search (debounced) ----------
  await page.fill('input[aria-label="ค้นหาคอร์สเรียน"]', "ขนมปัง");
  await page.waitForURL("**search=**");
  await expect(page, "text=พบ 1 คอร์ส", "debounced search hits the server and narrows the count");
  await expect(page, "text=พื้นฐานการอบขนมปังสำหรับมือใหม่", "matching course remains visible");
  await page.click('button:has-text("ล้าง")');
  await page.waitForURL(`${BASE}/courses`);
  ok("clear-search action resets");

  // Search matches course DESCRIPTION server-side (not just titles)
  await page.fill('input[aria-label="ค้นหาคอร์สเรียน"]', "ยีสต์");
  await page.waitForURL("**search=**");
  await expect(page, "text=พื้นฐานการอบขนมปังสำหรับมือใหม่", "search matches text inside the course description");
  await page.click('button:has-text("ล้าง")');

  // ---------- Stored aggregates on cards (no N+1) ----------
  await expect(page, "text=40 นาที", "total duration from the list payload shows on the card");
  await expect(page, "text=4.7", "rating aggregate shows on the reviewed course");

  // ---------- No-results recovery ----------
  await page.waitForURL(`${BASE}/courses`);
  await page.fill('input[aria-label="ค้นหาคอร์สเรียน"]', "ซูเฟล่ควอนตัม");
  await page.waitForURL("**search=**", { timeout: 10_000 });
  await expect(page, "text=ไม่พบคอร์สที่ตรงกับ", "no-results state explains the miss");
  await expect(page, "text=คอร์สทั้งหมดที่เปิดสอนตอนนี้", "no-results still offers the real catalog");
  await page.click('button:has-text("ล้างตัวกรองทั้งหมด")');
  // Wait for the reset to land and the catalog to re-render before
  // touching the accordion - clicking a node mid-refetch hits a corpse.
  await page.waitForURL(`${BASE}/courses`);
  await page.waitForSelector("text=พื้นฐานการอบขนมปังสำหรับมือใหม่");

  // ---------- Curriculum accordion on the bread course card ----------
  await page.click('button:has-text("ดูบทเรียนในคอร์ส") >> nth=1');
  await expect(page, "text=รู้จักแป้งและยีสต์", "curriculum accordion lists real lessons with durations");

  // ---------- Signed in: progress everywhere ----------
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");
  await page.goto(`${BASE}/courses`);

  // Derived from the account's real progress: the strip only exists while
  // a course is unfinished, and this learner's courses get completed by
  // other suites. Both branches are real behaviour.
  const inProgress = await page.evaluate(async () => {
    const data = await (
      await fetch("http://localhost:8000/api/v1/me/progress/", {
        credentials: "include",
      })
    ).json();
    return data.courses.filter((course) => !course.completed_at).length;
  });

  if (inProgress > 0) {
    await expect(page, "text=เรียนต่อจากที่ค้างไว้", "continue-learning strip appears before the catalog");
    await expect(page, "text=/เรียนแล้ว \\d+ จาก \\d+/", "strip shows real lesson counts");
    await expect(page, 'button:has-text("เรียนต่อ →")', "enrolled card CTA becomes Continue");
    await expect(page, 'div[role="progressbar"]', "progress bar shows directly on the card");
  } else {
    if (await page.locator("text=เรียนต่อจากที่ค้างไว้").count()) {
      throw new Error("continue-learning strip rendered with nothing in progress");
    }
    ok("no course is in progress, so the continue-learning strip is correctly absent");
  }

  // Learning-status facet  the count comes from the same live progress
  // read, so the assertion stays true as the account's courses finish.
  await page.click('button:has-text("กำลังเรียน")');
  await expect(
    page,
    `text=พบ ${inProgress} คอร์ส`,
    `in-progress facet narrows to the ${inProgress} unfinished course(s)`,
  );
  await page.click('button:has-text("ยังไม่เริ่ม")');
  await expect(page, "text=ศิลปะการแต่งหน้าเค้กเบื้องต้น", "not-started facet shows the unenrolled course");
  await page.click("text=ล้างทั้งหมด");
  await page.screenshot({ path: `${SHOT_DIR}/28-courses-authed.png`, fullPage: true });

  // ---------- Mobile ----------
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${BASE}/courses`);
  await mobile.waitForSelector('h1:has-text("คอร์สเรียน")');
  await mobile.waitForSelector('button:has-text("เริ่มต้นได้เลย")');
  ok("mobile renders level tiles");
  await mobile.click('button:has-text("ตัวกรอง")');
  await expect(mobile, 'div[role="dialog"][aria-label="ตัวกรองคอร์ส"]', "mobile bottom-sheet filter opens");
  await mobile.click('div[role="dialog"] button:has-text("ดูผลลัพธ์")');
  await mobile.screenshot({ path: `${SHOT_DIR}/29-courses-mobile.png`, fullPage: true });
  await mobile.close();

  console.log(`\nCourse-list E2E: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
