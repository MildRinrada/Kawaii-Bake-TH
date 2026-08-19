/* eslint-disable @next/next/no-img-element -- media comes from the Django
   origin at arbitrary sizes; next/image would need remote-pattern config
   per deploy and buys little for local dev media */

import { PLACEHOLDER } from "@/lib/assets";
import { cn } from "@/lib/cn";

/** Which stand-in to draw when there is no photo. */
const ART = {
  recipe: PLACEHOLDER.recipeCover,
  course: PLACEHOLDER.courseCover,
  post: PLACEHOLDER.postImage,
} as const;

const TINTS = [
  "bg-berry-soft",
  "bg-peach-soft",
  "bg-butter-soft",
  "bg-lavender-soft",
  "bg-mint-soft",
] as const;

/**
 * Cover-image frame with an honest fallback.
 *
 * Content with no photo gets a soft flavor tint and the matching
 * placeholder illustration from `public/placeholders/`  friendly, but
 * unmistakably a placeholder. The caption is real HTML rather than text
 * baked into the SVG, so it stays legible at thumbnail size and is not
 * announced twice by a screen reader.
 *
 * `seed` only picks the tint. It is deliberately deterministic so the
 * same recipe looks the same on every render and across the list/detail
 * pages.
 */
export function MediaFrame({
  src,
  alt = "",
  seed,
  kind = "recipe",
  className,
  onNaturalSize,
}: {
  src?: string | null;
  alt?: string;
  seed: string;
  kind?: keyof typeof ART;
  className?: string;
  /** The photo's own pixel size, once decoded - for frames that choose
      their aspect from the picture (see `CoverFrame`). */
  onNaturalSize?: (width: number, height: number) => void;
}) {
  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onLoad={
          onNaturalSize
            ? (event) =>
                onNaturalSize(
                  event.currentTarget.naturalWidth,
                  event.currentTarget.naturalHeight,
                )
            : undefined
        }
        className={cn("size-full object-cover", className)}
      />
    );
  }

  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 997;

  return (
    <div
      className={cn(
        "flex size-full flex-col items-center justify-center gap-1 p-3",
        TINTS[hash % TINTS.length],
        className,
      )}
    >
      <img
        src={ART[kind]}
        alt=""
        aria-hidden
        draggable={false}
        className="max-h-[62%] w-auto max-w-[70%] select-none opacity-90"
      />
      <span className="text-center text-xl text-fg-muted">
        ยังไม่มีภาพหน้าปก
      </span>
    </div>
  );
}
