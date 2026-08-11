"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "tertiary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Shows a spinner and disables the button. */
  loading?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-fg-inverted shadow-raised hover:bg-accent-hover active:translate-y-px disabled:bg-fg-subtle disabled:shadow-none",
  secondary:
    "border border-edge-strong/60 bg-surface text-fg hover:border-accent/50 hover:bg-accent-subtle hover:text-accent-hover active:translate-y-px disabled:text-fg-subtle",
  tertiary:
    "bg-pastel-blue text-fg-inverted shadow-raised hover:bg-pastel-blue-hover active:translate-y-px disabled:bg-fg-subtle disabled:shadow-none",
  ghost:
    "text-fg-muted hover:bg-pastel-blue-subtle hover:text-pastel-blue-hover disabled:text-fg-subtle",
  danger:
    "bg-danger text-fg-inverted shadow-raised hover:opacity-90 active:translate-y-px disabled:bg-fg-subtle",
};

const SIZES: Record<Size, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-7 text-base",
};

/**
 * Pill button  the KawaiiBake control shape. Warm, tactile, and calm:
 * one raspberry primary, soft-outline secondary, quiet ghost.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { variant = "primary", size = "md", loading, className, children, ...rest },
    ref,
  ) {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-full font-medium",
          "transition-[background-color,border-color,color,transform,box-shadow] duration-150",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          "disabled:cursor-not-allowed",
          VARIANTS[variant],
          SIZES[size],
          className,
        )}
        disabled={loading || rest.disabled}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? (
          <span
            aria-hidden
            className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          />
        ) : null}
        {children}
      </button>
    );
  },
);
