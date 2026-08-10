/* eslint-disable @next/next/no-img-element -- these are fixed-size local SVGs
   from public/; next/image would add a loader round-trip and buy nothing */

/**
 * The two ways KawaiiBake draws an icon.
 *
 * `Icon` takes a name from the library under `public/icons/` and draws
 * the file **as authored** — the artwork is full-colour, so painting it
 * a single flat colour would throw away the thing that makes it good.
 * `ArtIcon` does the same for art addressed by path rather than by name
 * (badges, modal status art). See `public/README.md`.
 *
 * ## Tinting
 *
 * A tinted icon is drawn as a CSS mask over `currentColor`, so the glyph
 * inherits text colour the way it would in an icon font. That throws the
 * artwork's own colours away, which is only ever right for the glyphs
 * that *have* no meaningful colour — a plain star, a slider, a
 * paperclip. Those are listed in `MASKABLE` and tint automatically, so
 * no call site has to remember.
 *
 * The `tint` prop overrides that per call: `true` forces the mask (an
 * icon on a background its own colours would vanish into), `false`
 * forces the original artwork.
 */

import type { CSSProperties } from "react";

import { cn } from "@/lib/cn";

export type UiIconName =
  | "alert"
  | "arrow-down"
  | "arrow-left"
  | "arrow-right"
  | "bell"
  | "book"
  | "book-open"
  | "bookmark"
  | "bowl"
  | "camera"
  | "chat"
  | "check"
  | "check-circle"
  | "chef-hat"
  | "chevron-down"
  | "chevron-right"
  | "clock"
  | "close"
  | "copy"
  | "croissant"
  | "download"
  | "edit"
  | "eye"
  | "eye-off"
  | "filter"
  | "fire"
  | "flower"
  | "gift"
  | "graduation"
  | "heart"
  | "heart-filled"
  | "heart-filled-2"
  | "home"
  | "image"
  | "info"
  | "link"
  | "lock"
  | "medal"
  | "menu"
  | "note"
  | "paperclip"
  | "party"
  | "pin"
  | "plate"
  | "plug"
  | "plus"
  | "print"
  | "refresh"
  | "robot"
  | "salt"
  | "scroll"
  | "search"
  | "settings"
  | "share"
  | "shield"
  | "sliders"
  | "sparkle"
  | "sprout"
  | "star"
  | "target"
  | "timer"
  | "trash"
  | "trophy"
  | "unlock"
  | "user"
  | "zap";

export type AdminIconName =
  | "dashboard"
  | "users"
  | "recipes"
  | "categories"
  | "courses"
  | "lessons"
  | "reviews"
  | "questions"
  | "quizzes"
  | "progress"
  | "certificates"
  | "achievements"
  | "favorites"
  | "notifications"
  | "assistant"
  | "recommendations"
  | "security"
  | "logout";

export type IconName = `ui/${UiIconName}` | `admin/${AdminIconName}`;

/**
 * Glyphs with no meaningful colour of their own, which therefore read
 * better inheriting the surrounding text colour than keeping their flat
 * source fill. Everything not listed here keeps its artwork.
 */
const MASKABLE = new Set<IconName>([
  "ui/star",
  "ui/sparkle",
  "ui/sliders",
  "ui/target",
  "ui/paperclip",
  "ui/camera",
  "ui/chat",
]);

/**
 * An icon from the library, drawn in its own colours.
 *
 * Decorative by default. Pass `label` only when the icon is the *only*
 * carrier of the meaning (an icon-only button); if there is adjacent
 * text saying the same thing, leaving it hidden is the correct choice.
 *
 * Pass `tint` to flatten it to `currentColor` instead — see the file
 * docstring for when that is the right call.
 */
export function Icon({
  name,
  label,
  className,
  style,
  tint,
}: {
  name: IconName;
  label?: string;
  className?: string;
  style?: CSSProperties;
  /**
   * Force the mask on (`true`) or off (`false`). Omit to let `MASKABLE`
   * decide — see the file docstring.
   */
  tint?: boolean;
}) {
  const src = `/icons/${name}.svg`;

  if (tint ?? MASKABLE.has(name)) {
    const url = `url("${src}")`;
    return (
      <span
        role={label ? "img" : undefined}
        aria-label={label}
        aria-hidden={label ? undefined : true}
        className={cn("inline-block size-5 shrink-0 bg-current", className)}
        style={{
          ...style,
          maskImage: url,
          WebkitMaskImage: url,
          maskRepeat: "no-repeat",
          WebkitMaskRepeat: "no-repeat",
          maskPosition: "center",
          WebkitMaskPosition: "center",
          maskSize: "contain",
          WebkitMaskSize: "contain",
        }}
      />
    );
  }

  return (
    <img
      src={src}
      alt={label ?? ""}
      aria-hidden={label ? undefined : true}
      draggable={false}
      // `object-contain` so a non-square glyph letterboxes inside the box
      // instead of stretching, matching what the mask used to do.
      className={cn("inline-block size-5 shrink-0 select-none object-contain", className)}
      style={style}
    />
  );
}

/** Full-colour illustration art (modal status, flavor motifs, badges). */
export function ArtIcon({
  src,
  alt = "",
  className,
  style,
}: {
  src: string;
  alt?: string;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <img
      src={src}
      alt={alt}
      aria-hidden={alt ? undefined : true}
      draggable={false}
      className={cn("select-none", className)}
      style={style}
    />
  );
}
