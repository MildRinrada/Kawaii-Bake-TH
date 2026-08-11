"use client";

/**
 * Shared helpers for the three content apps that expose the same
 * `publish | unpublish | archive` lifecycle (recipes, courses, quizzes).
 *
 * The backend is authoritative: these helpers only call it and translate
 * its refusal. Notably `*_not_publishable` returns **every** unmet
 * requirement in `details`, so the admin sees a checklist rather than
 * one blocker per attempt.
 */

import { api } from "@/lib/api/client";
import { ApiError, NetworkError } from "@/lib/api/errors";

export type Transition = "publish" | "unpublish" | "archive";

export const TRANSITION_LABELS: Record<Transition, string> = {
  publish: "เผยแพร่",
  unpublish: "ถอนกลับเป็นฉบับร่าง",
  archive: "เก็บเข้าคลัง",
};

export async function runTransition(
  basePath: string,
  slug: string,
  transition: Transition,
): Promise<void> {
  await api.post(`${basePath}/${slug}/${transition}/`);
}

/** Turn any backend refusal into one line an operator can act on. */
export function describeAdminError(error: unknown): string {
  if (error instanceof ApiError) {
    const detailLines = Object.entries(error.details).flatMap(([field, messages]) =>
      (Array.isArray(messages) ? messages : [String(messages)]).map((message) =>
        field === "non_field_errors" ? String(message) : `${field}: ${message}`,
      ),
    );
    const head =
      error.status === 403
        ? "ไม่มีสิทธิ์ทำรายการนี้ (403)"
        : error.status === 404
          ? "ไม่พบรายการนี้ หรือคุณไม่มีสิทธิ์เห็นมัน (404)"
          : error.status === 409
            ? `ทำรายการไม่ได้เพราะสถานะขัดกัน (409)  ${error.message}`
            : error.message;
    return detailLines.length ? `${head}  ${detailLines.join(" · ")}` : head;
  }
  if (error instanceof NetworkError) return "เชื่อมต่อระบบหลังบ้านไม่ได้";
  return "เกิดข้อผิดพลาดที่ไม่คาดคิด";
}
