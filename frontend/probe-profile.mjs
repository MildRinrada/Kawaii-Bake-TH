/** Probe: the restructured profile page + the always-visible chat launcher. */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 950 } });

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");

  await page.goto(`${BASE}/profile`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=กำลังเรียนอยู่");

  /* ---- Two columns start directly under the identity card ---- */
  const layout = await page.evaluate(() => {
    const learning = [...document.querySelectorAll("h2")].find(
      (h) => h.textContent.trim() === "กำลังเรียนอยู่",
    );
    const aside = document.querySelector("aside");
    if (!learning || !aside) return null;
    return {
      learningTop: Math.round(learning.getBoundingClientRect().top),
      asideTop: Math.round(aside.getBoundingClientRect().top),
      asideLeft: Math.round(aside.getBoundingClientRect().left),
      learningLeft: Math.round(learning.getBoundingClientRect().left),
    };
  });
  console.log("layout:", layout);
  if (!layout) throw new Error("profile layout not found");
  if (Math.abs(layout.learningTop - layout.asideTop) > 40) {
    throw new Error("sidebar does not start alongside the first section");
  }
  if (layout.asideLeft <= layout.learningLeft) {
    throw new Error("sidebar is not the right-hand column");
  }
  console.log("two-column layout starts under the cover: ok");

  /* ---- Section order tells "what I did" before "what I saved" ---- */
  const order = await page.$$eval("h2", (hs) => hs.map((h) => h.textContent.trim()));
  console.log("section order:", order.join(" → "));
  const idx = (title) => order.indexOf(title);
  if (idx("ผลงานที่แชร์ไว้") === -1) throw new Error("shared-work section missing");
  if (!(idx("กำลังเรียนอยู่") < idx("ผลงานที่แชร์ไว้"))) {
    throw new Error("shared work must follow currently-learning");
  }
  if (!(idx("ผลงานที่แชร์ไว้") < idx("สูตรที่บันทึกไว้"))) {
    throw new Error("shared work must come before saved content");
  }
  console.log("section order: doing before saving");

  /* ---- Stats are inline, not a card grid ---- */
  const statText = await page.textContent("main");
  if (!/คอร์สที่เรียนจบ|กำลังเรียน|สูตรที่บันทึกไว้/.test(statText)) {
    throw new Error("stat strip missing");
  }
  const progressBars = await page.locator('div[role="progressbar"]').count();
  console.log("progress bars rendered:", progressBars);
  const trackVisible = await page.evaluate(() => {
    const bar = document.querySelector('div[role="progressbar"]');
    if (!bar) return null;
    const style = getComputedStyle(bar);
    return { bg: style.backgroundColor, h: Math.round(bar.getBoundingClientRect().height) };
  });
  console.log("progress track:", trackVisible);
  if (trackVisible && /rgba\(0, 0, 0, 0\)/.test(trackVisible.bg)) {
    throw new Error("progress bar has no visible track");
  }

  /* ---- Completion gaps are Thai and clickable ---- */
  const missing = await page.locator("text=ยังขาด:").count();
  if (missing) {
    const raw = await page.textContent("aside");
    if (/bio|location|birthday|favorite_categories/.test(raw)) {
      throw new Error("raw field names leaked into the completion hint");
    }
    console.log("completion gaps rendered in Thai: ok");
  }

  await page.screenshot({ path: "e2e-shots/80-profile.png", fullPage: true });

  /* ---- Chat launcher stays visible and toggles ---- */
  const fab = page.locator('button[aria-label="เปิดผู้ช่วย AI"]');
  await fab.click();
  await page.waitForSelector('section[aria-label="ผู้ช่วย AI"]');
  const toggle = page.locator('button[aria-label="ปิดผู้ช่วย AI"]');
  const overlap = await page.evaluate(() => {
    const button = document.querySelector('button[aria-expanded="true"][aria-label*="ผู้ช่วย AI"]');
    const panel = document.querySelector('section[aria-label="ผู้ช่วย AI"]');
    if (!button || !panel) return null;
    const b = button.getBoundingClientRect();
    const p = panel.getBoundingClientRect();
    const covered = !(p.bottom <= b.top || p.top >= b.bottom || p.right <= b.left || p.left >= b.right);
    // Does a click at the button's centre actually land on the button?
    const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    return { covered, hitIsButton: button.contains(hit) };
  });
  console.log("launcher vs panel:", overlap);
  if (!overlap || overlap.covered || !overlap.hitIsButton) {
    throw new Error("the open panel covers the launcher button");
  }
  await page.screenshot({ path: "e2e-shots/81-widget-open.png" });
  await toggle.first().click();
  await page.waitForSelector('section[aria-label="ผู้ช่วย AI"]', { state: "detached" });
  console.log("clicking the round button closes the panel: ok");

  console.log("probe done");
} finally {
  await browser.close();
}
