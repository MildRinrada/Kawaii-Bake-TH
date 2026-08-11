/**
 * The certificate design document — the client twin of the backend
 * validator (`apps/certificates/validators/template_validator.py`).
 *
 * A design is data, never markup: elements carry typed style values the
 * renderer turns into React inline styles, so nothing in a document can
 * smuggle HTML anywhere.
 */

import { BRAND_MARK, badgeArt } from "@/lib/assets";

export type ElementKind = "field" | "text" | "image" | "signature" | "box";

export type FieldKey =
  | "recipient_first_name"
  | "recipient_last_name"
  | "recipient_full_name"
  | "course_name"
  | "course_description"
  | "completion_date"
  | "certificate_id"
  | "instructor_name"
  | "instructor_title"
  | "course_duration"
  | "achievement_text";

export interface ElementStyle {
  fontFamily?: "display" | "sans" | "serif" | "mono";
  fontSize?: number;
  fontWeight?: number;
  lineHeight?: number;
  letterSpacing?: number;
  align?: "left" | "center" | "right";
  color?: string;
  background?: string;
  borderWidth?: number;
  borderColor?: string;
  borderRadius?: number;
  shadow?: boolean;
  fit?: "contain" | "cover";
}

export interface SignatureConfig {
  name: string;
  title: string;
  organization: string;
  image: string;
}

export interface DesignElement {
  id: string;
  kind: ElementKind;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  rotation: number;
  opacity: number;
  z: number;
  locked: boolean;
  hidden: boolean;
  field?: FieldKey;
  text?: string;
  src?: string;
  signature?: SignatureConfig;
  style: ElementStyle;
}

export interface DesignDoc {
  size: { width: number; height: number };
  background: string;
  elements: DesignElement[];
}

export const MAX_SIGNATURES = 3;
export const CANVAS_GRID = 4;

/* ------------------------------------------------------------------ */
/* Dynamic fields: labels + realistic sample data                      */
/* ------------------------------------------------------------------ */

export interface SampleData {
  label: string;
  values: Record<FieldKey, string>;
}

export const SAMPLES: SampleData[] = [
  {
    label: "ตัวอย่าง 1",
    values: {
      recipient_first_name: "มิลด์",
      recipient_last_name: "รินรดา",
      recipient_full_name: "มิลด์ รินรดา",
      course_name: "Advanced Baking Fundamentals",
      course_description: "หลักสูตรพื้นฐานการอบขั้นสูงสำหรับผู้เริ่มจริงจัง",
      completion_date: "11 August 2026",
      certificate_id: "KB-2026-000001",
      instructor_name: "มะปราง จันทร์หอม",
      instructor_title: "Head Instructor",
      course_duration: "12 ชั่วโมง",
      achievement_text: "สำเร็จหลักสูตรด้วยความมุ่งมั่นและตั้งใจ",
    },
  },
  {
    label: "ตัวอย่าง 2",
    values: {
      recipient_first_name: "มินตรา",
      recipient_last_name: "อบอุ่น",
      recipient_full_name: "มินตรา อบอุ่น",
      course_name: "ศิลปะการแต่งหน้าเค้กเบื้องต้น",
      course_description: "จากเค้กเปล่าเปลือยสู่หน้าเค้กที่เล่าเรื่องได้",
      completion_date: "1 กันยายน 2026",
      certificate_id: "KB-2026-000042",
      instructor_name: "รินรดา ลายอัด",
      instructor_title: "Pastry Instructor",
      course_duration: "8 ชั่วโมง",
      achievement_text: "ผ่านทุกบทเรียนและแบบทดสอบครบถ้วน",
    },
  },
];

export const FIELD_LABELS: Record<FieldKey, string> = {
  recipient_first_name: "ชื่อผู้รับ (ชื่อจริง)",
  recipient_last_name: "นามสกุลผู้รับ",
  recipient_full_name: "ชื่อ-นามสกุลผู้รับ",
  course_name: "ชื่อคอร์ส",
  course_description: "คำอธิบายคอร์ส",
  completion_date: "วันที่เรียนจบ",
  certificate_id: "เลขที่ใบประกาศ",
  instructor_name: "ชื่อผู้สอน",
  instructor_title: "ตำแหน่งผู้สอน",
  course_duration: "ระยะเวลาคอร์ส",
  achievement_text: "ข้อความความสำเร็จ",
};

export const FIELD_KEYS = Object.keys(FIELD_LABELS) as FieldKey[];

/* ------------------------------------------------------------------ */
/* Branding asset library (existing public art only)                   */
/* ------------------------------------------------------------------ */

export const BRAND_ASSETS: Array<{ label: string; src: string }> = [
  { label: "โลโก้ KawaiiBake", src: BRAND_MARK },
  { label: "ตราความสำเร็จ", src: badgeArt("course_completed", true) },
  { label: "ตราคอร์สแรก", src: badgeArt("first_course", true) },
  { label: "ภาพขนมปัง", src: "/category/bread.jpg" },
  { label: "ภาพเค้ก", src: "/category/cake.jpg" },
  { label: "ภาพมาการอง", src: "/category/macarons.jpg" },
];

/* ------------------------------------------------------------------ */
/* Documents + element factories                                       */
/* ------------------------------------------------------------------ */

let counter = 0;
export function freshId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}${counter}`;
}

export const BLANK_DESIGN: DesignDoc = {
  size: { width: 1123, height: 794 },
  background: "#fffaf3",
  elements: [],
};

function baseElement(kind: ElementKind, name: string): DesignElement {
  return {
    id: freshId(kind),
    kind,
    name,
    x: 411,
    y: 340,
    w: 300,
    h: 48,
    rotation: 0,
    opacity: 1,
    z: 0,
    locked: false,
    hidden: false,
    style: {},
  };
}

export function makeField(field: FieldKey): DesignElement {
  return {
    ...baseElement("field", FIELD_LABELS[field]),
    field,
    style: { fontSize: 24, align: "center", color: "#3d2c33" },
  };
}

export function makeText(): DesignElement {
  return {
    ...baseElement("text", "ข้อความ"),
    text: "ข้อความใหม่",
    style: { fontSize: 20, align: "center", color: "#3d2c33" },
  };
}

export function makeImage(src: string, label: string): DesignElement {
  return {
    ...baseElement("image", label),
    src,
    x: 481,
    y: 80,
    w: 160,
    h: 160,
    style: { fit: "contain" },
  };
}

export function makeBox(): DesignElement {
  return {
    ...baseElement("box", "กล่องตกแต่ง"),
    x: 361,
    y: 300,
    w: 400,
    h: 120,
    style: {
      background: "#fdeef2",
      borderWidth: 0,
      borderColor: "#e7b8c4",
      borderRadius: 12,
    },
  };
}

export function makeSignature(index: number): DesignElement {
  return {
    ...baseElement("signature", `ลายเซ็น ${index}`),
    x: 120 + (index - 1) * 320,
    y: 600,
    w: 280,
    h: 110,
    signature: { name: "ชื่อผู้ลงนาม", title: "ตำแหน่ง", organization: "", image: "" },
    style: { fontSize: 14, align: "center", color: "#3d2c33" },
  };
}

export function signatureCount(doc: DesignDoc): number {
  return doc.elements.filter((element) => element.kind === "signature").length;
}

/** Elements in paint order (stable for equal z). */
export function paintOrder(doc: DesignDoc): DesignElement[] {
  return [...doc.elements].sort((a, b) => a.z - b.z);
}
