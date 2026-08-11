/**
 * The notification-composer catalog: what a notification can be about,
 * who it can target, and which `{{variables}}` are honest to use.
 *
 * Everything here is presentation data. The backend keeps the real
 * contracts: `kind` is a free (validated) slug so new types are a
 * catalog entry, not a migration; audiences and variables are closed
 * server-side and this file only mirrors those rules for the UI.
 */

export type KindCategory = {
  key: string;
  label: string;
};

export type NotificationKind = {
  key: string;
  category: string;
  label: string;
  description: string;
  icon: string;
};

export const KIND_CATEGORIES: KindCategory[] = [
  { key: "social", label: "โซเชียล" },
  { key: "learning", label: "การเรียน" },
  { key: "recipe", label: "สูตรอาหาร" },
  { key: "community", label: "ชุมชน" },
  { key: "achievement", label: "ความสำเร็จ" },
  { key: "system", label: "ระบบ" },
  { key: "custom", label: "กำหนดเอง" },
];

/**
 * The kind catalog. Add entries freely - the backend accepts any
 * `[a-z0-9_]+` slug, so a new type is one line here.
 */
export const NOTIFICATION_KINDS: NotificationKind[] = [
  // Social
  { key: "post_liked", category: "social", label: "มีคนถูกใจโพสต์", description: "โพสต์ของผู้ใช้ได้รับการถูกใจ", icon: "💖" },
  { key: "post_commented", category: "social", label: "มีคอมเมนต์ใหม่", description: "มีคนคอมเมนต์โพสต์ของผู้ใช้", icon: "💬" },
  { key: "post_bookmarked", category: "social", label: "โพสต์ถูกบันทึก", description: "มีคนบันทึกโพสต์เก็บไว้", icon: "🔖" },
  { key: "new_follower", category: "social", label: "มีผู้ติดตามใหม่", description: "มีคนติดตามผู้ใช้", icon: "✨" },
  { key: "post_viral", category: "social", label: "โพสต์กำลังไวรัล", description: "โพสต์ได้รับความนิยมสูงผิดปกติ", icon: "🎉" },
  { key: "comment_replied", category: "social", label: "มีคนตอบคอมเมนต์", description: "คอมเมนต์ของผู้ใช้ได้รับการตอบกลับ", icon: "↩️" },
  // Learning
  { key: "course_update", category: "learning", label: "คอร์สอัปเดต", description: "เนื้อหาในคอร์สมีการเปลี่ยนแปลง", icon: "📚" },
  { key: "new_lesson", category: "learning", label: "บทเรียนใหม่", description: "คอร์สเพิ่มบทเรียนใหม่", icon: "🆕" },
  { key: "quiz_result", category: "learning", label: "ผลแบบทดสอบ", description: "ประกาศผลแบบทดสอบ", icon: "📝" },
  { key: "course_completed", category: "learning", label: "เรียนจบคอร์ส", description: "แสดงความยินดีกับผู้เรียนจบ", icon: "🎓" },
  { key: "certificate_ready", category: "learning", label: "ใบประกาศพร้อมแล้ว", description: "ใบประกาศนียบัตรพร้อมให้ดาวน์โหลด", icon: "📜" },
  { key: "learning_reminder", category: "learning", label: "เตือนกลับมาเรียน", description: "ชวนผู้เรียนกลับมาเรียนต่อ", icon: "⏰" },
  // Recipe
  { key: "new_recipe", category: "recipe", label: "สูตรใหม่", description: "มีสูตรอาหารใหม่น่าสนใจ", icon: "🧁" },
  { key: "recipe_updated", category: "recipe", label: "สูตรอัปเดต", description: "สูตรที่ติดตามมีการปรับปรุง", icon: "🔄" },
  { key: "recipe_featured", category: "recipe", label: "สูตรถูกแนะนำ", description: "สูตรของผู้ใช้ถูกคัดเป็นสูตรเด่น", icon: "🌟" },
  { key: "recipe_recommendation", category: "recipe", label: "สูตรแนะนำสำหรับคุณ", description: "แนะนำสูตรที่น่าจะถูกใจ", icon: "🍰" },
  // Community
  { key: "community_announcement", category: "community", label: "ประกาศชุมชน", description: "ข่าวสารถึงสมาชิกชุมชน", icon: "📣" },
  { key: "community_event", category: "community", label: "กิจกรรมชุมชน", description: "ชวนร่วมกิจกรรมหรือชาเลนจ์", icon: "🎪" },
  { key: "qa_activity", category: "community", label: "ความเคลื่อนไหวถามตอบ", description: "มีความเคลื่อนไหวในกระทู้ถามตอบ", icon: "❓" },
  { key: "moderation_notice", category: "community", label: "แจ้งจากทีมดูแล", description: "การแจ้งเตือนจากทีมดูแลชุมชน", icon: "🛡️" },
  // Achievement
  { key: "achievement_unlocked", category: "achievement", label: "ปลดล็อกความสำเร็จ", description: "ผู้ใช้ทำภารกิจสำเร็จ", icon: "🏆" },
  { key: "new_badge", category: "achievement", label: "ได้รับเหรียญใหม่", description: "มีเหรียญตราใหม่ในคอลเลกชัน", icon: "🎖️" },
  { key: "milestone_reached", category: "achievement", label: "ถึงหมุดหมายสำคัญ", description: "ครบยอดสำคัญ เช่น สูตรที่ 100", icon: "🚩" },
  // System
  { key: "platform_update", category: "system", label: "แพลตฟอร์มอัปเดต", description: "ฟีเจอร์ใหม่หรือการเปลี่ยนแปลงระบบ", icon: "🛠️" },
  { key: "maintenance", category: "system", label: "ปิดปรับปรุงระบบ", description: "แจ้งช่วงเวลาปิดปรับปรุง", icon: "🚧" },
  { key: "announcement", category: "system", label: "ประกาศสำคัญ", description: "ประกาศถึงผู้ใช้ทั้งแพลตฟอร์ม", icon: "📢" },
  // Custom
  { key: "custom", category: "custom", label: "กำหนดเอง", description: "เขียนการแจ้งเตือนอิสระ", icon: "🍒" },
];

export const KIND_BY_KEY = new Map(
  NOTIFICATION_KINDS.map((kind) => [kind.key, kind]),
);

export function kindLabel(key: string): string {
  return KIND_BY_KEY.get(key)?.label ?? key;
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
