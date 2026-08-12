"use client";

import { useState } from "react";

import { MediaFrame } from "@/components/content/media-frame";
import { cn } from "@/lib/cn";

/**
 * A detail-page cover that fits the photo instead of trimming it.
 *
 * One upload serves both the card and this frame, so the frame has to
 * bend rather than the picture: a wide banner (the old 21:9) sliced a
 * 4:3 food photo down to its middle band and threw away the plate. Here
 * the frame takes the card's own 4:3 — the crop the author already
 * approved — and switches to 3:4 when the file is portrait, which is
 * what a phone camera hands you. Either way `object-cover` has almost
 * nothing left to cut.
 *
 * The orientation is read from the decoded image, so it costs no extra
 * request and needs no field on the model. Until it loads (or when
 * there is no photo at all) the landscape frame holds the space, which
 * is the common case and keeps the layout from jumping.
 */
/** Width ÷ height of a landscape cover. The upload cropper targets this
    exact number, and the card and this frame both draw it, so a photo
    approved once is never re-cropped by a later layout. Keep it in step
    with the `aspect-4/3` class below. */
export const COVER_ASPECT = 4 / 3;

export function CoverFrame({
  src,
  alt,
  seed,
  kind = "recipe",
  className,
}: {
  src?: string | null;
  alt?: string;
  seed: string;
  kind?: "recipe" | "course" | "post";
  className?: string;
}) {
  const [portrait, setPortrait] = useState(false);

  return (
    <div
      className={cn(
        "mx-auto overflow-hidden rounded-surface border border-edge shadow-raised",
        // Both orientations are capped at the same height (the width is
        // what gets limited, so the ratio is never broken): a phone
        // photo would otherwise stand 650px tall and push everything
        // beside it into a column of empty space.
        portrait
          ? "aspect-3/4 w-full max-w-72"
          : "aspect-4/3 w-full max-w-lg",
        className,
      )}
    >
      <MediaFrame
        src={src}
        alt={alt}
        seed={seed}
        kind={kind}
        onNaturalSize={(width, height) => setPortrait(height > width * 1.05)}
      />
    </div>
  );
}
