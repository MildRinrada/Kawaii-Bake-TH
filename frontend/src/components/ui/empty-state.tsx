import type { ReactNode } from "react";

/**
 * Friendly empty state: one restrained bakery glyph in a soft dish, a
 * warm message — never a wall of gray.
 */
export function EmptyState({
  title,
  description,
  action,
  icon = "🧁",
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-14 text-center">
      <span
        aria-hidden
        className="flex size-16 items-center justify-center rounded-full bg-surface-sunken text-3xl"
      >
        {icon}
      </span>
      <p className="font-display text-base font-medium text-fg">{title}</p>
      {description ? (
        <p className="max-w-sm text-sm text-fg-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
