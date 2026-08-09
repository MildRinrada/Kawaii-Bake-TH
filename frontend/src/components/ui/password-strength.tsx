"use client";

import { cn } from "@/lib/cn";

/**
 * Live password guidance mirroring the backend's validators (minimum 10
 * characters, not entirely numeric — Django's configured set). The meter
 * can only ever be *stricter* than the server; the server stays the
 * authority.
 */

export interface PasswordStrength {
  /** 0 = empty, 1 = too weak to submit, 2 = acceptable, 3 = strong. */
  level: 0 | 1 | 2 | 3;
  label: string;
}

export function passwordStrength(password: string): PasswordStrength {
  if (!password) return { level: 0, label: "" };
  if (password.length < 10) {
    return { level: 1, label: "รหัสผ่านต้องยาวอย่างน้อย 10 ตัวอักษร" };
  }
  if (/^\d+$/.test(password)) {
    return { level: 1, label: "รหัสผ่านต้องไม่เป็นตัวเลขล้วน" };
  }
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/].filter((re) =>
    re.test(password),
  ).length;
  if (password.length >= 12 && classes >= 3) {
    return { level: 3, label: "รหัสผ่านแข็งแรงมาก 💪" };
  }
  return {
    level: 2,
    label: "ใช้ได้ — เพิ่มตัวพิมพ์ใหญ่ ตัวเลข หรือสัญลักษณ์ให้ปลอดภัยขึ้น",
  };
}

const BAR_COLORS: Record<1 | 2 | 3, string> = {
  1: "bg-danger",
  2: "bg-warning",
  3: "bg-success",
};

const TEXT_COLORS: Record<1 | 2 | 3, string> = {
  1: "text-danger",
  2: "text-warning",
  3: "text-success",
};

export function PasswordStrengthMeter({ password }: { password: string }) {
  const { level, label } = passwordStrength(password);
  if (level === 0) return null;
  return (
    <div className="space-y-1 pt-1">
      <div className="flex gap-1" aria-hidden>
        {([1, 2, 3] as const).map((segment) => (
          <span
            key={segment}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors",
              segment <= level ? BAR_COLORS[level] : "bg-surface-sunken",
            )}
          />
        ))}
      </div>
      <p role="status" className={cn("text-xs", TEXT_COLORS[level])}>
        {label}
      </p>
    </div>
  );
}
