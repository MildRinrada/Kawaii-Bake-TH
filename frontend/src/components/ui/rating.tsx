"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

/**
 * Star ratings — read-only display and the interactive picker.
 *
 * Two things this component is deliberate about:
 *
 * **Partial stars.** The filled row is drawn over the empty row and
 * clipped to `average / 5`, so 3.5 shows half a star and 4.2 shows what
 * it actually is. Rounding to the nearest whole star told a small lie
 * every time and made every rating look identical.
 *
 * **Few reviews are not a score.** "3.0" beside a recipe reads as a
 * lukewarm verdict from a crowd; with one review there is no crowd, and
 * three filled stars make the recipe look worse than the evidence can
 * support. Under `FEW_REVIEWS` neither the stars nor the average are
 * drawn — the honest reading is "not enough ratings yet, N reviews".
 */

const FEW_REVIEWS = 3;

const SIZES = { sm: "size-3.5", md: "size-4", lg: "size-6" } as const;
type StarSize = keyof typeof SIZES;

/** The gold gradient the earned part of a rating is painted with.
    It sits on the masked glyph itself, not a wrapper — the mask is what
    the paint shows through. */
const GOLD = "bg-linear-to-b from-star to-star-deep";

/** One row of five stars, all in the same state. */
function StarRow({
  size,
  filled,
  tone,
}: {
  size: StarSize;
  filled: boolean;
  tone: string;
}) {
  return (
    <span className="flex">
      {Array.from({ length: 5 }, (_, index) => (
        <Icon
          key={index}
          tint
          name={filled ? "ui/star-filled" : "ui/star"}
          className={cn(SIZES[size], tone)}
        />
      ))}
    </span>
  );
}

export function Stars({
  value,
  size = "md",
  className,
}: {
  /** 0–5; any fraction is honoured, not rounded. */
  value: number;
  size?: StarSize;
  className?: string;
}) {
  const percent = Math.max(0, Math.min(100, (value / 5) * 100));
  return (
    <span aria-hidden className={cn("relative inline-flex shrink-0", className)}>
      <StarRow size={size} filled={false} tone="text-star-empty" />
      <span
        className="absolute inset-y-0 left-0 overflow-hidden"
        style={{ width: `${percent}%` }}
      >
        <StarRow size={size} filled tone={GOLD} />
      </span>
    </span>
  );
}

/**
 * Read-only star rating with an accessible text alternative.
 */
export function Rating({
  average,
  count,
  size = "md",
  className,
}: {
  average: number | string | null;
  count?: number;
  size?: StarSize;
  className?: string;
}) {
  const parsed = average === null ? null : Number(average);
  const value = parsed === null || Number.isNaN(parsed) ? null : parsed;
  const few = count !== undefined && count > 0 && count < FEW_REVIEWS;
  const none = value === null || count === 0;

  return (
    <span
      className={cn("inline-flex items-center gap-1.5 text-sm", className)}
      aria-label={
        none
          ? "ยังไม่มีคะแนนรีวิว"
          : count === undefined
            ? `${value!.toFixed(1)} จาก 5 ดาว`
            : `คะแนนเฉลี่ย ${value!.toFixed(1)} จาก 5 จาก ${count} รีวิว`
      }
    >
      {none || few ? null : <Stars value={value!} size={size} />}
      {none ? (
        <span aria-hidden className="text-fg-subtle">
          ยังไม่มีรีวิว
        </span>
      ) : few ? (
        // One or two voices are not a score. Three filled stars from a
        // single review make a recipe look mediocre on evidence that
        // cannot support the claim, so the stars are withheld until
        // there is a crowd to average.
        <span aria-hidden className="text-fg-muted">
          ยังมีคะแนนไม่พอ · {count} รีวิว
        </span>
      ) : (
        <>
          <span aria-hidden className="font-medium text-fg">
            {value!.toFixed(1)}
          </span>
          {count !== undefined ? (
            <span aria-hidden className="text-fg-subtle">
              ({count})
            </span>
          ) : null}
        </>
      )}
    </span>
  );
}

/**
 * The interactive picker: same gold, with a hover preview so the choice
 * is visible before it is committed.
 */
export function StarPicker({
  value,
  onChange,
  label = "ให้คะแนน",
}: {
  value: number;
  onChange: (value: number) => void;
  label?: string;
}) {
  const [hovered, setHovered] = useState(0);
  const shown = hovered || value;

  return (
    <span
      role="radiogroup"
      aria-label={label}
      className="inline-flex items-center gap-0.5"
      onMouseLeave={() => setHovered(0)}
    >
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          role="radio"
          aria-checked={value === star}
          aria-label={`${star} ดาว`}
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onFocus={() => setHovered(star)}
          onBlur={() => setHovered(0)}
          className="rounded-full p-1 transition-transform hover:scale-110 focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon
            tint
            name={star <= shown ? "ui/star-filled" : "ui/star"}
            className={cn("size-7", star <= shown ? GOLD : "text-star-empty")}
          />
        </button>
      ))}
    </span>
  );
}
