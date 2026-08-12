/**
 * The notification-composer catalog: what an announcement can be about,
 * who it can target, and which `{{variables}}` are honest to use.
 *
 * Everything here is admin-side copy over closed server-side sets:
 * `kind`, audiences and variables are all enumerated in
 * `apps/notifications`, and this file only supplies Thai wording (and,
 * for kinds, re-exports the drawing the recipient sees).
 */

import {
  ANNOUNCEMENT_KINDS,
  ANNOUNCEMENT_KIND_ORDER,
} from "@/lib/notifications";
import type { UiIconName } from "@/components/ui/icon";

const KIND_DESCRIPTIONS: Record<string, string> = {
  general: "ข่าวสารทั่วไปถึงผู้ใช้",
  feature: "ฟีเจอร์ใหม่หรือการปรับปรุงที่ผู้ใช้ได้ประโยชน์",
  event: "กิจกรรม ชาเลนจ์ หรือแคมเปญที่ชวนเข้าร่วม",
  maintenance: "ช่วงเวลาที่ระบบจะใช้งานไม่ได้",
  policy: "การเปลี่ยนแปลงข้อตกลงหรือนโยบายความเป็นส่วนตัว",
  alert: "เรื่องด่วนที่ต้องให้ผู้ใช้รู้ทันที",
};

export type AnnouncementKindOption = {
  key: string;
  label: string;
  description: string;
  icon: UiIconName;
  /** The same bubble/badge classes the recipient's row uses. */
  tone: string;
};

/**
 * The kinds a staff announcement can be - the closed set the backend
 * enforces (`AnnouncementKind`), drawn exactly as the recipient will see
 * it.
 *
 * It replaced an open catalog of 26 slugs with an emoji each. Two
 * problems with that: the emoji never reached anybody (the reader's row
 * has drawn its own glyph since the notification rework), and a free
 * slug meant the sender could invent a category no client knows how to
 * render. The sender now picks a category; the design system picks the
 * picture, and the picker shows that picture so there is no surprise.
 */
export const ANNOUNCEMENT_KIND_OPTIONS: AnnouncementKindOption[] =
  ANNOUNCEMENT_KIND_ORDER.map((key) => ({
    key,
    label: ANNOUNCEMENT_KINDS[key].label,
    icon: ANNOUNCEMENT_KINDS[key].icon,
    tone: ANNOUNCEMENT_KINDS[key].tone,
    description: KIND_DESCRIPTIONS[key],
  }));

export const DEFAULT_KIND = "general";

export function kindLabel(key: string): string {
  return ANNOUNCEMENT_KINDS[key]?.label ?? key;
}

export function isKnownKind(key: string): boolean {
  return key in ANNOUNCEMENT_KINDS;
}

/* ------------------------------------------------------------------ */
/* Audiences - mirrors apps/notifications/validators (ADR 0030)        */
/* ------------------------------------------------------------------ */

export type AudienceDoc = {
  kind: string;
  days?: number;
  course_slug?: string;
  level?: string;
  usernames?: string[];
};

export const AUDIENCE_KINDS: {
  key: string;
  label: string;
  description: string;
}[] = [
  { key: "all", label: "ผู้ใช้ทุกคน", description: "ทุกบัญชีที่ยังใช้งานอยู่" },
  { key: "active", label: "ผู้ใช้ที่แอ็กทีฟ", description: "เข้าสู่ระบบภายในช่วงวันที่กำหนด" },
  { key: "new_users", label: "สมาชิกใหม่", description: "สมัครภายในช่วงวันที่กำหนด" },
  { key: "course_enrolled", label: "ผู้เรียนในคอร์ส", description: "ลงทะเบียนหรือเรียนจบคอร์สที่เลือก" },
  { key: "course_completed", label: "ผู้เรียนจบคอร์ส", description: "เรียนจบคอร์สที่เลือกแล้ว" },
  { key: "recipe_creators", label: "ผู้สร้างสูตร", description: "เคยเผยแพร่สูตรอย่างน้อย 1 สูตร" },
  { key: "community_creators", label: "ผู้สร้างในชุมชน", description: "เคยโพสต์ในชุมชนอย่างน้อย 1 โพสต์" },
  { key: "skill_level", label: "ตามระดับฝีมือ", description: "ผู้ใช้ที่ระบุระดับฝีมือที่เลือก" },
  { key: "specific_users", label: "ระบุรายชื่อ", description: "พิมพ์ชื่อผู้ใช้เป็นรายบัญชี" },
];

export const SKILL_LEVELS: { value: string; label: string }[] = [
  { value: "beginner", label: "มือใหม่" },
  { value: "intermediate", label: "ปานกลาง" },
  { value: "advanced", label: "ขั้นสูง" },
  { value: "professional", label: "มืออาชีพ" },
];

/** A one-line Thai summary of an audience document, for tables. */
export function audienceLabel(audience: unknown): string {
  const doc = (audience ?? {}) as AudienceDoc;
  switch (doc.kind) {
    case "all":
      return "ผู้ใช้ทุกคน";
    case "active":
      return `แอ็กทีฟใน ${doc.days ?? 30} วัน`;
    case "new_users":
      return `สมัครใน ${doc.days ?? 30} วัน`;
    case "course_enrolled":
      return `ผู้เรียน: ${doc.course_slug ?? "?"}`;
    case "course_completed":
      return `เรียนจบ: ${doc.course_slug ?? "?"}`;
    case "recipe_creators":
      return "ผู้สร้างสูตร";
    case "community_creators":
      return "ผู้สร้างในชุมชน";
    case "skill_level":
      return (
        "ระดับ" +
        (SKILL_LEVELS.find((level) => level.value === doc.level)?.label ??
          doc.level ??
          "?")
      );
    case "specific_users":
      return `ระบุรายชื่อ (${doc.usernames?.length ?? 0} บัญชี)`;
    default:
      return "-";
  }
}

/* ------------------------------------------------------------------ */
/* Variables                                                           */
/* ------------------------------------------------------------------ */

export type VariableMeta = {
  name: string;
  label: string;
  sample: string;
  /**
   * When delivery can truthfully fill it: every audience, only
   * course-scoped audiences, or never (preview-only - the backend
   * rejects a send that embeds one of these).
   */
  availability: "always" | "course" | "sample_only";
};

export const VARIABLES: VariableMeta[] = [
  { name: "user_name", label: "ชื่อผู้รับ", sample: "มิลด์ รินรดา", availability: "always" },
  { name: "course_name", label: "ชื่อคอร์ส", sample: "ศิลปะการแต่งหน้าเค้กเบื้องต้น", availability: "course" },
  { name: "post_title", label: "ชื่อโพสต์", sample: "ครัวซองต์ฝีมือแรกของฉัน", availability: "sample_only" },
  { name: "recipe_name", label: "ชื่อสูตร", sample: "ชิฟฟ่อนใบเตยนุ่มฟู", availability: "sample_only" },
  { name: "commenter_name", label: "ชื่อผู้คอมเมนต์", sample: "มินตรา อบอุ่น", availability: "sample_only" },
  { name: "like_count", label: "จำนวนถูกใจ", sample: "128", availability: "sample_only" },
  { name: "comment_count", label: "จำนวนคอมเมนต์", sample: "24", availability: "sample_only" },
];

const VARIABLE_PATTERN = /\{\{\s*([a-z_]+)\s*\}\}/g;

const SAMPLE_BY_NAME = new Map(
  VARIABLES.map((variable) => [variable.name, variable.sample]),
);

/** Fill every known variable with its sample value, for previews. */
export function renderSample(text: string): string {
  return text.replace(
    VARIABLE_PATTERN,
    (whole, name: string) => SAMPLE_BY_NAME.get(name) ?? whole,
  );
}

/** The variable names delivery can fill for this audience kind. */
export function resolvableVariables(audienceKind: string): Set<string> {
  const names = new Set(["user_name"]);
  if (audienceKind === "course_enrolled" || audienceKind === "course_completed") {
    names.add("course_name");
  }
  return names;
}

/** Variables embedded in `text` that a send to this audience would reject. */
export function unresolvableIn(text: string, audienceKind: string): string[] {
  const allowed = resolvableVariables(audienceKind);
  const found = new Set<string>();
  for (const match of text.matchAll(VARIABLE_PATTERN)) {
    if (!allowed.has(match[1])) found.add(match[1]);
  }
  return [...found];
}

/* ------------------------------------------------------------------ */
/* Campaign status                                                     */
/* ------------------------------------------------------------------ */

export const CAMPAIGN_STATUS: Record<
  string,
  { label: string; tone: "neutral" | "success" | "warning" | "danger" }
> = {
  draft: { label: "ฉบับร่าง", tone: "warning" },
  scheduled: { label: "ตั้งเวลาไว้", tone: "neutral" },
  sent: { label: "ส่งแล้ว", tone: "success" },
  canceled: { label: "ยกเลิกแล้ว", tone: "danger" },
};
