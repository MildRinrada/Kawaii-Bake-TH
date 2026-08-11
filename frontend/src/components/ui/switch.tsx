"use client";

/**
 * An on/off switch built on a real `<button role="switch">`.
 *
 * State is carried by `aria-checked`, not by colour alone: the knob
 * physically moves and a check mark appears when on, so the control is
 * still readable in greyscale or to someone who cannot distinguish the
 * accent from the track.
 *
 * The whole row is the label  `<Switch>` renders the text and the
 * control together so the touch target is the full width, which matters
 * far more on a phone than a 44px square does.
 */

import { useId } from "react";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

export function Switch({
  checked,
  onChange,
  label,
  description,
  disabled,
  className,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
  className?: string;
}) {
  const id = useId();

  return (
    <div
      className={cn(
        "flex items-start justify-between gap-4 py-3.5",
        disabled && "opacity-60",
        className,
      )}
    >
      <span className="min-w-0">
        <label
          htmlFor={id}
          className="block text-sm font-medium text-fg"
        >
          {label}
        </label>
        {description ? (
          <span
            id={`${id}-description`}
            className="mt-0.5 block text-sm leading-relaxed text-fg-muted"
          >
            {description}
          </span>
        ) : null}
      </span>

      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${id}-description` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-full",
          "transition-colors duration-150",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          "disabled:cursor-not-allowed",
          checked ? "bg-accent" : "bg-edge-strong",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "flex size-5 items-center justify-center rounded-full bg-surface shadow-raised",
            "transition-transform duration-150",
            checked ? "translate-x-[1.375rem]" : "translate-x-0.5",
          )}
        >
          {checked ? (
            <Icon name="ui/check" tint className="size-3 text-accent" />
          ) : null}
        </span>
      </button>
    </div>
  );
}
