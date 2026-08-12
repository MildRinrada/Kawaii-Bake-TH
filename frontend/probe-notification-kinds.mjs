/**
 * Probe: announcement kinds reach the reader, and clicks are counted.
 *
 * Two things the design review asked for, checked end to end against the
 * real backend rather than by reading the code:
 *
 * 1. A staff announcement's **kind** picks the glyph and the colour the
 *    recipient sees - so two announcements of different kinds must not
 *    look identical, which is exactly what they did when every one of
 *    them was the same lavender pin.
 * 2. Following a notification's link is **recorded**, and the campaign's
 *    analytics report it.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const API = process.env.API_BASE_URL ?? "http://localhost:8000/api/v1";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const STAFF = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };
const READER = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };
const SIGNIN = 'form[aria-label="เข้าสู่ระบบ"]';
const STAMP = Date.now().toString(36);

let passed = 0;
const ok = (label) => console.log(`  ok ${String(++passed).padStart(2, "0")}  ${label}`);

async function signIn(page, { email, password }) {
  await page.goto(`${BASE}/login`);
  await page.fill(`${SIGNIN} input[type="email"]`, email);
  await page.fill(`${SIGNIN} input[type="password"]`, password);
  await page.click(`${SIGNIN} button[type="submit"]`);
  // The form replaces the URL once the session exists; the header differs
  // between a learner and a staff account, so the URL is the signal.
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), {
    timeout: 15_000,
  });
}

/** Drive the admin API from the signed-in page (cookies + CSRF included). */
function callApi(page, api) {
  return async (method, path, body) =>
    page.evaluate(
      async ({ api, method, path, body }) => {
        const csrf =
          document.cookie
            .split("; ")
            .find((part) => part.startsWith("csrftoken="))
            ?.slice("csrftoken=".length) ?? "";
        const response = await fetch(`${api}${path}`, {
          method,
          credentials: "include",
          headers: {
            "X-CSRFToken": csrf,
            "Content-Type": "application/json",
          },
          body: body ? JSON.stringify(body) : undefined,
        });
        return { status: response.status, body: await response.json().catch(() => null) };
      },
      { api, method, path, body },
    );
}

const browser = await chromium.launch();
try {
  const staffPage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await signIn(staffPage, STAFF);
  const api = callApi(staffPage, API);
  await staffPage.evaluate(
    (base) => fetch(`${base}/auth/csrf/`, { credentials: "include" }),
    API,
  );

  /* ---- An unknown kind is not a kind ---- */
  const refused = await api("POST", "/admin/notifications/campaigns/", {
    kind: "post_viral",
    title: `ทดสอบชนิดผิด ${STAMP}`,
    link: "/community",
    audience: { kind: "specific_users", usernames: ["mildbakes"] },
  });
  if (refused.status !== 400) {
    throw new Error(`a free-form kind was accepted (${refused.status})`);
  }
  ok("an unknown kind is refused (the set is closed server-side)");

  /* ---- Send two announcements of different kinds ---- */
  const sent = [];
  for (const [kind, title] of [
    ["maintenance", `ระบบจะปิดปรับปรุงคืนนี้ ${STAMP}`],
    ["feature", `มีโหมดทำขนมใหม่แล้ว ${STAMP}`],
  ]) {
    const created = await api("POST", "/admin/notifications/campaigns/", {
      kind,
      title,
      body: "ทดสอบจาก probe",
      link: "/recipes",
      audience: { kind: "specific_users", usernames: ["mildbakes"] },
    });
    if (created.status !== 201) {
      throw new Error(`campaign create failed: ${JSON.stringify(created)}`);
    }
    const delivered = await api(
      "POST",
      `/admin/notifications/campaigns/${created.body.id}/send/`,
    );
    if (delivered.status !== 200) {
      throw new Error(`send failed: ${JSON.stringify(delivered)}`);
    }
    sent.push({ id: created.body.id, kind, title });
  }
  ok(`sent two announcements (${sent.map((row) => row.kind).join(", ")})`);

  /* ---- The reader sees two different drawings ---- */
  const readerPage = await browser.newPage({ viewport: { width: 1360, height: 950 } });
  await signIn(readerPage, READER);
  await readerPage.goto(`${BASE}/notifications`, { waitUntil: "networkidle" });

  const drawn = await readerPage.evaluate((stamp) => {
    const rows = [...document.querySelectorAll("li")].filter((li) =>
      li.innerText.includes(stamp),
    );
    return rows.map((li) => {
      const bubble = li.querySelector("span[aria-hidden]");
      const badge = [...li.querySelectorAll("span")].find((node) =>
        /ปิดปรับปรุงระบบ|ฟีเจอร์ใหม่|ประกาศจากทีมงาน|กิจกรรม|นโยบาย|แจ้งเตือนสำคัญ/.test(
          node.textContent.trim(),
        ),
      );
      const style = bubble ? getComputedStyle(bubble) : null;
      return {
        title: li.innerText.split("\n")[0].slice(0, 40),
        badge: badge?.textContent.trim() ?? null,
        background: style?.backgroundColor ?? null,
        glyph: bubble?.querySelector("span")?.style.maskImage ?? "",
      };
    });
  }, STAMP);

  console.log("     rows:", JSON.stringify(drawn));
  if (drawn.length !== 2) {
    throw new Error(`expected 2 announcement rows, found ${drawn.length}`);
  }
  const [first, second] = drawn;
  if (first.background === second.background) {
    throw new Error("both kinds are drawn in the same colour");
  }
  if (first.glyph === second.glyph) {
    throw new Error("both kinds are drawn with the same glyph");
  }
  if (!first.badge || !second.badge || first.badge === second.badge) {
    throw new Error(`badges do not name the kind (${first.badge}/${second.badge})`);
  }
  ok(`two kinds, two colours, two glyphs (${first.badge} vs ${second.badge})`);
  await readerPage.screenshot({
    path: `${SHOT_DIR}/92-notification-kinds.png`,
    fullPage: false,
  });

  /* ---- Following the link is recorded ---- */
  const target = readerPage
    .locator("li", { hasText: sent[1].title })
    .locator('a[href="/recipes"]')
    .first();
  await target.click();
  await readerPage.waitForURL("**/recipes**", { timeout: 15_000 });
  ok("the row navigates to its link");

  // The click is reported as the page navigates; give it a moment to land.
  await readerPage.waitForTimeout(1500);
  const analytics = await api(
    "GET",
    `/admin/notifications/campaigns/${sent[1].id}/analytics/`,
  );
  console.log("     analytics:", JSON.stringify(analytics.body));
  if (analytics.body.clicked !== 1) {
    throw new Error(`click was not recorded (${JSON.stringify(analytics.body)})`);
  }
  if (analytics.body.read !== 1) {
    throw new Error("a click did not imply a read");
  }
  if (Math.abs(analytics.body.click_rate - 1) > 0.001) {
    throw new Error(`click_rate is ${analytics.body.click_rate}, expected 1`);
  }
  ok("the click reaches the campaign's analytics (clicked 1, rate 100%)");

  /* ---- The other campaign, unread, stays at zero ---- */
  const untouched = await api(
    "GET",
    `/admin/notifications/campaigns/${sent[0].id}/analytics/`,
  );
  if (untouched.body.clicked !== 0) {
    throw new Error("clicks leaked between campaigns");
  }
  ok("an untouched campaign still reports zero clicks");

  /* ---- Clean up: retract both sends ---- */
  for (const row of sent) {
    await api("DELETE", `/admin/notifications/campaigns/${row.id}/`);
  }
  ok("probe campaigns retracted (inboxes left as they were)");

  console.log(`\nNotification-kind probe: ${passed}/${passed} passed`);
} finally {
  await browser.close();
}
