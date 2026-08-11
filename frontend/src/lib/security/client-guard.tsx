"use client";

/**
 * The browser-side guard  a deterrent and a sensor, never a control.
 *
 * ## Read this before changing it
 *
 * **A web page cannot prevent DevTools from opening.** It cannot detect
 * them reliably either. The browser menu, the command palette, a
 * keyboard remap, `--auto-open-devtools-for-tabs`, or simply running
 * `curl` all bypass everything below, and every published "detector" is
 * a heuristic that false-positives on zoom, docked panels, on-screen
 * keyboards and translation bars.
 *
 * Anything shipped to a browser is public. This file does not pretend
 * otherwise. What it actually buys:
 *
 * - a speed bump for casual poking (`deter` mode), and
 * - a **signal** the backend can correlate with real, server-observed
 *   probing from the same address (ADR 0025).
 *
 * Because the signal is forgeable and noisy, the backend scores it at
 * the very bottom of the weight table: ten devtools reports still rank
 * below one honeypot hit.
 *
 * ## Configuration
 *
 * The mode comes from **one** place  the backend's
 * `SECURITY_CLIENT_GUARD_MODE` env var, served by
 * `GET /security/client-policy/`. Duplicating it into a `NEXT_PUBLIC_`
 * variable would create two switches that can disagree.
 *
 *   off      nothing runs
 *   detect   observe and report, never interfere (default)
 *   deter    additionally intercept F12 / Ctrl+Shift+I / Ctrl+Shift+J /
 *             Ctrl+U / right-click
 *
 * Signed-in visitors are exempt from `deter` when the policy says so 
 * the requested "only logged-in users can open F12", stated the honest
 * way round: anonymous visitors meet the speed bump, signed-in ones do
 * not.
 */

import { useEffect, useRef } from "react";

import { API_BASE_URL } from "@/lib/config";
import { useAuth } from "@/lib/auth/auth-context";

type GuardMode = "off" | "detect" | "deter";

interface ClientPolicy {
  guard_mode: GuardMode;
  exempt_authenticated: boolean;
  report_signals: boolean;
}

type SignalKind =
  | "devtools_opened"
  | "view_source_attempt"
  | "context_menu_attempt"
  | "console_tamper";

/** Per-kind cooldown, so one determined visitor is not a firehose. */
const REPORT_COOLDOWN_MS = 60_000;

/** How often the window-geometry heuristic re-checks. */
const PROBE_INTERVAL_MS = 2_000;

/**
 * Threshold for the outer/inner size delta, in CSS pixels.
 *
 * Generous on purpose: a docked devtools panel is hundreds of pixels
 * wide, while browser chrome, scrollbars and zoom account for tens. A
 * tighter threshold would flag ordinary visitors, and a false positive
 * here is worse than a miss  the miss costs one weak signal, the false
 * positive puts a real learner in a security log.
 */
const SIZE_DELTA_PX = 220;

export function ClientGuard() {
  const { status } = useAuth();
  const sent = useRef(new Map<SignalKind, number>());

  useEffect(() => {
    // Wait for the session to resolve; acting while it is "loading"
    // would deter a signed-in visitor for the first second of every page.
    if (status === "loading") return;

    const controller = new AbortController();
    let cleanup: (() => void) | undefined;

    async function start() {
      let policy: ClientPolicy;
      try {
        const response = await fetch(`${API_BASE_URL}/security/client-policy/`, {
          signal: controller.signal,
        });
        if (!response.ok) return;
        policy = (await response.json()) as ClientPolicy;
      } catch {
        // No policy, no guard. Failing open is correct: a monitoring
        // feature must never be the reason a page misbehaves.
        return;
      }
      if (controller.signal.aborted || policy.guard_mode === "off") return;

      const exempt =
        policy.exempt_authenticated && status === "authenticated";
      const deter = policy.guard_mode === "deter" && !exempt;

      function report(kind: SignalKind, detail?: Record<string, string>) {
        if (!policy.report_signals) return;
        const now = Date.now();
        const last = sent.current.get(kind) ?? 0;
        if (now - last < REPORT_COOLDOWN_MS) return;
        sent.current.set(kind, now);

        const body = JSON.stringify({
          kind,
          path: window.location.pathname,
          ...(detail ? { detail } : {}),
        });
        // `keepalive` so a report survives the navigation that often
        // follows (Ctrl+U opens a new tab, for instance).
        void fetch(`${API_BASE_URL}/security/client-signals/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          keepalive: true,
        }).catch(() => undefined);
      }

      function onKeyDown(event: KeyboardEvent) {
        const key = event.key.toUpperCase();
        const devtools =
          event.key === "F12" ||
          ((event.ctrlKey || event.metaKey) &&
            event.shiftKey &&
            (key === "I" || key === "J" || key === "C"));
        const viewSource = (event.ctrlKey || event.metaKey) && key === "U";

        if (devtools) {
          report("devtools_opened", { via: "shortcut" });
          if (deter) event.preventDefault();
        } else if (viewSource) {
          report("view_source_attempt");
          if (deter) event.preventDefault();
        }
      }

      function onContextMenu(event: MouseEvent) {
        if (!deter) return;
        // Only reported in `deter` mode, where we actually suppressed
        // something. Logging every right-click in `detect` mode would
        // bury real signals under people copying a recipe.
        report("context_menu_attempt");
        event.preventDefault();
      }

      let flagged = false;
      function probeGeometry() {
        const wide = window.outerWidth - window.innerWidth > SIZE_DELTA_PX;
        const tall = window.outerHeight - window.innerHeight > SIZE_DELTA_PX;
        const open = wide || tall;
        // Edge-triggered: report the transition, not every tick.
        if (open && !flagged) {
          report("devtools_opened", { via: "geometry" });
        }
        flagged = open;
      }

      window.addEventListener("keydown", onKeyDown);
      window.addEventListener("contextmenu", onContextMenu);
      const timer = window.setInterval(probeGeometry, PROBE_INTERVAL_MS);

      cleanup = () => {
        window.removeEventListener("keydown", onKeyDown);
        window.removeEventListener("contextmenu", onContextMenu);
        window.clearInterval(timer);
      };
    }

    void start();
    return () => {
      controller.abort();
      cleanup?.();
    };
  }, [status]);

  return null;
}
