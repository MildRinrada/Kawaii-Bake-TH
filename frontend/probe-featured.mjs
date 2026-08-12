/** Probe: featured course covers share one aspect ratio; widget button look. */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 900 });

  const measure = async (url, label) => {
    await page.goto(`${BASE}${url}`, { waitUntil: "networkidle" });
    // Both pages only mount a featured cover once the catalogue is big
    // enough; absence is a state to report, not a failure to wait for.
    await page
      .waitForSelector('[class*="md:w-1/2"]', { timeout: 3000 })
      .catch(() => null);
    const box = await page.evaluate(() => {
      const el = [...document.querySelectorAll("a,div")].find(
        (node) =>
          typeof node.className === "string" &&
          node.className.includes("md:w-1/2") &&
          node.className.includes("aspect-video"),
      );
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return {
        w: Math.round(rect.width),
        h: Math.round(rect.height),
        ratio: +(rect.width / rect.height).toFixed(3),
      };
    });
    console.log(label, box);
    return box;
  };

  // Home only mounts its featured card at >=4 courses (below that it
  // falls back to a plain fluid grid), so a missing cover there is a
  // valid state, not a failure.
  const home = await measure("/", "home featured:");
  const courses = await measure("/courses", "/courses featured:");
  if (!courses) {
    console.log("/courses shows the small-catalogue fallback - nothing to compare");
  }
  if (!home) {
    console.log("home shows the <4-courses fluid fallback - nothing to compare");
  } else if (Math.abs(home.ratio - courses.ratio) > 0.01) {
    throw new Error(`ratios differ: home ${home.ratio} vs courses ${courses.ratio}`);
  } else {
    console.log("featured ratios equal:", home.ratio);
  }

  /* ---- Widget button (authenticated) ---- */
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "p16-learner@example.com");
  await page.fill('input[type="password"]', "Rhubarb!Tart2024");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=MildBakes");
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForSelector('button[aria-label="เปิดผู้ช่วย AI"]');
  await page.screenshot({
    path: "e2e-shots/75-widget-button.png",
    clip: { x: 1280 - 220, y: 900 - 220, width: 220, height: 220 },
  });
  console.log("widget button screenshot saved");
} finally {
  await browser.close();
}
