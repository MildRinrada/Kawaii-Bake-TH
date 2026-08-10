/* eslint-disable @next/next/no-img-element -- these are fixed-size local SVGs
   from public/; next/image would add a loader round-trip and buy nothing */

/**
 * The two ways KawaiiBake draws an icon.
 *
 * `Icon` paints a monochrome glyph through a CSS mask, so it inherits
 * `currentColor` exactly like text does — an admin nav item and a danger
 * button get the right colour for free. `ArtIcon` renders full-colour
 * illustration art as a plain image.
 *
 * Which one to use is decided by which folder the file is in, and the
 * split is enforced by the union types below: `icons/ui` and
 * `icons/admin` are mask art, everything else is picture art. See
 * `public/README.md`.
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
 * A monochrome glyph that takes the surrounding text colour.
 *
 * Decorative by default. Pass `label` only when the icon is the *only*
 * carrier of the meaning (an icon-only button); if there is adjacent
 * text saying the same thing, leaving it hidden is the correct choice.
 */
export function Icon({
  name,
  label,
  className,
  style,
}: {
  name: IconName;
  label?: string;
  className?: string;
  style?: CSSProperties;
}) {
  const url = `url("/icons/${name}.svg")`;
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
