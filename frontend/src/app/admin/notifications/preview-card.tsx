"use client";

/**
 * The live notification preview: exactly the card the user-facing
 * notification center renders (`(main)/notifications`), with sample
 * values filled into `{{variables}}`.
 */

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

import { renderSample } from "./kinds";

export function NotificationPreviewCard({
  icon,
  title,
  body,
  ctaText,
  link,
  compact = false,
}: {
  icon: string;
  title: string;
  body: string;
  ctaText: string;
  link: string;
  /** Narrow layout, imitating a phone-width notification center. */
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-3.5 rounded-surface border border-accent/30 bg-berry-soft/40 px-4 py-3.5",
        compact ? "max-w-xs" : "max-w-md",
      )}
    >
      <span
        aria-hidden
        className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-fg-muted"
      >
        {icon ? (
          <span className="text-xl leading-none">{icon}</span>
        ) : (
          <Icon name="ui/bell" className="size-5" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">
          {renderSample(title) || "หัวข้อการแจ้งเตือน"}
        </p>
        {body ? (
          <p className="mt-0.5 whitespace-pre-wrap text-sm text-fg-muted">
            {renderSample(body)}
          </p>
        ) : null}
        {link ? (
          <p className="mt-1.5 text-sm font-medium text-accent">
            {ctaText || "ดูรายละเอียด"} →
          </p>
        ) : null}
        <p className="mt-1 text-xs text-fg-subtle">เมื่อสักครู่</p>
      </div>
    </div>
  );
}
