"use client";

import { useId, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface FieldProps {
  label: string;
  /** Field-level errors (already localised by the backend). */
  errors?: string[];
  hint?: string;
  required?: boolean;
  className?: string;
  /** Render prop receives the wiring for the control. */
  children: (control: {
    id: string;
    "aria-invalid": boolean | undefined;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}

/**
 * Label + control + error wiring in one accessible unit: the control is
 * always labelled, and errors are announced via `aria-describedby`.
 */
export function Field({
  label,
  errors,
  hint,
  required,
  className,
  children,
}: FieldProps) {
  const id = useId();
  const describedBy = errors?.length ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium text-fg">
        {label}
        {required ? <span aria-hidden> *</span> : null}
      </label>
      {children({
        id,
        "aria-invalid": errors?.length ? true : undefined,
        "aria-describedby": describedBy,
      })}
      {hint && !errors?.length ? (
        <p id={`${id}-hint`} className="text-sm text-fg-muted">
          {hint}
        </p>
      ) : null}
      {errors?.length ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-danger">
          {errors.join(" ")}
        </p>
      ) : null}
    </div>
  );
}
