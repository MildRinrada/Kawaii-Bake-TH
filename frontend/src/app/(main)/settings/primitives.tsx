"use client";

/**
 * The shared vocabulary of the settings screens.
 *
 * Settings is a utility surface: one calm card per group, dividers
 * instead of decoration, and the same left-label / right-control rhythm
 * throughout. Nothing here is a coloured hero  the page is read, not
 * browsed.
 */

import type { ReactNode } from "react";
import { useId } from "react";

import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";
import type { SaveStatus } from "./use-auto-save";

/** A titled group of related settings. */
export function Group({
  title,
  description,
  footnote,
  children,
}: {
  title: string;
  description?: string;
  footnote?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-display text-base font-medium text-fg">{title}</h3>
        {description ? (
          <p className="mt-1 text-sm leading-relaxed text-fg-muted">
            {description}
          </p>
        ) : null}
      </div>
      <Card className="px-5 py-1 sm:px-6">{children}</Card>
      {footnote ? (
        <p className="text-xs leading-relaxed text-fg-subtle">{footnote}</p>
      ) : null}
    </section>
  );
}

/** A divider between rows inside a `Group`'s card. */
export function Rows({ children }: { children: ReactNode }) {
  return <div className="divide-y divide-edge">{children}</div>;
}

/** A label/description on the left, a control on the right. */
export function Row({
  label,
  description,
  htmlFor,
  children,
}: {
  label: string;
  description?: string;
  /** Set when the control is a single labelable element. */
  htmlFor?: string;
  children: ReactNode;
}) {
  const Tag = htmlFor ? "label" : "span";
  return (
    <div className="flex flex-col gap-2 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <span className="min-w-0">
        <Tag
          {...(htmlFor ? { htmlFor } : {})}
          className="block text-sm font-medium text-fg"
        >
          {label}
        </Tag>
        {description ? (
          <span className="mt-0.5 block text-sm leading-relaxed text-fg-muted">
            {description}
          </span>
        ) : null}
      </span>
      <span className="shrink-0 sm:max-w-xs">{children}</span>
    </div>
  );
}

/**
 * A radio group rendered as pill options.
 *
 * A real `<fieldset>` + `<input type="radio">` per option, so arrow-key
 * navigation, the group label and the checked state all come from the
 * platform. The pill is the styled label; `peer-focus-visible` puts the
 * focus ring on it because the input itself is visually hidden.
 */
export function RadioPills<T extends string>({
  legend,
  description,
  value,
  options,
  onChange,
  disabled,
}: {
  legend: string;
  description?: string;
  value: T;
  options: Array<{ value: T; label: string; hint?: string }>;
  onChange: (next: T) => void;
  disabled?: boolean;
}) {
  const name = useId();
  return (
    <fieldset disabled={disabled} className="py-3.5">
      <legend className="text-sm font-medium text-fg">{legend}</legend>
      {description ? (
        <p className="mt-0.5 text-sm leading-relaxed text-fg-muted">
          {description}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = option.value === value;
          return (
            <span key={option.value} className="relative">
              <input
                type="radio"
                name={name}
                id={`${name}-${option.value}`}
                value={option.value}
                checked={active}
                onChange={() => onChange(option.value)}
                className="peer sr-only"
              />
              <label
                htmlFor={`${name}-${option.value}`}
                className={cn(
                  "flex cursor-pointer items-center gap-1.5 rounded-full px-4 py-2 text-sm transition-colors",
                  "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus",
                  "peer-disabled:cursor-not-allowed peer-disabled:opacity-60",
                  active
                    ? "bg-accent font-medium text-fg-inverted shadow-raised"
                    : "bg-surface-sunken text-fg-muted hover:text-fg",
                )}
              >
                {/* A check, not just a colour  state survives greyscale. */}
                {active ? <Icon name="ui/check" tint className="size-3.5" /> : null}
                <span>{option.label}</span>
              </label>
            </span>
          );
        })}
      </div>
      {options.find((option) => option.value === value)?.hint ? (
        <p className="mt-2 text-xs leading-relaxed text-fg-subtle">
          {options.find((option) => option.value === value)?.hint}
        </p>
      ) : null}
    </fieldset>
  );
}

/** Multi-select chips  the checkbox equivalent of `RadioPills`. */
export function CheckChips<T extends string>({
  legend,
  description,
  values,
  options,
  onToggle,
  disabled,
}: {
  legend: string;
  description?: string;
  values: readonly T[];
  options: Array<{ value: T; label: string }>;
  onToggle: (value: T, next: boolean) => void;
  disabled?: boolean;
}) {
  const name = useId();
  return (
    <fieldset disabled={disabled} className="py-3.5">
      <legend className="text-sm font-medium text-fg">{legend}</legend>
      {description ? (
        <p className="mt-0.5 text-sm leading-relaxed text-fg-muted">
          {description}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = values.includes(option.value);
          return (
            <span key={option.value} className="relative">
              <input
                type="checkbox"
                id={`${name}-${option.value}`}
                checked={active}
                onChange={(event) => onToggle(option.value, event.target.checked)}
                className="peer sr-only"
              />
              <label
                htmlFor={`${name}-${option.value}`}
                className={cn(
                  "flex cursor-pointer items-center gap-1.5 rounded-full px-4 py-2 text-sm transition-colors",
                  "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus",
                  "peer-disabled:cursor-not-allowed peer-disabled:opacity-60",
                  active
                    ? "bg-accent font-medium text-fg-inverted shadow-raised"
                    : "bg-surface-sunken text-fg-muted hover:text-fg",
                )}
              >
                {active ? <Icon name="ui/check" tint className="size-3.5" /> : null}
                <span>{option.label}</span>
              </label>
            </span>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * The auto-save read-out for a panel.
 *
 * `role="status"` so a screen reader hears the outcome without the
 * focus moving, and the failure carries the server's own message rather
 * than a generic apology.
 */
export function SaveIndicator({
  status,
  error,
}: {
  status: SaveStatus;
  error?: string | null;
}) {
  return (
    <p
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center gap-1.5 text-xs",
        status === "error" ? "text-danger" : "text-fg-subtle",
      )}
    >
      {status === "saving" ? "กำลังบันทึก…" : null}
      {status === "saved" ? (
        <>
          <Icon name="ui/check" tint className="size-3.5" />
          บันทึกแล้ว
        </>
      ) : null}
      {status === "error" ? (
        <>
          <Icon name="ui/alert" tint className="size-3.5" />
          {error ?? "บันทึกไม่สำเร็จ"}
        </>
      ) : null}
      {status === "idle" ? "การเปลี่ยนแปลงจะถูกบันทึกอัตโนมัติ" : null}
    </p>
  );
}

/**
 * States a capability the backend does not have yet.
 *
 * Shipping a dead control is worse than shipping nothing: it teaches the
 * user their choice was recorded when it was not. Naming the gap keeps
 * the page honest and tells the next developer exactly what is missing.
 */
export function NotAvailable({
  title,
  reason,
}: {
  title: string;
  reason: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-control bg-surface-sunken px-4 py-3">
      <Icon name="ui/info" tint className="mt-0.5 size-4 shrink-0 text-fg-subtle" />
      <p className="text-sm leading-relaxed text-fg-muted">
        <span className="font-medium text-fg">{title}</span>
        <span className="mt-0.5 block text-fg-subtle">{reason}</span>
      </p>
    </div>
  );
}
