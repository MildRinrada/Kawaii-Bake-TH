"use client";

import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const inputClassName = cn(
  "block w-full rounded-control border border-edge-strong/50 bg-surface px-3.5 py-2.5 text-sm text-fg",
  "placeholder:text-fg-subtle",
  "transition-colors hover:border-edge-strong",
  "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus",
  "aria-invalid:border-danger",
  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-fg-subtle",
);

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cn(inputClassName, className)} {...rest} />;
});
