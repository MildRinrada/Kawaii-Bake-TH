import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The KawaiiBake surface: generously rounded, soft warm shadow, sand
 * border. One card style everywhere — variety comes from content and
 * flavor accents, not from competing card treatments.
 */
export function Card({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-surface border border-edge bg-surface-raised shadow-raised",
        className,
      )}
      {...rest}
    />
  );
}

export function CardHeader({
  title,
  actions,
}: {
  title: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-edge px-5 py-3.5">
      <h2 className="font-display text-base font-medium text-fg">{title}</h2>
      {actions}
    </div>
  );
}

export function CardBody({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...rest} />;
}
