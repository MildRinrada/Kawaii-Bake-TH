import type { UiIconName } from "@/components/ui/icon";

/**
 * How a notification is presented - shared by the bell panel and the
 * notification centre so the two can never drift apart.
 */

/** One line glyph per wired event type; unknown types fall back to the
    bell. Staff announcements are drawn as announcements, not as whatever
    emoji the sender typed - one icon system, not two. */
const EVENT_ICONS: Record<string, UiIconName> = {
  review_received: "star",
  course_enrollment: "graduation",
  achievement_earned: "medal",
  qa_answer_received: "chat",
  qa_answer_accepted: "check-circle",
  gallery_comment: "chat",
  custom: "pin",
};

export function eventIcon(eventType: string, announcement: boolean): UiIconName {
  if (announcement) return "pin";
  return EVENT_ICONS[eventType] ?? "bell";
}

/**
 * How a staff announcement is drawn.
 *
 * A closed set mirroring `AnnouncementKind` in
 * `apps/notifications/constants.py`: the sender picks a *category*, and
 * this table picks the glyph, the colour and the badge wording. That is
 * the whole point of the kind existing - it replaced a free emoji field,
 * where a sender could put anything and every announcement still looked
 * identical in the list.
 *
 * An unknown kind (an older row, a value added server-side first) falls
 * back to `general` rather than rendering nothing.
 */
export interface AnnouncementStyle {
  label: string;
  icon: UiIconName;
  /** Tailwind classes for the glyph bubble and the badge. */
  tone: string;
}

export const ANNOUNCEMENT_KINDS: Record<string, AnnouncementStyle> = {
  general: {
    label: "ประกาศจากทีมงาน",
    icon: "pin",
    tone: "bg-lavender-soft text-lavender-ink",
  },
  feature: {
    label: "ฟีเจอร์ใหม่",
    icon: "sparkle",
    tone: "bg-berry-soft text-berry-ink",
  },
  event: {
    label: "กิจกรรม",
    icon: "party",
    tone: "bg-butter-soft text-butter-ink",
  },
  maintenance: {
    label: "ปิดปรับปรุงระบบ",
    icon: "plug",
    tone: "bg-surface-sunken text-fg-muted",
  },
  policy: {
    label: "นโยบายและข้อกำหนด",
    icon: "shield",
    tone: "bg-mint-soft text-mint-ink",
  },
  alert: {
    label: "แจ้งเตือนสำคัญ",
    icon: "alert",
    tone: "bg-danger-subtle text-danger",
  },
};

export const ANNOUNCEMENT_KIND_ORDER = [
  "general",
  "feature",
  "event",
  "maintenance",
  "policy",
  "alert",
] as const;

export function announcementStyle(kind: string | undefined): AnnouncementStyle {
  return ANNOUNCEMENT_KINDS[kind ?? ""] ?? ANNOUNCEMENT_KINDS.general;
}

/** The buckets the notification centre offers as tabs. */
export type NotificationGroup = "engagement" | "achievement" | "announcement";

const GROUPS: Record<string, NotificationGroup> = {
  review_received: "engagement",
  course_enrollment: "engagement",
  qa_answer_received: "engagement",
  qa_answer_accepted: "engagement",
  gallery_comment: "engagement",
  achievement_earned: "achievement",
};

/** The bucket one event type belongs to. Anything not about the reader
    personally is an announcement - the one category someone may want to
    mute without losing the things that concern them. */
export function groupForEventType(eventType: string): NotificationGroup {
  return GROUPS[eventType] ?? "announcement";
}

/** Thai names for the buckets, shared by the centre and the settings. */
export const GROUP_LABELS: Record<NotificationGroup, string> = {
  engagement: "การมีส่วนร่วม",
  achievement: "ความสำเร็จ",
  announcement: "ประกาศจากทีมงาน",
};

/** Which bucket a notification belongs to. */
export function notificationGroup(item: {
  event_type: string;
}): NotificationGroup {
  return groupForEventType(item.event_type);
}

/** "วันนี้" / "เมื่อวาน" / a date - the heading a run of items sits under. */
export function dayBucket(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const startOfDay = (value: Date) =>
    new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  const days = Math.round(
    (startOfDay(today) - startOfDay(date)) / (24 * 60 * 60 * 1000),
  );
  if (days <= 0) return "วันนี้";
  if (days === 1) return "เมื่อวาน";
  if (days < 7) return "สัปดาห์นี้";
  return "ก่อนหน้านี้";
}
