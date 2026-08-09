"use client";

import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";
import { inputClassName } from "@/components/ui/input";

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...rest }, ref) {
  return (
    <select ref={ref} className={cn(inputClassName, className)} {...rest}>
      {children}
    </select>
  );
});
