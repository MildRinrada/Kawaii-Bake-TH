"use client";

import { forwardRef, useState, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/icon";
import { inputClassName } from "@/components/ui/input";

/**
 * Password field with a show/hide toggle. Seeing what you typed is what
 * lets the form ask for the password only once  the toggle replaces a
 * confirm field, which is why the target is a full 40x40: it is a
 * control people reach for on a phone, not a decoration.
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
        className={cn(inputClassName, "pr-13", className)}
        {...rest}
      />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        aria-label={visible ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}
        aria-pressed={visible}
        className={cn(
          "absolute inset-y-0 right-1 my-auto flex size-10 items-center justify-center rounded-full",
          "text-fg-muted hover:bg-surface-sunken hover:text-fg",
          "focus-visible:outline-2 focus-visible:outline-focus",
        )}
      >
        <Icon name={visible ? "ui/eye-off" : "ui/eye"} tint className="size-5" />
      </button>
    </div>
  );
});
