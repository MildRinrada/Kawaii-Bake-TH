/* eslint-disable @next/next/no-img-element -- media comes from the Django
   origin at arbitrary sizes; next/image would need remote-pattern config
   per deploy and buys little for local dev media */

import { cn } from "@/lib/cn";

const FALLBACK_GLYPHS = ["🍰", "🥐", "🍞", "🧁", "🍪", "🥧"];

/**
 * Cover-image frame with a warm bakery fallback: content without a photo
 * gets a soft flavor dish and a deterministic pastry glyph instead of a
 * gray box — friendly, never fake imagery.
 */
export function MediaFrame({
  src,
  alt = "",
  seed,
  className,
}: {
  src?: string | null;
  alt?: string;
  seed: string;
  className?: string;
}) {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  const glyph = FALLBACK_GLYPHS[hash % FALLBACK_GLYPHS.length];
  const soft = ["bg-berry-soft", "bg-peach-soft", "bg-butter-soft", "bg-lavender-soft", "bg-mint-soft"][hash % 5];

  return src ? (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={cn("size-full object-cover", className)}
    />
  ) : (
    <div
      aria-hidden
      className={cn(
        "flex size-full items-center justify-center text-4xl",
        soft,
        className,
      )}
    >
      {glyph}
    </div>
  );
}
