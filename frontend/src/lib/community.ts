/**
 * Community (gallery) constants and client-side upload rules.
 *
 * The image limits mirror `apps/gallery/constants.py` exactly. They are
 * duplicated here on purpose and only as a *pre-check*: rejecting a
 * 12 MB HEIC before the upload starts is far kinder than a round trip,
 * but the server remains the authority and its refusal is always shown.
 */

/** How many attached posts a recipe page shows before "see all". */
export const MAX_RECIPE_COMMUNITY_POSTS = 5;

/** `MAX_IMAGES_PER_POST` in the gallery app. */
export const MAX_IMAGES_PER_POST = 10;

/** `GALLERY_IMAGE_MAX_SIZE_BYTES` in the gallery app. */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

/** `ALLOWED_GALLERY_IMAGE_EXTENSIONS` — SVG is excluded project-wide. */
export const ALLOWED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
] as const;

export const ALLOWED_IMAGE_LABEL = "JPG · PNG · WebP (ไม่เกิน 5 MB ต่อรูป)";

/**
 * Return a Thai reason this file cannot be uploaded, or `null` when it
 * passes the checks the server would apply.
 */
export function describeImageProblem(file: File): string | null {
  if (/\.(heic|heif)$/i.test(file.name)) {
    return "ไฟล์ .HEIC/.HEIF จาก iPhone ยังอัปโหลดไม่ได้ — แปลงเป็น JPG หรือ PNG ก่อนนะ";
  }
  if (!ALLOWED_IMAGE_TYPES.includes(file.type as (typeof ALLOWED_IMAGE_TYPES)[number])) {
    return `รองรับเฉพาะ ${ALLOWED_IMAGE_LABEL} — ไฟล์นี้เป็น ${file.type || "ชนิดที่ไม่รู้จัก"}`;
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return `รูปใหญ่เกิน 5 MB (ไฟล์นี้ ${(file.size / 1024 / 1024).toFixed(1)} MB)`;
  }
  return null;
}
