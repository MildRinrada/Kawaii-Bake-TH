"use client";

/**
 * Numbered pagination: ‹ 1 2 [3] 4 … 10 ›
 *
 * The full page count is visible up front - "… 10" tells the visitor how
 * deep the catalog goes before they commit to walking it, which a bare
 * prev/next pair never does. The number window slides around the current
 * page; the first and last page are always reachable directly.
 */

import { cn } from "@/lib/cn";

/** Pages to render: numbers, with `null` marking an ellipsis gap. */
function pageWindow(current: number, total: number): Array<number | null> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }
  const around = [current - 1, current, current + 1].filter(
    (page) => page > 1 && page < total,
  );
  const pages: Array<number | null> = [1];
  if ((around[0] ?? total) > 2) pages.push(null);
  pages.push(...around);
  if ((around[around.length - 1] ?? 1) < total - 1) pages.push(null);
  pages.push(total);
  return pages;
}

export function PageBar({
  page,
  totalPages,
  onPage,
  className,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
  className?: string;
}) {
  if (totalPages <= 1) return null;

  return (
    <nav
      aria-label="เปลี่ยนหน้า"
      className={cn("flex flex-wrap items-center justify-center gap-1.5", className)}
    >
      <button
        type="button"
        aria-label="หน้าก่อนหน้า"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className={cn(
          "flex h-9 items-center rounded-full px-3 text-sm text-fg-muted shadow-raised transition-colors",
          "hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          "disabled:cursor-not-allowed disabled:opacity-40",
          "bg-surface",
        )}
      >
        ←
      </button>

      {pageWindow(page, totalPages).map((target, index) =>
        target === null ? (
          <span
            key={`gap-${index}`}
            aria-hidden
            className="px-1 text-sm text-fg-subtle"
          >
            …
          </span>
        ) : (
          <button
            key={target}
            type="button"
            aria-label={`หน้า ${target}`}
            aria-current={target === page ? "page" : undefined}
            onClick={() => onPage(target)}
            className={cn(
              "h-9 min-w-9 rounded-full px-2 text-sm tabular-nums shadow-raised transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
              target === page
                ? "bg-accent font-medium text-fg-inverted"
                : "bg-surface text-fg-muted hover:text-fg",
            )}
          >
            {target}
          </button>
        ),
      )}

      <button
        type="button"
        aria-label="หน้าถัดไป"
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
        className={cn(
          "flex h-9 items-center rounded-full px-3 text-sm text-fg-muted shadow-raised transition-colors",
          "hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          "disabled:cursor-not-allowed disabled:opacity-40",
          "bg-surface",
        )}
      >
        →
      </button>
    </nav>
  );
}
