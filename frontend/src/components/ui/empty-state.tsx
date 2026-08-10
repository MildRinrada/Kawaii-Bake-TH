import type { ReactNode } from "react";

/**
 * Friendly empty state: one restrained badge, a warm message — never a
 * wall of gray.
 *
 * `icon` is a node so callers pass real artwork from `public/icons/`
 * (via `<Icon>`/`<ArtIcon>`); there is no default — an empty state with
 * nothing to show a picture of gets a plain soft badge instead of a
 * stock illustration standing in for content. The badge sizes itself
 * from the icon plus padding rather than a fixed box — `shrink-0` on a
 * flex-row ancestor (there is none here, but a caller's wrapper might
 * be one) would otherwise squish a wide child down to fit a fixed box,
 * which distorts anything that isn't already square.
 */
export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-14 text-center">
      {icon ? (
        <span
          aria-hidden
          className="flex shrink-0 items-center justify-center rounded-full bg-surface-sunken p-4"
        >
          {icon}
        </span>
      ) : null}
      <p className="font-display text-base font-medium text-fg">{title}</p>
      {description ? (
        <p className="max-w-sm text-sm text-fg-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
