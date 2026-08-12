/* eslint-disable @next/next/no-img-element -- fixed local photos under
   public/category/, sized per call site; next/image buys nothing here */

/**
 * Category photography, in the two shapes it appears in.
 *
 * `CategoryThumb` is a small flat-colour glyph for inline chips/pills 
 * a photo crop reads as noise at 20px, so it uses the category icon set
 * instead of `categoryArt`'s photography.
 *
 * `CategoryTile` is the "explore by category" unit: a fixed-size square
 * that always fills itself (`object-cover`) regardless of the source
 * photo's own aspect ratio  cropping is accepted on purpose so every
 * tile in a row lines up. A gentle zoom plays on hover/focus, respecting
 * `prefers-reduced-motion`.
 */

import Link from "next/link";
import type { Route } from "next";

import { categoryArt, categoryIcon } from "@/lib/assets";
import { cn } from "@/lib/cn";

export function CategoryThumb({
  slug,
  className,
}: {
  slug: string;
  className?: string;
}) {
  return (
    <img
      src={categoryIcon(slug)}
      alt=""
      aria-hidden
      draggable={false}
      className={cn("size-5 shrink-0 object-contain", className)}
    />
  );
}

export function CategoryTile({
  slug,
  name,
  count,
  countLabel = "สูตร",
  href,
  active,
  onClick,
  /** An empty category leads nowhere - the tile stays visible as
   *  information but stops behaving like a control. */
  disabled,
  /** Small fixed-width tile for a horizontal-scroll row (quick filters)
   *  instead of a full-width grid cell (the "explore" section). */
  compact,
  /** `square` (default) for filter rows; `landscape` for the home page's
   *  "explore by category" grid, which wants width over height. */
  aspect = "square",
  /** A photo uploaded by staff (`Category.image_url`); the built-in
   *  slug-mapped artwork remains the fallback, so a fresh database with
   *  no uploads still looks finished. */
  imageUrl,
  className,
}: {
  slug: string;
  name: string;
  /** A count shown under the name, when the caller has one. */
  count?: number;
  /** Unit for `count`  recipes, posts, whatever the caller is counting. */
  countLabel?: string;
  /** Renders an `<a>` when given; otherwise a `<button>` for onClick. */
  href?: Route;
  active?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  compact?: boolean;
  aspect?: "square" | "landscape";
  imageUrl?: string | null;
  className?: string;
}) {
  const content = (
    <>
      <img
        src={imageUrl || categoryArt(slug)}
        alt=""
        aria-hidden
        draggable={false}
        className="absolute inset-0 size-full object-cover transition-transform duration-300 ease-out motion-safe:group-hover:scale-110 motion-safe:group-focus-visible:scale-110"
      />
      {/* Strong enough that white text survives even a bright, busy
          photo - the top half stays clear so the image still reads. */}
      <div
        aria-hidden
        className="absolute inset-0 bg-linear-to-t from-black/70 via-black/25 to-black/0"
      />
      <span
        className={cn(
          "relative flex h-full flex-col justify-end text-left text-fg-inverted",
          compact ? "p-1.5" : "p-2.5",
        )}
      >
        <span
          className={cn(
            "font-display font-medium drop-shadow-sm",
            compact ? "line-clamp-1 text-xs" : "text-sm sm:text-base",
          )}
        >
          {name}
        </span>
        {count !== undefined ? (
          <span
            className={cn(
              "text-fg-inverted/85",
              compact ? "text-[10px]" : "text-xs",
            )}
          >
            {count} {countLabel}
          </span>
        ) : null}
      </span>
    </>
  );

  const shared = cn(
    "group relative overflow-hidden rounded-surface shadow-raised transition-shadow duration-150",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
    aspect === "landscape" ? "aspect-4/3" : "aspect-square",
    compact ? "w-20 shrink-0 snap-start sm:w-24" : "w-full",
    disabled
      ? "cursor-not-allowed opacity-40 shadow-none"
      : "hover:shadow-overlay",
    active && "outline-2 outline-offset-2 outline-focus",
    className,
  );

  if (href) {
    return (
      <Link
        href={href}
        aria-current={active ? "true" : undefined}
        aria-disabled={disabled || undefined}
        // A dead link is worse than no link: an empty category cannot
        // be navigated into at all.
        onClick={disabled ? (event) => event.preventDefault() : undefined}
        tabIndex={disabled ? -1 : undefined}
        className={shared}
      >
        {content}
      </Link>
    );
  }
  return (
    <button
      type="button"
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={shared}
    >
      {content}
    </button>
  );
}
