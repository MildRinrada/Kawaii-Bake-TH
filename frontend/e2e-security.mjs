/**
 * Security monitoring E2E.
 *
 * Drives the whole loop against the real stack: fire genuine probes at
 * Django, confirm the middleware scored them, then read and act on them
 * through `/admin/security` as a staff user.
 *
 * **Fixture ownership.** Every probe is sent with
 * `X-Forwarded-For: 203.0.113.99` (a TEST-NET-3 address, reserved for
 * documentation and guaranteed not to be anyone). All the data this test
 * creates therefore lands on one profile, which the script deletes at the
 * end  it never touches events the real dev traffic produced.
 *
 * Requires Django started with `SECURITY_TRUSTED_IPS=""`; the shipped
 * default trusts 127.0.0.1, which would (correctly) make every probe from
 * this machine unscored.
 *
 * The scanner probe uses `nikto` rather than `sqlmap`: endpoint-protection
 * software on this workstation severs any connection whose user agent
 * contains "sqlmap" or "masscan" before it reaches the loopback listener.
 * Both markers are in the backend's list and are covered by
 * `apps/security/tests/test_detectors.py`; only the browser-driven leg
 * has to route around the local product.
 */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000/api/v1";
const ORIGIN = "http://localhost:8000";
const SHOT_DIR = process.env.SHOT_DIR ?? "e2e-shots";
const ADMIN = { email: "admin@kawaiibake.local", password: "Kawaii!Chef2026" };
const LEARNER = { email: "p16-learner@example.com", password: "Rhubarb!Tart2024" };

/** The synthetic source every probe in this test claims to come from. */
const PROBE_IP = "203.0.113.99";
const PROBE_HEADERS = { "X-Forwarded-For": PROBE_IP };

let passed = 0;
function ok(label) {
  passed += 1;
  console.log(`  ok ${String(passed).padStart(2, "0")}  ${label}`);
}
async function expect(page, selector, label, timeout = 15_000) {
  await page.waitForSelector(selector, { timeout });
  ok(label);
}
function assert(condition, label) {
  if (!condition) throw new Error(`FAILED: ${label}`);
  ok(label);
}

function cleanup() {
  const repo = resolve(process.cwd(), "..");
  execFileSync(
    resolve(repo, ".venv/Scripts/python.exe"),
    [
      "manage.py",
      "shell",
      "-c",
      `from apps.security.models import SecurityEvent, ThreatProfile
SecurityEvent.objects.filter(ip="${PROBE_IP}").delete()
ThreatProfile.objects.filter(ip="${PROBE_IP}").delete()
print("cleaned")`,
    ],
    { cwd: repo, env: { ...process.env, PYTHONIOENCODING: "utf-8" } },
  );
}

const browser = await chromium.launch();
try {
  cleanup(); // start from a known-empty fixture

  /* ---------- The public policy ---------- */
  const anon = await browser.newContext({ viewport: { width: 1360, height: 950 } });
  const guest = await anon.newPage();
  await guest.goto(BASE);

  const policy = await guest.evaluate(
    async (api) => (await fetch(`${api}/security/client-policy/`)).json(),
    API,
  );
  assert(
    ["off", "detect", "deter"].includes(policy.guard_mode),
    `client policy is public and env-driven (mode: ${policy.guard_mode})`,
  );
  assert(
    !("score" in policy) && !("level" in policy),
    "the policy tells a visitor nothing about their own standing",
  );

  /* ---------- The deterrent, anonymous ---------- */
  if (policy.guard_mode === "deter") {
    // The guard fetches its policy before attaching listeners.
    await guest.waitForTimeout(1200);
    const suppressed = await guest.evaluate(() => {
      const event = new MouseEvent("contextmenu", {
        bubbles: true,
        cancelable: true,
      });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    assert(suppressed, "deter mode suppresses the context menu for a visitor");
  } else {
    ok(`deter checks skipped  server is in "${policy.guard_mode}" mode`);
  }

  /* ---------- A browser-reported signal is accepted and bounded ---------- */
  const reported = await guest.evaluate(async (api) => {
    const good = await fetch(`${api}/security/client-signals/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "devtools_opened", path: "/e2e" }),
    });
    const forged = await fetch(`${api}/security/client-signals/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "scanner_agent" }),
    });
    const spoofed = await fetch(`${api}/security/client-signals/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "devtools_opened", ip: "203.0.113.1" }),
    });
    return { good: good.status, forged: forged.status, spoofed: spoofed.status };
  }, API);
  assert(reported.good === 201, "a browser may report a devtools signal");
  assert(reported.forged === 400, "a browser may NOT forge a server-only signal");
  assert(reported.spoofed === 400, "a browser may NOT choose the address recorded");

  /* ---------- Real probes, from a synthetic source ---------- */
  const probes = [
    { path: "/.env", ua: "nikto/2.5.0", expect: "scanner_agent" },
    { path: "/wp-login.php", ua: "Mozilla/5.0", expect: "honeypot_path" },
    { path: "/backup.sql", ua: "Mozilla/5.0", expect: "sensitive_file_probe" },
    {
      path: "/api/v1/recipes/?search=x%27%20UNION%20SELECT%20password",
      ua: "Mozilla/5.0",
      expect: "sqli_probe",
    },
    { path: "/api/v1/courses/", ua: "curl/8.4.0", expect: "automation_agent" },
    {
      path: "/api/v1/recipes/",
      ua: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
      expect: null, // allowed crawler  must score nothing
    },
  ];
  for (const probe of probes) {
    await anon.request.get(`${ORIGIN}${probe.path}`, {
      headers: { ...PROBE_HEADERS, "User-Agent": probe.ua },
      failOnStatusCode: false,
    });
  }
  ok(`fired ${probes.length} probes from ${PROBE_IP}`);

  const trap = await anon.request.get(`${ORIGIN}/.env`, {
    headers: { ...PROBE_HEADERS, "User-Agent": "Mozilla/5.0" },
    failOnStatusCode: false,
  });
  const ordinaryMiss = await anon.request.get(
    `${ORIGIN}/definitely-not-a-real-path-9182/`,
    { headers: { ...PROBE_HEADERS, "User-Agent": "Mozilla/5.0" }, failOnStatusCode: false },
  );
  assert(trap.status() === 404, "a trap path answers an ordinary 404");
  // The property that matters is that the trap tells the scanner nothing
  // an ordinary miss would not. Comparing whole bodies is no good  the
  // DEBUG 404 page echoes the requested path  so compare *what the two
  // responses reveal*: no detection vocabulary may appear in one and not
  // the other.
  const trapBody = (await trap.text()).toLowerCase();
  const missBody = (await ordinaryMiss.text()).toLowerCase();
  const tells = ["honeypot", "request_blocked", "suspicious", "threat", "detected"];
  assert(
    trap.status() === ordinaryMiss.status() &&
      tells.every((word) => trapBody.includes(word) === missBody.includes(word)),
    "a trap reveals nothing an ordinary missing page does not",
  );
  await anon.close();

  /* ---------- Staff dashboard ---------- */
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const apiErrors = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/v1/") && r.status() >= 500) {
      apiErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    }
  });

  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', ADMIN.email);
  await page.fill('input[type="password"]', ADMIN.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  await page.goto(`${BASE}/admin/security`);
  // `h1`, not a bare text match: the same label is also a sidebar link,
  // which is display:none below `lg` and would never become visible.
  await expect(page, 'h1:has-text("ความปลอดภัย")', "the security page renders for staff");
  await expect(page, "text=แหล่งที่มา", "the sources tab renders");

  // The honest-labelling requirement, asserted rather than assumed.
  await expect(
    page,
    "text=/หน้าเว็บไม่สามารถห้ามเปิด DevTools ได้จริง/",
    "the page states plainly that devtools cannot actually be blocked",
  );

  /* ---------- What the backend actually recorded ---------- */
  const truth = await page.evaluate(async (api) => {
    const events = await (
      await fetch(`${api}/admin/security/events/?ip=203.0.113.99&page_size=50`, {
        credentials: "include",
      })
    ).json();
    const profiles = await (
      await fetch(`${api}/admin/security/profiles/?search=203.0.113.99`, {
        credentials: "include",
      })
    ).json();
    const summary = await (
      await fetch(`${api}/admin/security/summary/`, { credentials: "include" })
    ).json();
    return {
      kinds: events.results.map((row) => row.kind),
      agents: events.results.map((row) => row.user_agent),
      profile: profiles.results[0] ?? null,
      summary,
    };
  }, API);

  for (const probe of probes.filter((item) => item.expect)) {
    assert(
      truth.kinds.includes(probe.expect),
      `${probe.expect} recorded for ${probe.path.slice(0, 42)}`,
    );
  }
  assert(
    !truth.agents.some((agent) => agent.toLowerCase().includes("googlebot")),
    "the Googlebot request produced no event at all",
  );
  assert(truth.profile !== null, "the probes rolled up into one source profile");
  assert(
    truth.profile.level === "critical",
    `repeated probing bands the source as critical (score ${truth.profile.score.toFixed(1)})`,
  );
  assert(
    truth.profile.current_score <= truth.profile.score,
    "the decayed score never exceeds the stored one",
  );
  assert(
    truth.summary.profiles_by_level.critical >= 1,
    "the summary counts it in the critical band",
  );

  /* ---------- The dashboard shows it ---------- */
  await page.fill('input[type="search"]', PROBE_IP);
  await page.waitForTimeout(800);
  await expect(page, `text=${PROBE_IP}`, "search finds the source by address");
  await expect(page, "text=วิกฤต", "the critical band is labelled in Thai");
  await page.screenshot({ path: `${SHOT_DIR}/80-admin-security.png`, fullPage: true });

  /* ---------- Drill down and act ---------- */
  await page.click(`td:has-text("${PROBE_IP}")`);
  await expect(page, "dialog[open]", "the source detail panel opens");
  await expect(page, "text=หลักฐานล่าสุด", "the evidence list renders");
  await expect(page, "text=/คะแนนลดลงครึ่งหนึ่งทุก 12 ชม/", "decay is explained, not hidden");
  await page.screenshot({ path: `${SHOT_DIR}/81-security-detail.png` });

  await page.click('button:has-text("บล็อก 60 นาที")');
  await expect(page, "text=/IP หนึ่งอาจเป็นผู้ใช้หลายคน/", "blocking warns that an IP is not a person");
  // Two dialogs are open at once (the detail panel and the confirmation),
  // and both contain a button with this label  target the confirmation
  // by its own aria-label so the click is unambiguous.
  await page.click(
    `dialog[aria-label="บล็อก ${PROBE_IP} 60 นาที"] button:has-text("บล็อก 60 นาที")`,
  );
  await page.waitForTimeout(1200);

  const blocked = await page.evaluate(
    async (api) =>
      (
        await (
          await fetch(`${api}/admin/security/profiles/?search=203.0.113.99`, {
            credentials: "include",
          })
        ).json()
      ).results[0],
    API,
  );
  assert(blocked.is_blocked, "the block is recorded through the real endpoint");
  assert(blocked.blocked_until !== null, "the block carries an expiry  never permanent");

  // And it is enforced on the next request from that address.
  const denied = await context.request.get(`${ORIGIN}/api/v1/recipes/`, {
    headers: PROBE_HEADERS,
    failOnStatusCode: false,
  });
  assert(denied.status() === 403, "a blocked source is refused on its next request");
  const deniedBody = await denied.json();
  assert(
    deniedBody.error?.code === "request_blocked",
    "the refusal uses the platform's standard error envelope",
  );

  await page.click('button:has-text("ปลดบล็อก")');
  await page.waitForTimeout(1200);
  const allowed = await context.request.get(`${ORIGIN}/api/v1/recipes/`, {
    headers: PROBE_HEADERS,
    failOnStatusCode: false,
  });
  assert(allowed.status() === 200, "unblocking takes effect on the next request");

  await page.click('button:has-text("ตรวจแล้ว  ปกติ")');
  await page.waitForTimeout(1000);
  const reviewed = await page.evaluate(
    async (api) =>
      (
        await (
          await fetch(`${api}/admin/security/profiles/?search=203.0.113.99`, {
            credentials: "include",
          })
        ).json()
      ).results[0],
    API,
  );
  assert(reviewed.review_state === "ignored", "triage is recorded");
  assert(reviewed.reviewed_by_handle !== "", "triage records who decided");
  assert(
    reviewed.score === blocked.score,
    "marking reviewed changes no score and deletes no evidence",
  );

  /* ---------- The events tab and its filters ---------- */
  await page.keyboard.press("Escape");
  await page.click('button[role="tab"]:has-text("บันทึกเหตุการณ์")');
  // Scope to the events panel and to real cells: a bare `text=` locator
  // also matches the hidden <option> "No user agent supplied" in the
  // filter select, which never becomes visible.
  const eventsPanel = page.locator('[role="tabpanel"]').nth(1);
  await eventsPanel.locator('th:has-text("User agent")').waitFor({ state: "visible" });
  ok("the event log renders");
  await eventsPanel.locator('input[type="search"]').fill("nikto");
  await page.waitForTimeout(1000);
  await eventsPanel.locator('td:has-text("nikto")').first().waitFor({ state: "visible" });
  ok("the event log is searchable by user agent");
  await page.screenshot({ path: `${SHOT_DIR}/82-security-events.png`, fullPage: true });

  /* ---------- Non-staff cannot reach any of it ---------- */
  const learnerContext = await browser.newContext();
  const learner = await learnerContext.newPage();
  await learner.goto(`${BASE}/login`);
  await learner.fill('input[type="email"]', LEARNER.email);
  await learner.fill('input[type="password"]', LEARNER.password);
  await learner.click('button[type="submit"]');
  await learner.waitForURL((url) => !url.pathname.startsWith("/login"));

  await learner.goto(`${BASE}/admin/security`);
  await expect(learner, "text=403", "a signed-in learner is stopped at the staff gate");

  const learnerApi = await learner.evaluate(
    async (api) =>
      (
        await fetch(`${api}/admin/security/summary/`, { credentials: "include" })
      ).status,
    API,
  );
  assert(learnerApi === 403, "and the API refuses them too, not just the UI");

  // The deterrent leaves signed-in visitors alone.
  if (policy.guard_mode === "deter" && policy.exempt_authenticated) {
    await learner.goto(BASE);
    await learner.waitForTimeout(1500);
    const suppressed = await learner.evaluate(() => {
      const event = new MouseEvent("contextmenu", {
        bubbles: true,
        cancelable: true,
      });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    assert(!suppressed, "a signed-in visitor is exempt from the deterrent");
  }
  await learnerContext.close();

  /* ---------- Mobile ---------- */
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(`${BASE}/admin/security`);
  await mobile.waitForSelector('h1:has-text("ความปลอดภัย")');
  const overflows = await mobile.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  assert(!overflows, "the dashboard does not scroll horizontally on mobile");
  await mobile.screenshot({ path: `${SHOT_DIR}/83-security-mobile.png`, fullPage: true });
  await mobile.close();

  if (apiErrors.length) {
    throw new Error(`Unexpected 5xx responses:\n  ${apiErrors.join("\n  ")}`);
  }
  ok("no 5xx responses anywhere in the run");

  console.log(`\nSecurity E2E: ${passed}/${passed} passed`);
} finally {
  cleanup();
  console.log(`cleaned up every row for ${PROBE_IP}`);
  await browser.close();
}
