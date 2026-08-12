/** Probe: /threads board, thread detail + legacy redirect, /qa FAQ, /support, nav + footer. */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 900 });

  /* ---- The question board at its new home ---- */
  await page.goto(`${BASE}/threads`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=กระทู้ถาม-ตอบ");
  const threadLinks = page.locator('a[href^="/threads/"]');
  const threadCount = await threadLinks.count();
  console.log("threads board rows listed:", threadCount);
  await page.screenshot({ path: "e2e-shots/66-threads-board.png", fullPage: true });

  /* ---- The board carries the numbers people choose by ---- */
  const board = await page.evaluate(() => {
    const row = document.querySelector("main li");
    if (!row) return null;
    const text = row.innerText;
    return {
      hasAnswers: text.includes("คำตอบ"),
      hasReaders: text.includes("คนอ่าน"),
      hasStatus: /รอคำตอบ|มีคำตอบที่เลือกแล้ว|ต้องการคนช่วยตอบ/.test(text),
      hasActivity: /ตอบล่าสุด|ถามเมื่อ/.test(text),
      avatars: document.querySelectorAll("main li img, main li span[aria-hidden]")
        .length,
    };
  });
  console.log("board row:", JSON.stringify(board));
  if (board && !(board.hasAnswers && board.hasReaders && board.hasStatus && board.hasActivity)) {
    throw new Error("a board row is missing its decision numbers");
  }

  /* ---- Filters narrow, and the sort is a real request ---- */
  const total = await page.locator("main li").count();
  // Wait for the request the click causes, not for a render tick: the
  // old rows are still on screen while it is in flight.
  const applied = page.waitForResponse(
    (response) =>
      response.url().includes("/qa/threads/") &&
      response.url().includes("resolved=true"),
  );
  await page.click('button:has-text("แก้แล้ว")');
  await applied;
  await page.waitForTimeout(300);
  const resolved = await page.locator("main li").count();
  console.log(`filter "แก้แล้ว": ${total} -> ${resolved} rows`);
  if (resolved > total) throw new Error("a filter widened the list");
  const resolvedAllAccepted = await page.evaluate(() =>
    [...document.querySelectorAll("main li")].every((row) =>
      row.innerText.includes("มีคำตอบที่เลือกแล้ว"),
    ),
  );
  if (!resolvedAllAccepted) throw new Error("the resolved filter let others through");

  await page.click('button:has-text("ทั้งหมด")');
  const byPopularity = page.waitForResponse(
    (response) =>
      response.url().includes("/qa/threads/") &&
      response.url().includes("ordering=popular"),
  );
  await page.selectOption('select[aria-label="เรียงกระทู้"]', "popular");
  await byPopularity;
  await page.waitForTimeout(300);
  const sorted = await page.evaluate(() =>
    [...document.querySelectorAll("main li")].map((row) => {
      const match = row.innerText.match(/(\d+)\s+คนอ่าน/);
      return match ? Number(match[1]) : 0;
    }),
  );
  console.log("readers by row, sorted by popularity:", sorted.join(", "));
  if (sorted.some((value, index) => index > 0 && value > sorted[index - 1])) {
    throw new Error("the popularity sort is not applied");
  }
  await page.selectOption('select[aria-label="เรียงกระทู้"]', "latest");
  await page.waitForTimeout(400);

  let firstThreadHref = null;
  if (threadCount > 0) {
    firstThreadHref = await threadLinks.first().getAttribute("href");
    await threadLinks.first().click();
    await page.waitForSelector("text=กลับไปหน้ากระทู้");
    await page.waitForSelector("text=คำตอบ (");
    console.log("thread detail renders: true");
    await page.screenshot({ path: "e2e-shots/67-thread-detail.png", fullPage: true });

    // Old delivered notifications link /qa/threads/{id} - must redirect.
    const legacy = `${BASE}/qa${firstThreadHref}`;
    await page.goto(legacy, { waitUntil: "networkidle" });
    await page.waitForSelector("text=กลับไปหน้ากระทู้");
    if (!page.url().includes(firstThreadHref) || page.url().includes("/qa/")) {
      throw new Error(`legacy redirect failed: ${legacy} -> ${page.url()}`);
    }
    console.log("legacy /qa/threads/{id} redirect: ok");
  }

  /* ---- /qa is now the FAQ ---- */
  await page.goto(`${BASE}/qa`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=คำถามที่พบบ่อย (FAQ)");
  const faqCount = await page.locator("details").count();
  console.log("faq entries:", faqCount);
  await page.fill('input[aria-label="ค้นหาคำถามที่พบบ่อย"]', "ลืมรหัสผ่าน");
  await page.waitForSelector("text=พบ 1 จาก");
  await page.waitForSelector("text=ทีมงานจะส่งลิงก์ตั้งรหัสผ่านใหม่");
  console.log("faq search narrows and opens the match: ok");
  await page.fill('input[aria-label="ค้นหาคำถามที่พบบ่อย"]', "");
  await page.screenshot({ path: "e2e-shots/68-faq.png", fullPage: true });

  /* ---- Support links to both help surfaces ---- */
  await page.goto(`${BASE}/support`);
  await page.waitForSelector("text=ศูนย์ช่วยเหลือและติดต่อเรา");
  console.log(
    "support channels (faq, board, mailto):",
    await page.locator("text=ไปที่คำถามที่พบบ่อย").count(),
    await page.locator("text=ไปที่กระทู้ถาม-ตอบ").count(),
    await page.locator('a[href^="mailto:"]').count(),
  );
  await page.screenshot({ path: "e2e-shots/69-support.png", fullPage: true });

  /* ---- Nav has the new tab; footer splits FAQ vs board ---- */
  const navTab = page.locator('header nav a[href="/threads"]');
  if ((await navTab.count()) === 0) throw new Error("nav tab /threads missing");
  console.log("nav tab กระทู้ถาม-ตอบ: present");

  const footer = page.locator("footer");
  for (const label of [
    "กระทู้ถาม-ตอบ",
    "คำถามที่พบบ่อย (FAQ)",
    "ศูนย์ช่วยเหลือ / ติดต่อเรา",
    "ข้อตกลงการใช้งาน",
    "นโยบายความเป็นส่วนตัว",
    "นโยบายคุกกี้",
  ]) {
    const count = await footer.locator(`a:has-text("${label}")`).count();
    if (!count) throw new Error(`footer missing: ${label}`);
  }
  console.log("footer help links: all present");

  // The six-tab nav must not overflow at the lg breakpoint.
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  const overflow = await page.evaluate(() => {
    const header = document.querySelector("header > div");
    return header ? header.scrollWidth - header.clientWidth : -1;
  });
  console.log("header overflow px at 1024:", overflow);
  await page.screenshot({ path: "e2e-shots/70-nav-1024.png" });
  if (overflow > 0) throw new Error(`nav overflows at 1024px by ${overflow}px`);

  console.log("probe done");
} finally {
  await browser.close();
}
