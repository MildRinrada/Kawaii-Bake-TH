/**
 * Thai translations for backend error text.
 *
 * The API speaks English domain messages (single error contract, ADR 0008
 * family); the UI speaks Thai. Codes are stable identifiers so they get
 * first priority; raw DRF/Django validator strings are matched exactly,
 * then by prefix for parameterised messages. Unknown text passes through
 * untranslated  wrong Thai would be worse than English.
 */

const CODE_MESSAGES: Record<string, string> = {
  email_already_registered:
    "อีเมลนี้มีบัญชีอยู่แล้ว  ลองเข้าสู่ระบบ หรือใช้เมนูลืมรหัสผ่าน",
  username_taken: "ชื่อผู้ใช้นี้ถูกใช้แล้ว ลองชื่ออื่นดูนะ",
  invalid_credentials: "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
  account_disabled: "บัญชีนี้ถูกปิดการใช้งาน",
  email_not_verified: "กรุณายืนยันอีเมลก่อนเข้าสู่ระบบ",
  rate_limited: "พยายามหลายครั้งเกินไป กรุณารอสักครู่แล้วลองใหม่",
  invalid_token: "ลิงก์นี้ไม่ถูกต้องหรือหมดอายุแล้ว กรุณาขอลิงก์ใหม่",
};

const EXACT_MESSAGES: Record<string, string> = {
  "This field is required.": "กรุณากรอกข้อมูลนี้",
  "This field may not be blank.": "กรุณากรอกข้อมูลนี้",
  "Enter a valid email address.": "รูปแบบอีเมลไม่ถูกต้อง เช่น name@example.com",
  "This password is too common.":
    "รหัสผ่านนี้เดาง่ายเกินไป ลองผสมคำให้คาดเดายากขึ้น",
  "This password is entirely numeric.": "รหัสผ่านต้องไม่เป็นตัวเลขล้วน",
  "The two password entries do not match.": "รหัสผ่านทั้งสองช่องไม่ตรงกัน",
  "This username is reserved. Please choose another.":
    "ชื่อนี้ถูกสงวนไว้ กรุณาเลือกชื่ออื่น",
  "This username is already taken.": "ชื่อผู้ใช้นี้ถูกใช้แล้ว ลองชื่ออื่นดูนะ",
  "An account with this email address already exists.":
    "อีเมลนี้มีบัญชีอยู่แล้ว  ลองเข้าสู่ระบบ หรือใช้เมนูลืมรหัสผ่าน",
  "Username may only contain lowercase letters, numbers, hyphens and underscores, and must start and end with a letter or number.":
    "ชื่อผู้ใช้ใช้ได้เฉพาะ a-z, 0-9, ขีดกลาง (-) และขีดล่าง (_) และต้องขึ้นต้นและลงท้ายด้วยตัวอักษรหรือตัวเลข",
  // Django's ImageField message. The most common real cause is an iPhone
  // HEIC photo, which the server's Pillow build cannot decode  so the
  // Thai version names that cause instead of restating "invalid".
  "Upload a valid image. The file you uploaded was either not an image or a corrupted image.":
    "ไฟล์นี้ไม่ใช่รูปภาพที่ระบบเปิดได้  ถ้าเป็นรูปจาก iPhone (.HEIC) ให้แปลงเป็น JPG หรือ PNG ก่อน",
  "The submitted file is empty.": "ไฟล์ที่อัปโหลดว่างเปล่า",
};

/** Parameterised messages (lengths, similarity targets) matched by prefix. */
const PREFIX_MESSAGES: Array<[string, string]> = [
  [
    "This password is too short.",
    "รหัสผ่านสั้นเกินไป  ต้องมีอย่างน้อย 10 ตัวอักษร",
  ],
  [
    "The password is too similar to",
    "รหัสผ่านคล้ายกับอีเมลหรือชื่อผู้ใช้ของคุณเกินไป",
  ],
  ["Username must be at least", "ชื่อผู้ใช้ต้องยาวอย่างน้อย 3 ตัวอักษร"],
  ["Username must be at most", "ชื่อผู้ใช้ต้องยาวไม่เกิน 30 ตัวอักษร"],
  ["Ensure this field has at least", "ข้อมูลนี้สั้นเกินไป"],
  ["Ensure this field has no more than", "ข้อมูลนี้ยาวเกินกำหนด"],
];

export function translateMessage(message: string): string {
  const exact = EXACT_MESSAGES[message];
  if (exact) return exact;
  for (const [prefix, thai] of PREFIX_MESSAGES) {
    if (message.startsWith(prefix)) return thai;
  }
  return message;
}

export function translateFormError(code: string, message: string): string {
  return CODE_MESSAGES[code] ?? translateMessage(message);
}

export function translateFieldErrors(
  fieldErrors: Record<string, string[]>,
): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(fieldErrors)) {
    result[field] = messages.map(translateMessage);
  }
  return result;
}
