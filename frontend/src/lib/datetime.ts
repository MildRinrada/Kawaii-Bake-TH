/**
 * Thai time formatting for timelines.
 *
 * Callers render these on the client only (after data arrives), so the
 * `Date.now()` read cannot produce a server/client hydration mismatch.
 */

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "เมื่อสักครู่" / "3 ชั่วโมงที่แล้ว" / "12 มี.ค. 2569" for older events. */
export function relativeThai(iso: string): string {
  const elapsed = Date.now() - new Date(iso).getTime();
  if (elapsed < MINUTE) return "เมื่อสักครู่";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} นาทีที่แล้ว`;
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)} ชั่วโมงที่แล้ว`;
  if (elapsed < 7 * DAY) return `${Math.floor(elapsed / DAY)} วันที่แล้ว`;
  if (elapsed < 30 * DAY) return `${Math.floor(elapsed / (7 * DAY))} สัปดาห์ที่แล้ว`;
  return new Date(iso).toLocaleDateString("th-TH", { dateStyle: "medium" });
}

/** "สิงหาคม 2569" — the granularity a join date deserves. */
export function monthYearThai(iso: string): string {
  return new Date(iso).toLocaleDateString("th-TH", {
    month: "long",
    year: "numeric",
  });
}
