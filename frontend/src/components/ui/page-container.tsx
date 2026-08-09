import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/**
 * The page-width constraint every route shares. Responsive paddings live
 * here once; the design phase tunes width/rhythm in one place.
 */
export function PageContainer({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("mx-auto w-full max-w-6xl px-4 py-8 sm:px-6", className)}
      {...rest}
    />
  );
}
