import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/** Loading placeholder block. Size it with utility classes at the call site. */
export function Skeleton({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse rounded-control bg-linear-to-r from-surface-sunken via-edge/60 to-surface-sunken",
        className,
      )}
      {...rest}
    />
  );
}
