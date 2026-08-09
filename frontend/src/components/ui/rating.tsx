import { cn } from "@/lib/cn";

/**
 * Read-only star rating. Butter-toned stars, accessible text alternative.
 */
export function Rating({
  average,
  count,
  className,
}: {
  average: number | string | null;
  count?: number;
  className?: string;
}) {
  const value = average === null ? null : Number(average);
  const rounded = value === null ? 0 : Math.round(value);

  return (
    <span
      className={cn("inline-flex items-center gap-1 text-sm", className)}
      aria-label={
        value === null
          ? "ยังไม่มีคะแนนรีวิว"
          : `คะแนนเฉลี่ย ${value.toFixed(1)} จาก 5${count !== undefined ? ` (${count} รีวิว)` : ""}`
      }
    >
      <span aria-hidden className="tracking-tight text-butter-ink">
        {Array.from({ length: 5 }, (_, index) =>
          index < rounded ? "★" : "☆",
        ).join("")}
      </span>
      {value !== null ? (
        <span aria-hidden className="font-medium text-fg">
          {value.toFixed(1)}
        </span>
      ) : null}
      {count !== undefined ? (
        <span aria-hidden className="text-fg-subtle">
          ({count})
        </span>
      ) : null}
    </span>
  );
}
