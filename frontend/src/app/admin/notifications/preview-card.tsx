"use client";

/**
 * The live notification preview.
 *
 * It renders the *actual* component the notification centre and the bell
 * panel use, with sample values filled into `{{variables}}`. A preview
 * that reimplements the card drifts from it within one design change —
 * this one cannot, because there is only one card.
 */

import type { NotificationItem } from "@/lib/api/models";
import { NotificationRow } from "@/components/notifications/notification-item";

import { renderSample } from "./kinds";

export function NotificationPreviewCard({
  title,
  body,
  ctaText,
  link,
  kind,
  compact = false,
}: {
  title: string;
  body: string;
  ctaText: string;
  link: string;
  /** The announcement kind, which picks the glyph and colour. */
  kind: string;
  /** Narrow layout, imitating a phone-width notification center. */
  compact?: boolean;
}) {
  // A campaign send always lands as an unread `announcement` — the
  // preview is that row, not an approximation of it.
  const sample: NotificationItem = {
    id: 0,
    event_type: "announcement",
    title: renderSample(title) || "หัวข้อการแจ้งเตือน",
    body: renderSample(body),
    actor_handle: "",
    link,
    kind,
    cta_text: ctaText,
    read_at: null,
    clicked_at: null,
    created_at: new Date().toISOString(),
  };

  return (
    <ul className={compact ? "w-full max-w-xs" : "w-full max-w-md"}>
      <NotificationRow item={sample} compact={compact} />
    </ul>
  );
}
