"use client";

import { forwardRef, useState, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";
import { inputClassName } from "@/components/ui/input";

/**
 * Password field with a show/hide toggle. Seeing what you typed is what
 * lets the form ask for the password only once  the toggle replaces a
 * confirm field.
 */
export const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, "type">
>(function PasswordInput({ className, ...rest }, ref) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        ref={ref}
        type={visible ? "text" : "password"}
        className={cn(inputClassName, "pr-12", className)}
        {...rest}
      />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        aria-label={visible ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}
        aria-pressed={visible}
        className={cn(
          "absolute inset-y-0 right-1.5 my-auto flex size-8 items-center justify-center rounded-full text-base",
          "text-fg-muted hover:bg-surface-sunken hover:text-fg",
          "focus-visible:outline-2 focus-visible:outline-focus",
        )}
      >
        <span aria-hidden>{visible ? "🙈" : "👁️"}</span>
      </button>
    </div>
  );
});
