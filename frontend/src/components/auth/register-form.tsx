"use client";

/**
 * Sign-up: three fields and a consent box.
 *
 * What is *not* here is the design decision. The legal name printed on
 * certificates used to be collected on this form; it is now asked for
 * once, at issuance, where it is the point of the request (see
 * `POST /courses/{slug}/certificate/` and its `legal_name_required`).
 * Most accounts never claim a certificate, so most people were filling
 * two fields for a document they would never ask for.
 *
 * Everything the server can refuse is stated before it can refuse it:
 * the password rules are on screen from the first paint, the handle is
 * checked live against the backend, and the submit button stays out of
 * reach until the form is actually sendable. The server remains the
 * authority on every rule - inline checks only surface its verdicts
 * earlier.
 */

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import { GoogleSignIn } from "@/components/auth/google-sign-in";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import {
  PasswordChecklist,
  passwordMeetsRules,
} from "@/components/ui/password-strength";
import { useAuth } from "@/lib/auth/auth-context";
import { useFormSubmit } from "@/lib/forms/use-form";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Mirrors the backend's USERNAME_PATTERN (users app).
const USERNAME_RE = /^[a-z0-9][a-z0-9_-]*[a-z0-9]$/;

function emailFormatError(value: string): string | null {
  if (!value) return "กรุณากรอกอีเมล";
  if (!EMAIL_RE.test(value)) {
    return "รูปแบบอีเมลไม่ถูกต้อง เช่น name@example.com";
  }
  return null;
}

function usernameFormatError(value: string): string | null {
  if (!value) return "กรุณาตั้งชื่อผู้ใช้";
  if (value.length < 3) return "ชื่อผู้ใช้ต้องยาวอย่างน้อย 3 ตัวอักษร";
  if (value.length > 30) return "ชื่อผู้ใช้ต้องยาวไม่เกิน 30 ตัวอักษร";
  if (!USERNAME_RE.test(value)) {
    return "ใช้ได้เฉพาะ a-z, 0-9, ขีดกลาง (-) และขีดล่าง (_) และต้องขึ้นต้นและลงท้ายด้วยตัวอักษรหรือตัวเลข";
  }
  return null;
}

interface AvailabilityAnswer {
  username: string;
  available: boolean;
}

export function RegisterForm({
  onSwitchToLogin,
}: {
  /** Slide across to sign-in instead of navigating away. */
  onSwitchToLogin: () => void;
}) {
  const { register } = useAuth();
  const router = useRouter();
  const { submitting, formError, fieldErrors, submit } = useFormSubmit();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [attempted, setAttempted] = useState(false);
  const [availability, setAvailability] = useState<AvailabilityAnswer | null>(
    null,
  );

  const trimmedEmail = email.trim();
  const normalizedUsername = username.trim().toLowerCase();
  const emailError = emailFormatError(trimmedEmail);
  const usernameError = usernameFormatError(normalizedUsername);
  const identity = { username: normalizedUsername, email: trimmedEmail };
  const passwordOk = passwordMeetsRules(password, identity);

  // Live availability: debounced while typing; the answer is only trusted
  // for the exact handle it was asked about, so a stale reply can never
  // label the current input.
  useEffect(() => {
    const candidate = username.trim().toLowerCase();
    if (usernameFormatError(candidate)) return;
    const timer = setTimeout(() => {
      api
        .get<AvailabilityAnswer>(
          `/auth/username-available/?username=${encodeURIComponent(candidate)}`,
        )
        .then(setAvailability)
        .catch(() => {
          // Advisory only  registration itself still enforces the rule.
        });
    }, 450);
    return () => clearTimeout(timer);
  }, [username]);

  const availabilityKnown =
    availability?.username === normalizedUsername
      ? availability.available
      : null;

  const showError = (field: string) => touched[field] || attempted;
  const markTouched = (field: string) =>
    setTouched((state) => ({ ...state, [field]: true }));

  const emailErrors = [
    ...(showError("email") && emailError ? [emailError] : []),
    ...(fieldErrors.email ?? []),
  ];
  const usernameErrors = [
    ...(showError("username") && usernameError ? [usernameError] : []),
    ...(fieldErrors.username ?? []),
  ];
  const passwordErrors = fieldErrors.password ?? [];

  // What the button is waiting for, in the order the form asks for it.
  // A disabled button that says nothing is a dead end - but on an empty
  // form the list is every field, which says nothing either. It appears
  // once it can actually point at something.
  const missing = [
    emailError ? "อีเมล" : null,
    usernameError || availabilityKnown === false ? "ชื่อผู้ใช้" : null,
    passwordOk ? null : "รหัสผ่าน",
    acceptTerms ? null : "การยอมรับข้อตกลง",
  ].filter((item): item is string => item !== null);
  const canSubmit = missing.length === 0;
  const almostThere = missing.length > 0 && missing.length <= 2;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setAttempted(true);
    if (!canSubmit) return;

    const ok = await submit(() =>
      register({
        email: trimmedEmail.toLowerCase(),
        username: normalizedUsername,
        password,
        accept_terms: acceptTerms,
      }),
    );
    if (ok) {
      // No session yet on purpose: the inbox is the next stop, and the
      // user signs in themselves after confirming.
      router.replace(
        `/register/sent?email=${encodeURIComponent(trimmedEmail.toLowerCase())}`,
      );
    }
  }

  return (
    <Card className="w-full">
      <CardBody className="space-y-4">
        {/* The card says what it is on its own: on a narrow screen the
            pitch column's heading is far above the fold. */}
        <h2 className="font-display text-lg font-medium text-fg">สร้างบัญชี</h2>

        {/* Above the fields, where the fastest way in belongs. Renders
            nothing when this deployment has no Google client id. */}
        <GoogleSignIn label="สมัคร" onSignedIn={() => router.replace("/")} />

        {/* Labelled because sign-in is on the same page behind the
            slider: two unnamed forms in one document is a maze for a
            screen reader, and the label is what tells them apart. */}
        <form
          onSubmit={onSubmit}
          noValidate
          aria-label="สมัครสมาชิก"
          className="space-y-4"
        >
          {formError ? (
            <p
              role="alert"
              className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
            >
              {formError}
            </p>
          ) : null}

          {/* No hint: "you sign in with your email" is not news. The
              handle keeps its hint because it says something the field
              cannot - that this name is the public one. */}
          <Field label="อีเมล" errors={emailErrors} required>
            {(control) => (
              <Input
                {...control}
                type="email"
                name="email"
                inputMode="email"
                autoComplete="email"
                autoCapitalize="none"
                spellCheck={false}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                onBlur={() => markTouched("email")}
              />
            )}
          </Field>

          <Field
            label="ชื่อผู้ใช้"
            errors={usernameErrors}
            hint={
              normalizedUsername && !usernameError
                ? undefined
                : "ชื่อสาธารณะของคุณ  คนอื่นเห็นชื่อนี้แทนอีเมลเสมอ"
            }
            required
          >
            {(control) => (
              <div className="space-y-1.5">
                <Input
                  {...control}
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  onBlur={() => markTouched("username")}
                />
                {!usernameError && normalizedUsername ? (
                  <p role="status" className="flex items-center gap-1 text-sm">
                    {availabilityKnown === true ? (
                      <span className="flex items-center gap-1 text-success">
                        <Icon name="ui/check" tint className="size-3.5" />
                        ใช้ชื่อ @{normalizedUsername} ได้
                      </span>
                    ) : availabilityKnown === false ? (
                      <span className="flex items-center gap-1 text-danger">
                        <Icon name="ui/close" tint className="size-3.5" />
                        ชื่อนี้ถูกใช้แล้วหรือถูกสงวนไว้ ลองชื่ออื่นดูนะ
                      </span>
                    ) : (
                      <span className="text-fg-muted">กำลังตรวจสอบ…</span>
                    )}
                  </p>
                ) : null}
              </div>
            )}
          </Field>

          <Field label="รหัสผ่าน" errors={passwordErrors} required>
            {(control) => (
              <div>
                <PasswordInput
                  {...control}
                  name="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  onBlur={() => markTouched("password")}
                />
                <PasswordChecklist password={password} context={identity} />
              </div>
            )}
          </Field>

          <div className="space-y-1.5">
            <label className="flex items-start gap-2.5 text-sm text-fg">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(event) => setAcceptTerms(event.target.checked)}
                className="mt-1 size-4 shrink-0 cursor-pointer accent-accent"
              />
              <span className="leading-6">
                ยอมรับ{" "}
                <Link
                  href="/legal?doc=terms"
                  target="_blank"
                  className="font-medium text-accent underline underline-offset-2"
                >
                  ข้อตกลงการใช้งาน
                </Link>{" "}
                และ{" "}
                <Link
                  href="/legal?doc=privacy"
                  target="_blank"
                  className="font-medium text-accent underline underline-offset-2"
                >
                  นโยบายความเป็นส่วนตัว
                </Link>
              </span>
            </label>
            {(fieldErrors.accept_terms ?? []).map((message) => (
              <p key={message} role="alert" className="pl-6.5 text-sm text-danger">
                {message}
              </p>
            ))}
          </div>

          <div className="space-y-1.5">
            <Button
              type="submit"
              loading={submitting}
              disabled={!canSubmit}
              className="w-full"
            >
              สมัครสมาชิก
            </Button>
            {almostThere ? (
              <p className="text-center text-sm text-fg-muted">
                เหลืออีก: {missing.join(" · ")}
              </p>
            ) : null}
          </div>

          <p className="text-center text-sm text-fg-muted">
            มีบัญชีแล้ว?{" "}
            {/* A real link (right href, keyboard, middle-click), whose
                click is taken over to slide instead of navigate. */}
            <Link
              href="/login"
              onClick={(event) => {
                if (event.metaKey || event.ctrlKey || event.shiftKey) return;
                event.preventDefault();
                onSwitchToLogin();
              }}
              className="font-medium text-fg underline"
            >
              เข้าสู่ระบบ
            </Link>
          </p>
        </form>
      </CardBody>
    </Card>
  );
}
