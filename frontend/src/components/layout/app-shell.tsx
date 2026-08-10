"use client";

/**
 * KawaiiBake application chrome.
 *
 * Desktop: sticky translucent cream header — wordmark, pill nav, auth
 * area. Mobile: the nav collapses into a disclosure panel under a
 * hamburger. Footer is a quiet cream band. Warm, calm, zero decoration
 * that fights the content.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import type { Route } from "next";

import { BRAND_MARK } from "@/lib/assets";
import { ArtIcon, Icon } from "@/components/ui/icon";
import { LottieHover } from "@/components/ui/lottie-asset";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth/auth-context";
import { Avatar } from "@/components/ui/avatar";
import { Dropdown } from "@/components/ui/dropdown";

// Recipes and Community are the two creation destinations and both sit
// in the top level of the nav — Community is never nested inside the
// recipe section, and recipe authoring is never nested inside Community.
const NAV_ITEMS: Array<{ href: Route; label: string }> = [
  { href: "/recipes", label: "สูตรขนม" },
  { href: "/courses", label: "คอร์สเรียน" },
  { href: "/community", label: "ชุมชน" },
  { href: "/recommendations", label: "แนะนำสำหรับคุณ" },
  { href: "/assistant", label: "ผู้ช่วย AI" },
];

const FOOTER_LEARN: Array<{ href: Route; label: string }> = [
  { href: "/recipes", label: "สูตรขนมทั้งหมด" },
  { href: "/courses", label: "คอร์สเรียน" },
  { href: "/community", label: "ชุมชน" },
  { href: "/recommendations", label: "แนะนำสำหรับคุณ" },
  { href: "/assistant", label: "ผู้ช่วย AI" },
];

const FOOTER_ACCOUNT: Array<{ href: Route; label: string }> = [
  { href: "/profile", label: "โปรไฟล์" },
  { href: "/favorites", label: "รายการโปรด" },
  { href: "/certificates", label: "ใบประกาศนียบัตร" },
  { href: "/achievements", label: "ความสำเร็จ" },
  { href: "/settings", label: "ตั้งค่า" },
];

function NavLink({
  href,
  label,
  active,
  onNavigate,
}: {
  href: Route;
  label: string;
  active: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "rounded-full px-4 py-1.5 text-sm transition-colors",
        "focus-visible:outline-2 focus-visible:outline-focus",
        active
          ? "bg-berry-soft font-medium text-berry-ink"
          : "text-fg-muted hover:bg-surface-sunken hover:text-fg",
      )}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { status, user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  // Close the mobile panel on navigation — derived during render (the
  // React-documented alternative to a setState effect).
  const [menuPath, setMenuPath] = useState(pathname);
  if (menuPath !== pathname) {
    setMenuPath(pathname);
    setMenuOpen(false);
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-40 border-b border-edge bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Link
            href="/"
            className="font-display flex items-center gap-2 text-lg font-medium text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            <ArtIcon src={BRAND_MARK} className="size-13" />
            <span>
              Kawaii<span className="text-accent">Bake</span>
            </span>
          </Link>

          <nav aria-label="เมนูหลัก" className="hidden gap-1 lg:flex">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                active={pathname.startsWith(item.href)}
              />
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1.5">
            {status === "authenticated" && user ? (
              <>
                <Link
                  href="/notifications"
                  aria-label="การแจ้งเตือน"
                  className={cn(
                    "flex size-10 items-center justify-center text-lg",
                    pathname.startsWith("/notifications") && "",
                  )}
                >
                  <LottieHover src="/lottie/Notification bell.lottie" className="size-10" />
                </Link>
                <Dropdown
                  align="end"
                  trigger={
                    <span className="flex items-center gap-2 rounded-full py-1 pl-1 pr-3 hover:bg-surface-sunken">
                      <Avatar
                        src={user.avatar_url}
                        name={user.display_name || user.username}
                        size="sm"
                      />
                      <span className="hidden max-w-32 truncate text-sm font-medium text-fg sm:block">
                        {user.display_name || user.username}
                      </span>
                    </span>
                  }
                  items={[
                    { key: "profile", label: "โปรไฟล์", onSelect: () => router.push("/profile") },
                    { key: "favorites", label: "รายการโปรด", onSelect: () => router.push("/favorites") },
                    { key: "certificates", label: "ใบประกาศ", onSelect: () => router.push("/certificates") },
                    { key: "achievements", label: "ความสำเร็จ", onSelect: () => router.push("/achievements") },
                    { key: "settings", label: "ตั้งค่า", onSelect: () => router.push("/settings") },
                    { key: "logout", label: "ออกจากระบบ", onSelect: () => void logout() },
                  ]}
                />
              </>
            ) : status === "anonymous" ? (
              <>
                <Link
                  href="/login"
                  className="rounded-full px-4 py-2 text-sm font-medium text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                >
                  เข้าสู่ระบบ
                </Link>
                <Link
                  href="/register"
                  className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-fg-inverted shadow-raised hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  สมัครสมาชิก
                </Link>
              </>
            ) : null}

            <button
              type="button"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              aria-label={menuOpen ? "ปิดเมนู" : "เปิดเมนู"}
              onClick={() => setMenuOpen((value) => !value)}
              className="flex size-10 items-center justify-center rounded-full text-fg hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus lg:hidden"
            >
              <Icon name={menuOpen ? "ui/close" : "ui/menu"} className="size-5" />
            </button>
          </div>
        </div>

        {menuOpen ? (
          <nav
            id="mobile-nav"
            aria-label="เมนูหลัก (มือถือ)"
            className="border-t border-edge bg-surface px-4 py-3 lg:hidden"
          >
            <div className="flex flex-col gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.href}
                  {...item}
                  active={pathname.startsWith(item.href)}
                  onNavigate={() => setMenuOpen(false)}
                />
              ))}
            </div>
          </nav>
        ) : null}
      </header>

      <main id="main" className="flex-1">
        {children}
      </main>

      <footer className="mt-12 border-t border-edge bg-surface-sunken/60">
        <div className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6">
          <div className="grid gap-8 sm:grid-cols-[2fr_1fr_1fr]">
            <div>
              <p className="font-display flex items-center gap-2 text-base font-medium text-fg">
                <ArtIcon src={BRAND_MARK} className="size-10" /> Kawaii
                <span className="-ml-2 text-accent">Bake</span>
              </p>
              <p className="mt-2 max-w-xs text-sm text-fg-muted">
                แพลตฟอร์มเรียนทำเบเกอรี่ภาษาไทย อบอุ่น เป็นมิตร
                และอร่อยทุกบทเรียน
              </p>
            </div>
            <nav aria-label="เมนูเรียนรู้">
              <p className="mb-2.5 text-sm font-medium text-fg">เรียนรู้</p>
              <ul className="space-y-1.5 text-sm">
                {FOOTER_LEARN.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            <nav aria-label="เมนูบัญชี">
              <p className="mb-2.5 text-sm font-medium text-fg">บัญชีของฉัน</p>
              <ul className="space-y-1.5 text-sm">
                {FOOTER_ACCOUNT.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
          <p className="mt-8 border-t border-edge pt-5 text-center text-xs text-fg-subtle">
            © 2026 KawaiiBake | โปรเจกต์พอร์ตโฟลิโอ สร้างด้วย Django + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
