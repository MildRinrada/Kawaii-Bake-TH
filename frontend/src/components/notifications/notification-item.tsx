"use client";

import Link from "next/link";

import { api } from "@/lib/api/client";
import type { NotificationItem as Item } from "@/lib/api/models";
import { relativeThai } from "@/lib/datetime";
import { announcementStyle, eventIcon } from "@/lib/notifications";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

/**
 * One notification, shared by the bell panel and the notification centre.
 *
 * Three things it is deliberate about:
 *
 * **Unread is a mark, not a tint.** A solid dot and a bold title carry
 * the state; the background wash alone was a shade of pink most screens
 * render as "white, probably".
 *
 * **The time is a time, not a timestamp.** "47 นาทีที่แล้ว" beside the
 * title, where meta belongs — `11/8/2569 17:24:17` under the CTA told
 * nobody anything and cost a line.
 *
 * **The whole row is the link.** Every card carried an identical "ดู
 * รายละเอียด →", which is a sentence that says only "this is clickable".
 *
 * **A staff announcement is drawn by its kind** (ฟีเจอร์ใหม่, ปิดปรับปรุง,
 * แจ้งเตือนสำคัญ …) - one glyph and one colour per kind, from
 * `ANNOUNCEMENT_KINDS`. Before that every announcement was the same
 * lavender pin, so "ระบบจะปิดปรับปรุงคืนนี้" and "มีคอร์สใหม่มาแล้ว"
 * were indistinguishable at a glance.
 */
/**
 * Report that the recipient followed this row's link.
 *
 * Fire-and-forget on purpose: navigation must not wait on analytics, and
 * a report that never lands is a click the platform simply does not
 * count (which is why the admin panel calls the number a floor). The
 * server also stamps `read_at` from here - you cannot open what a
 * notification points at without having read it.
 */
function recordClick(id: number) {
  void api.post(`/me/notifications/${id}/click/`).catch(() => {});
}

export function NotificationRow({
  item,
  onMarkRead,
  compact = false,
  onNavigate,
}: {
  item: Item;
  /** Omitted where marking read is not offered (the bell panel marks on
      open instead). */
  onMarkRead?: (id: number) => void;
  compact?: boolean;
  onNavigate?: () => void;
}) {
  const unread = item.read_at === null;
  const announcement = item.event_type === "announcement";
  const style = announcementStyle(item.kind);

  const body = (
    <div className="flex min-w-0 flex-1 items-start gap-3">
      <span
        aria-hidden
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full",
          compact ? "size-8" : "size-10",
          announcement ? style.tone : "bg-surface-sunken text-fg-muted",
        )}
      >
        <Icon
          tint
          name={`ui/${announcement ? style.icon : eventIcon(item.event_type, false)}`}
          className={compact ? "size-4" : "size-5"}
        />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <p
            className={cn(
              "flex min-w-0 items-center gap-1.5 text-sm text-fg",
              unread && "font-medium",
            )}
          >
            {unread ? (
              <span
                aria-label="ยังไม่ได้อ่าน"
                className="size-2 shrink-0 rounded-full bg-accent"
              />
            ) : null}
            <span className="min-w-0 truncate">{item.title}</span>
          </p>
          <time
            dateTime={item.created_at}
            className="shrink-0 text-xs text-fg-subtle"
          >
            {relativeThai(item.created_at)}
          </time>
        </div>

        {announcement ? (
          <span
            className={cn(
              "mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
              style.tone,
            )}
          >
            {style.label}
          </span>
        ) : null}

        {item.body ? (
          <p
            className={cn(
              "mt-0.5 text-sm text-fg-muted",
              compact && "line-clamp-2",
            )}
          >
            {item.body}
          </p>
        ) : null}

        {/* Only a CTA that names its destination earns a line of its
            own; the generic one is replaced by the row being clickable. */}
        {item.link && item.cta_text ? (
          <span className="mt-1 inline-block text-sm font-medium text-accent">
            {item.cta_text} →
          </span>
        ) : null}
      </div>
    </div>
  );

  return (
    <li
      className={cn(
        "rounded-surface border transition-colors",
        unread ? "border-accent/25 bg-berry-soft/30" : "border-edge bg-surface",
      )}
    >
      <div className={cn("flex items-start gap-2", compact ? "p-2.5" : "p-3.5")}>
        {item.link ? (
          <Link
            href={item.link}
            onClick={() => {
              recordClick(item.id);
              onNavigate?.();
            }}
            className="flex min-w-0 flex-1 rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            {body}
          </Link>
        ) : (
          body
        )}

        {/* Read rows carry nothing: a disabled-looking "อ่านแล้ว" badge
            beside an identical button was two controls saying one word. */}
        {unread && onMarkRead ? (
          <button
            type="button"
            onClick={() => onMarkRead(item.id)}
            className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium text-fg-muted hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            ทำเป็นอ่านแล้ว
          </button>
        ) : null}
      </div>
    </li>
  );
}
