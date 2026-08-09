"use client";

/**
 * Admin chrome: sidebar, topbar, breadcrumbs and the staff gate.
 *
 * The gate reads `is_staff` from `/auth/me/` (ADR 0022) and is a
 * *rendering* decision only — the backend authorises every read and
 * write regardless. A non-staff caller who types an admin URL sees the
 * 403 screen here, and would see nothing privileged even if they didn't:
 * `scope=all` silently narrows to the public set for non-staff.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { api } from "@/lib/api/client";
import type { Me, NotificationList } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  /** Set when the page can only report a backend gap. */
  limited?: boolean;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

export const ADMIN_NAV: NavGroup[] = [
  {
    title: "ภาพรวม",
    items: [{ href: "/admin/dashboard", label: "แดชบอร์ด", icon: "▦" }],
  },
  {
    title: "เนื้อหา",
    items: [
      { href: "/admin/recipes", label: "สูตรอาหาร", icon: "🍰" },
      { href: "/admin/courses", label: "คอร์สเรียน", icon: "🎓" },
      { href: "/admin/lessons", label: "บทเรียน", icon: "📑" },
      { href: "/admin/categories", label: "หมวดหมู่", icon: "🏷" },
      { href: "/admin/quizzes", label: "แบบทดสอบ", icon: "✎" },
    ],
  },
  {
    title: "ชุมชน",
    items: [
      { href: "/admin/reviews", label: "รีวิว", icon: "★" },
      { href: "/admin/questions", label: "คลังคำถาม", icon: "?" },
    ],
  },
  {
    title: "การเรียนและรางวัล",
    items: [
      { href: "/admin/progress", label: "ความคืบหน้า", icon: "◷", limited: true },
      { href: "/admin/certificates", label: "ใบประกาศ", icon: "📜", limited: true },
      { href: "/admin/achievements", label: "ความสำเร็จ", icon: "🏅", limited: true },
      { href: "/admin/favorites", label: "รายการโปรด", icon: "♥", limited: true },
    ],
  },
  {
    title: "ระบบ",
    items: [
      { href: "/admin/users", label: "ผู้ใช้", icon: "👤", limited: true },
      { href: "/admin/notifications", label: "การแจ้งเตือน", icon: "🔔", limited: true },
      { href: "/admin/assistant", label: "ผู้ช่วย AI", icon: "✦", limited: true },
      { href: "/admin/recommendations", label: "การแนะนำ", icon: "◈", limited: true },
    ],
  },
];

const LABELS = new Map(
  ADMIN_NAV.flatMap((group) => group.items).map((item) => [item.href, item.label]),
);

/* ------------------------------------------------------------------ */
/* Staff gate                                                          */
/* ------------------------------------------------------------------ */

function GateScreen({
  code,
  title,
  description,
  action,
}: {
  code: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-md rounded-md border border-edge bg-surface-raised p-6 text-center">
        <p className="font-mono text-sm font-semibold text-warning">{code}</p>
        <h1 className="mt-2 text-lg font-semibold text-fg">{title}</h1>
        <p className="mt-2 text-sm text-fg-muted">{description}</p>
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
    </div>
  );
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);
  // The session mirror is the live signal: signing out elsewhere in the
  // app must drop this shell back to the gate, not leave it rendering
  // admin chrome against a stale identity read.
  const { status: sessionStatus } = useAuth();

  const me = useApiQuery(
    (signal) => api.get<{ user: Me | null }>("/auth/me/", { signal }),
    [],
  );

  if (me.loading || sessionStatus === "loading") {
    return (
      <div className="min-h-dvh bg-canvas p-6" aria-busy="true">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-4 h-64 w-full rounded-md" />
      </div>
    );
  }

  if (me.error) {
    return (
      <GateScreen
        code="ERROR"
        title="เชื่อมต่อระบบหลังบ้านไม่ได้"
        description="ตรวจสอบว่า API ทำงานอยู่ แล้วลองโหลดหน้านี้ใหม่อีกครั้ง"
        action={
          <Button size="sm" variant="secondary" onClick={me.refetch}>
            ลองใหม่
          </Button>
        }
      />
    );
  }

  const user =
    sessionStatus === "anonymous" ? null : (me.data?.user ?? null);

  if (!user) {
    return (
      <GateScreen
        code="401"
        title="ต้องเข้าสู่ระบบก่อน"
        description="ส่วนผู้ดูแลระบบเปิดให้เฉพาะบัญชีที่เข้าสู่ระบบและมีสิทธิ์ staff เท่านั้น"
        action={
          <Link href="/login">
            <Button size="sm">ไปหน้าเข้าสู่ระบบ</Button>
          </Link>
        }
      />
    );
  }

  if (!user.is_staff) {
    return (
      <GateScreen
        code="403"
        title="บัญชีนี้ไม่มีสิทธิ์ผู้ดูแลระบบ"
        description="คุณเข้าสู่ระบบแล้ว แต่บัญชีนี้ไม่ได้เป็น staff — ระบบหลังบ้านจะปฏิเสธคำสั่งของผู้ดูแลทุกคำสั่งอยู่ดี"
        action={
          <Link href="/">
            <Button size="sm" variant="secondary">
              กลับหน้าแรก
            </Button>
          </Link>
        }
      />
    );
  }

  const crumbLabel = LABELS.get(pathname) ?? "แดชบอร์ด";

  return (
    <div className="flex min-h-dvh bg-canvas">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-edge bg-surface lg:flex">
        <SidebarContent pathname={pathname} />
      </aside>

      {/* Mobile drawer */}
      {navOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="ปิดเมนู"
            onClick={() => setNavOpen(false)}
            className="absolute inset-0 bg-black/40"
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-edge bg-surface">
            <SidebarContent
              pathname={pathname}
              onNavigate={() => setNavOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader
          user={user}
          crumb={crumbLabel}
          onOpenNav={() => setNavOpen(true)}
        />
        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sidebar                                                             */
/* ------------------------------------------------------------------ */

function SidebarContent({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <>
      <div className="flex h-14 items-center gap-2 border-b border-edge px-4">
        <span aria-hidden className="text-lg">
          🧁
        </span>
        <div>
          <p className="text-sm font-semibold leading-tight text-fg">KawaiiBake</p>
          <p className="text-xs leading-tight text-fg-subtle">ผู้ดูแลระบบ</p>
        </div>
      </div>
      <nav aria-label="เมนูผู้ดูแลระบบ" className="flex-1 overflow-y-auto py-3">
        {ADMIN_NAV.map((group) => (
          <div key={group.title} className="mb-3">
            <p className="px-4 pb-1 text-xs font-medium uppercase tracking-wide text-fg-subtle">
              {group.title}
            </p>
            <ul>
              {group.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href as "/admin/dashboard"}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 px-4 py-1.5 text-sm focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                        active
                          ? "border-l-2 border-accent bg-accent-subtle pl-3.5 font-medium text-fg"
                          : "border-l-2 border-transparent pl-3.5 text-fg-muted hover:bg-surface-sunken hover:text-fg",
                      )}
                    >
                      <span aria-hidden className="w-4 text-center text-xs">
                        {item.icon}
                      </span>
                      <span className="truncate">{item.label}</span>
                      {item.limited ? (
                        <span
                          title="ระบบหลังบ้านยังไม่มี API สำหรับหน้านี้ทั้งหมด"
                          className="ml-auto text-xs text-warning"
                        >
                          !
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-edge px-4 py-3">
        <Link
          href="/"
          className="text-xs text-fg-muted hover:text-accent-hover"
          onClick={onNavigate}
        >
          ← กลับไปหน้าเว็บผู้เรียน
        </Link>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Topbar                                                              */
/* ------------------------------------------------------------------ */

function AdminHeader({
  user,
  crumb,
  onOpenNav,
}: {
  user: Me;
  crumb: string;
  onOpenNav: () => void;
}) {
  const { logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const notifications = useApiQuery(
    (signal) =>
      api.get<NotificationList>("/me/notifications/", {
        query: { page_size: 1 },
        signal,
      }),
    [],
  );
  const unread = notifications.data?.unread_count ?? 0;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-edge bg-surface/95 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onOpenNav}
        aria-label="เปิดเมนู"
        className="flex size-9 items-center justify-center rounded-md text-fg-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus lg:hidden"
      >
        <span aria-hidden>☰</span>
      </button>

      <nav aria-label="เส้นทางปัจจุบัน" className="min-w-0">
        <ol className="flex items-center gap-1.5 text-sm">
          <li>
            <Link
              href="/admin/dashboard"
              className="text-fg-muted hover:text-accent-hover"
            >
              ผู้ดูแลระบบ
            </Link>
          </li>
          <li aria-hidden className="text-fg-subtle">
            /
          </li>
          <li className="truncate font-medium text-fg" aria-current="page">
            {crumb}
          </li>
        </ol>
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <Link
          href="/notifications"
          aria-label={`การแจ้งเตือน${unread > 0 ? ` (ยังไม่อ่าน ${unread})` : ""}`}
          className="relative flex size-9 items-center justify-center rounded-md text-fg-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
        >
          <span aria-hidden>🔔</span>
          {unread > 0 ? (
            <span className="absolute right-1 top-1 flex min-w-4 justify-center rounded-full bg-danger px-1 text-[10px] font-medium text-fg-inverted">
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Link>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
          >
            <Avatar src={user.avatar_url} name={user.username} size="sm" />
            <span className="hidden text-sm text-fg sm:inline">
              {user.username}
            </span>
            <span aria-hidden className="text-xs text-fg-subtle">
              ▾
            </span>
          </button>
          {menuOpen ? (
            <div
              role="menu"
              className="absolute right-0 top-full z-40 mt-1 w-56 rounded-md border border-edge bg-surface-raised py-1 shadow-overlay"
            >
              <p className="border-b border-edge px-3 pb-2 pt-1 text-xs text-fg-muted">
                เข้าสู่ระบบเป็น{" "}
                <span className="font-medium text-fg">{user.username}</span>
                <span className="mt-0.5 block font-mono text-[11px] text-success">
                  staff
                </span>
              </p>
              <Link
                href="/profile"
                role="menuitem"
                onClick={() => setMenuOpen(false)}
                className="block px-3 py-1.5 text-sm text-fg hover:bg-surface-sunken"
              >
                โปรไฟล์ของฉัน
              </Link>
              <Link
                href="/settings"
                role="menuitem"
                onClick={() => setMenuOpen(false)}
                className="block px-3 py-1.5 text-sm text-fg hover:bg-surface-sunken"
              >
                ตั้งค่าบัญชี
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  void logout();
                }}
                className="block w-full px-3 py-1.5 text-left text-sm text-danger hover:bg-danger-subtle"
              >
                ออกจากระบบ
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Page header                                                         */
/* ------------------------------------------------------------------ */

export function AdminPageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-fg">{title}</h1>
        {description ? (
          <p className="mt-0.5 text-sm text-fg-muted">{description}</p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}
