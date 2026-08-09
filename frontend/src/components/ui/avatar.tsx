/* eslint-disable @next/next/no-img-element -- avatars come from the API
   origin with unknown dimensions; a plain img with fixed box is correct */

import { cn } from "@/lib/cn";

const SIZES = { sm: "size-7 text-xs", md: "size-9 text-sm", lg: "size-16 text-xl" };

/**
 * Avatar with a warm initial fallback — the first grapheme of the
 * display name on a flavor-soft dish, so Thai names render correctly.
 */
export function Avatar({
  src,
  name,
  size = "md",
  className,
}: {
  src?: string | null;
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const initial = [...name][0]?.toLocaleUpperCase("th") ?? "?";
  return src ? (
    <img
      src={src}
      alt=""
      className={cn(
        "shrink-0 rounded-full border border-edge object-cover",
        SIZES[size],
        className,
      )}
    />
  ) : (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-berry-soft font-medium text-berry-ink",
        SIZES[size],
        className,
      )}
    >
      {initial}
    </span>
  );
}
