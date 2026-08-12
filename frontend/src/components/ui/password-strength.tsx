"use client";

import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/icon";

/**
 * Live password guidance mirroring the backend's validators.
 *
 * Two different things, deliberately separated:
 *
 * * **Rules** (`passwordRules`) are what the server will refuse  the
 *   configured Django validators, restated. They are shown *before* the
 *   field is touched, so nobody types a password, submits, and only then
 *   learns it was ten characters short.
 * * **Strength** (`passwordStrength`) is advice on top of the rules. It
 *   can be stricter than the server, never looser.
 *
 * One validator is deliberately not restated as a rule:
 * ``CommonPasswordValidator`` checks a 20 000-word list that does not
 * belong in a page bundle. A tick that claimed to cover it would be a
 * tick that lies, so the server's verdict arrives inline under the field
 * instead. The server stays the authority for all of them.
 */

export interface PasswordRule {
  id: string;
  label: string;
  ok: boolean;
}

/** Identity fields Django's similarity validator compares against. */
export interface PasswordContext {
  username?: string;
  email?: string;
}

/** Mirrors `MinimumLengthValidator` in `config/settings/base.py`. */
const MIN_LENGTH = 8;

/** Rough stand-in for Django's SequenceMatcher check: a password that
    *contains* the handle or the mail name is what people actually do. */
function echoesIdentity(password: string, context: PasswordContext): boolean {
  const lowered = password.toLowerCase();
  const parts = [context.username, context.email?.split("@")[0]]
    .map((part) => (part ?? "").trim().toLowerCase())
    .filter((part) => part.length >= 3);
  return parts.some((part) => lowered.includes(part));
}

export function passwordRules(
  password: string,
  context: PasswordContext = {},
): PasswordRule[] {
  return [
    {
      id: "length",
      label: `ยาวอย่างน้อย ${MIN_LENGTH} ตัวอักษร`,
      ok: password.length >= MIN_LENGTH,
    },
    {
      id: "not-numeric",
      label: "ไม่ใช่ตัวเลขล้วน",
      ok: password.length > 0 && !/^\d+$/.test(password),
    },
    {
      id: "not-identity",
      label: "ไม่ซ้ำกับชื่อผู้ใช้หรืออีเมล",
      ok: password.length > 0 && !echoesIdentity(password, context),
    },
  ];
}

/** Whether every rule the client can check is satisfied. */
export function passwordMeetsRules(
  password: string,
  context: PasswordContext = {},
): boolean {
  return passwordRules(password, context).every((rule) => rule.ok);
}

export interface PasswordStrength {
  /** 0 = empty, 1 = too weak to submit, 2 = acceptable, 3 = strong. */
  level: 0 | 1 | 2 | 3;
  label: string;
}

export function passwordStrength(
  password: string,
  context: PasswordContext = {},
): PasswordStrength {
  if (!password) return { level: 0, label: "" };
  const failed = passwordRules(password, context).find((rule) => !rule.ok);
  if (failed) return { level: 1, label: failed.label };
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/].filter((re) =>
    re.test(password),
  ).length;
  if (password.length >= 12 && classes >= 3) {
    return { level: 3, label: "รหัสผ่านแข็งแรงมาก" };
  }
  return {
    level: 2,
    label: "ใช้ได้  เพิ่มตัวพิมพ์ใหญ่ ตัวเลข หรือสัญลักษณ์ให้ปลอดภัยขึ้น",
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

export function PasswordStrengthMeter({
  password,
  context,
}: {
  password: string;
  context?: PasswordContext;
}) {
  const { level, label } = passwordStrength(password, context);
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

/**
 * The rules, ticked as they are met, plus the strength bar once the
 * field has something in it.
 *
 * Rendered from the first paint  an empty field shows the same list in
 * grey, which is the point: the requirements are readable before you
 * choose a password, not after one is rejected.
 */
export function PasswordChecklist({
  password,
  context,
}: {
  password: string;
  context?: PasswordContext;
}) {
  const rules = passwordRules(password, context);
  // An untouched field states requirements; a typed-in one gives
  // verdicts. Grey for both would let "still 3 characters short" read as
  // "not looked at yet".
  const typing = password.length > 0;
  return (
    <div className="space-y-1.5 pt-1.5">
      <ul className="space-y-1">
        {rules.map((rule) => (
          <li
            key={rule.id}
            className={cn(
              "flex items-center gap-1.5 text-xs transition-colors",
              rule.ok
                ? "text-success"
                : typing
                  ? "text-warning"
                  : "text-fg-muted",
            )}
          >
            {rule.ok ? (
              <Icon name="ui/check" tint className="size-3.5" />
            ) : typing ? (
              <Icon name="ui/alert" tint className="size-3.5" />
            ) : (
              /* A bullet, not an empty checkbox: before anything is
                 typed these are requirements being stated, and an
                 unticked box reads as three things already failed. */
              <span
                aria-hidden
                className="mx-1 size-1.5 shrink-0 rounded-full bg-current opacity-40"
              />
            )}
            <span>{rule.label}</span>
          </li>
        ))}
      </ul>
      {/* The bar only says something the ticks do not once every rule is
          met  below that it would just repeat the failing line in red. */}
      {rules.every((rule) => rule.ok) ? (
        <PasswordStrengthMeter password={password} context={context} />
      ) : null}
    </div>
  );
}
