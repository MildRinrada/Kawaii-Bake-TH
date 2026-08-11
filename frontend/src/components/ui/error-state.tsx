"use client";

import { MODAL_ART } from "@/lib/assets";
import { Button } from "@/components/ui/button";
import { ArtIcon } from "@/components/ui/icon";
import { ApiError, NetworkError } from "@/lib/api/errors";

/**
 * Designed error states in the KawaiiBake voice  HTTP families get
 * friendly Thai copy and matching status art from `public/icons/modal/`,
 * never a browser default.
 *
 * The art is chosen by what the reader can *do* about it: a locked door
 * for "sign in" and "not yours", an informational mark for "not found"
 * (nothing is broken), a warning for a conflict that may resolve, and
 * the error mark only for genuine failures.
 */
function describe(
  error: Error | null,
): { art: string; title: string; detail?: string } {
  if (error instanceof NetworkError) {
    return {
      art: MODAL_ART.error,
      title: "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้",
      detail: "ตรวจสอบการเชื่อมต่อ แล้วลองใหม่อีกครั้ง",
    };
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return {
        art: MODAL_ART.locked,
        title: "กรุณาเข้าสู่ระบบก่อน",
        detail: "หน้านี้ต้องเข้าสู่ระบบเพื่อใช้งาน",
      };
    }
    if (error.status === 403) {
      return {
        art: MODAL_ART.locked,
        title: "ยังเข้าถึงส่วนนี้ไม่ได้",
        detail: error.message,
      };
    }
    if (error.status === 404) {
      return {
        art: MODAL_ART.info,
        title: "ไม่พบสิ่งที่ตามหา",
        detail: "อาจถูกลบไปแล้ว หรือลิงก์ไม่ถูกต้อง",
      };
    }
    if (error.status === 409) {
      return {
        art: MODAL_ART.warning,
        title: "ทำรายการไม่ได้ในตอนนี้",
        detail: error.message,
      };
    }
    return { art: MODAL_ART.error, title: "เกิดข้อผิดพลาด", detail: error.message };
  }
  return {
    art: MODAL_ART.error,
    title: "เกิดข้อผิดพลาด",
    detail: "กรุณาลองใหม่อีกครั้ง",
  };
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error | null;
  onRetry?: () => void;
}) {
  const { art, title, detail } = describe(error);
  return (
    <div role="alert" className="flex flex-col items-center gap-3 py-14 text-center">
      <ArtIcon src={art} className="size-16" />
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
