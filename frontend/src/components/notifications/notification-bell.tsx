"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type { NotificationList } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { LottieHover } from "@/components/ui/lottie-asset";
import { NotificationRow } from "@/components/notifications/notification-item";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

/** How many the panel shows before sending the reader to the full page. */
const PREVIEW_SIZE = 5;

/**
 * The bell, and the panel that drops from it.
 *
 * A peek, not a second notification centre: the newest few, the unread
 * count, and one link to the real page. The list is fetched when the
 * panel opens rather than on every page load — a badge nobody looked at
 * is not worth a request per navigation.
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const notifications = useApiQuery(
    (signal) =>
      api.get<NotificationList>("/me/notifications/", {
        query: { page_size: PREVIEW_SIZE },
        signal,
      }),
    [],
  );

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const unread = notifications.data?.unread_count ?? 0;
  const items = notifications.data?.results ?? [];

  async function markAll() {
    try {
      await api.post("/me/notifications/read-all/");
      notifications.refetch();
    } catch {
      // The panel is a peek; a failed bulk read is not worth a toast
      // over the page the reader is actually looking at.
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-label={
          unread > 0 ? `การแจ้งเตือน ${unread} รายการใหม่` : "การแจ้งเตือน"
        }
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setOpen((value) => !value);
          if (!open) notifications.refetch();
        }}
        className="relative flex size-10 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-focus"
      >
        <LottieHover
          src="/lottie/Notification bell.lottie"
          className="size-10"
        />
        {unread > 0 ? (
          <span className="absolute right-0.5 top-0.5 flex min-w-4.5 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-medium leading-4.5 text-fg-inverted">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <section
          role="dialog"
          aria-label="การแจ้งเตือนล่าสุด"
          className={cn(
            "absolute right-0 top-full z-50 mt-2 w-88 max-w-[calc(100vw-2rem)]",
            "rounded-surface border border-edge bg-surface shadow-overlay",
          )}
        >
          <header className="flex items-center justify-between gap-2 border-b border-edge px-3.5 py-2.5">
            <p className="text-sm font-medium text-fg">
              การแจ้งเตือน
              {unread > 0 ? (
                <span className="ml-1.5 text-xs font-normal text-fg-muted">
                  ใหม่ {unread} รายการ
                </span>
              ) : null}
            </p>
            {unread > 0 ? (
              <button
                type="button"
                onClick={() => void markAll()}
                className="text-xs text-fg-muted underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
              >
                อ่านทั้งหมด
              </button>
            ) : null}
          </header>

          <div className="max-h-96 overflow-y-auto p-2">
            {notifications.loading ? (
              <div className="space-y-2" aria-busy="true">
                <Skeleton className="h-14 w-full rounded-surface" />
                <Skeleton className="h-14 w-full rounded-surface" />
              </div>
            ) : items.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-fg-muted">
                ยังไม่มีการแจ้งเตือน
              </p>
            ) : (
              <ul className="space-y-2">
                {items.map((item) => (
                  <NotificationRow
                    key={item.id}
                    item={item}
                    compact
                    onNavigate={() => setOpen(false)}
                  />
                ))}
              </ul>
            )}
          </div>

          <footer className="border-t border-edge px-3.5 py-2.5 text-center">
            <Link
              href="/notifications"
              onClick={() => setOpen(false)}
              className="text-sm font-medium text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
            >
              ดูทั้งหมด →
            </Link>
          </footer>
        </section>
      ) : null}
    </div>
  );
}
