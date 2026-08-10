/**
 * Edge trap catcher.
 *
 * The public site is served by Next.js, so a scan of
 * `https://kawaiibake.example/.env` never reaches Django and the
 * backend's threat watcher never sees it. This runs before any route is
 * rendered, answers the trap with an ordinary 404, and forwards the
 * observation to the backend so it lands in the same event log as
 * everything the API origin saw itself.
 *
 * Two deliberate properties:
 *
 * 1. **The response is indistinguishable from a normal miss.** A bespoke
 *    body would tell the scanner it had been spotted.
 * 2. **Forwarding never blocks or breaks the response.** It is fired and
 *    forgotten; if the backend is down the visitor still just gets a 404.
 *
 * Forwarding requires `SECURITY_INGEST_SECRET` (server-side only, NOT
 * `NEXT_PUBLIC_`) to match the backend's. Without it the trap still 404s
 * — it simply is not reported, and the backend answers 404 to the
 * forward attempt anyway.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const INGEST_SECRET = process.env.SECURITY_INGEST_SECRET ?? "";

/** Paths that exist nowhere in this project. Mirrors the backend list. */
const TRAP_PREFIXES = [
  "/.env",
  "/.git",
  "/.aws",
  "/.ssh",
  "/wp-login.php",
  "/wp-admin",
  "/wp-content",
  "/xmlrpc.php",
  "/phpmyadmin",
  "/phpinfo.php",
  "/shell.php",
  "/cgi-bin",
  "/vendor",
  "/actuator",
  "/config.json",
  "/credentials.json",
  "/server-status",
];

/** Extensions that only appear in a backup or a leaked secret. */
const SENSITIVE_SUFFIX =
  /\.(sql|bak|backup|dump|pem|key|p12|sqlite3|db|zip|log)(\.gz)?$/i;

const TRAVERSAL = /(\.\.\/|\.\.\\|%2e%2e|\/etc\/passwd)/i;

type Kind = "honeypot_path" | "sensitive_file_probe" | "path_traversal";

function classify(pathname: string): Kind | null {
  const path = decodeURIComponent(pathname).toLowerCase();
  if (TRAVERSAL.test(path)) return "path_traversal";
  if (TRAP_PREFIXES.some((trap) => path === trap || path.startsWith(`${trap}/`))) {
    return "honeypot_path";
  }
  if (SENSITIVE_SUFFIX.test(path)) return "sensitive_file_probe";
  return null;
}

/** The visitor's address as this edge sees it. */
function visitorIp(request: NextRequest): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]!.trim();
  return request.headers.get("x-real-ip") ?? "";
}

export async function proxy(request: NextRequest) {
  const kind = classify(request.nextUrl.pathname);
  if (kind === null) return NextResponse.next();

  const ip = visitorIp(request);
  if (INGEST_SECRET && ip) {
    // Fire and forget: a reporting failure must never change what the
    // visitor sees, and must never delay the response.
    void fetch(`${API_BASE_URL}/security/edge-signals/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-KB-Edge-Secret": INGEST_SECRET,
      },
      body: JSON.stringify({
        kind,
        ip,
        path: request.nextUrl.pathname.slice(0, 400),
        user_agent: (request.headers.get("user-agent") ?? "").slice(0, 400),
      }),
    }).catch(() => undefined);
  }

  return new NextResponse(null, { status: 404 });
}

export const config = {
  // Only the trap shapes. Everything else — including every real route,
  // static asset and image — skips this entirely, so the site pays
  // nothing for the trap.
  matcher: [
    "/.env/:path*",
    "/.git/:path*",
    "/.aws/:path*",
    "/.ssh/:path*",
    "/wp-admin/:path*",
    "/wp-content/:path*",
    "/wp-login.php",
    "/xmlrpc.php",
    "/phpmyadmin/:path*",
    "/phpinfo.php",
    "/shell.php",
    "/cgi-bin/:path*",
    "/vendor/:path*",
    "/actuator/:path*",
    "/config.json",
    "/credentials.json",
    "/server-status",
    "/:path*.sql",
    "/:path*.bak",
    "/:path*.dump",
    "/:path*.pem",
    "/:path*.sqlite3",
    "/:path*.zip",
  ],
};
