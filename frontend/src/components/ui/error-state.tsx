"use client";

import { Button } from "@/components/ui/button";
import { ApiError, NetworkError } from "@/lib/api/errors";

/**
 * Designed error states in the KawaiiBake voice — HTTP families get
 * friendly Thai copy and a fitting glyph, never a browser default.
 */
function describe(error: Error | null): { icon: string; title: string; detail?: string } {
  if (error instanceof NetworkError) {
    return { icon: "🔌", title: "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", detail: "ตรวจสอบการเชื่อมต่อ แล้วลองใหม่อีกครั้ง" };
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return { icon: "🔐", title: "กรุณาเข้าสู่ระบบก่อน", detail: "หน้านี้ต้องเข้าสู่ระบบเพื่อใช้งาน" };
    }
    if (error.status === 403) {
      return { icon: "🙈", title: "ยังเข้าถึงส่วนนี้ไม่ได้", detail: error.message };
    }
    if (error.status === 404) {
      return { icon: "🍪", title: "ไม่พบสิ่งที่ตามหา", detail: "อาจถูกลบไปแล้ว หรือลิงก์ไม่ถูกต้อง" };
    }
    if (error.status === 409) {
      return { icon: "⏳", title: "ทำรายการไม่ได้ในตอนนี้", detail: error.message };
    }
    return { icon: "😿", title: "เกิดข้อผิดพลาด", detail: error.message };
  }
  return { icon: "😿", title: "เกิดข้อผิดพลาด", detail: "กรุณาลองใหม่อีกครั้ง" };
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error | null;
  onRetry?: () => void;
}) {
  const { icon, title, detail } = describe(error);
  return (
    <div role="alert" className="flex flex-col items-center gap-3 py-14 text-center">
      <span
        aria-hidden
        className="flex size-16 items-center justify-center rounded-full bg-danger-subtle text-3xl"
      >
        {icon}
      </span>
      <p className="font-display text-base font-medium text-fg">{title}</p>
      {detail ? <p className="max-w-sm text-sm text-fg-muted">{detail}</p> : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-1">
          ลองอีกครั้ง
        </Button>
      ) : null}
    </div>
  );
}
