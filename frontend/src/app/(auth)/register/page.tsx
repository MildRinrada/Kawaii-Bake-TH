"use client";

/**
 * Sign-up: email, handle, legal name, password - validated inline as
 * the user types. The handle is checked live against the backend; the
 * password gets a strength meter mirroring the server's validators; a
 * show/hide toggle replaces the confirm field. The server remains the
 * authority on every rule  inline checks only surface its verdicts
 * earlier.
 */

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import {
  PasswordStrengthMeter,
  passwordStrength,
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

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const { submitting, formError, fieldErrors, submit } = useFormSubmit();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [attempted, setAttempted] = useState(false);
  const [availability, setAvailability] = useState<AvailabilityAnswer | null>(
    null,
  );

  const normalizedUsername = username.trim().toLowerCase();
  const emailError = emailFormatError(email.trim());
  const usernameError = usernameFormatError(normalizedUsername);
  const firstNameError = firstName.trim() ? null : "กรุณากรอกชื่อจริง";
  const lastNameError = lastName.trim() ? null : "กรุณากรอกนามสกุล";
  const strength = passwordStrength(password);
  const passwordError = !password
    ? "กรุณาตั้งรหัสผ่าน"
    : strength.level < 2
      ? strength.label
      : null;

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
  const passwordErrors = [
    ...(attempted && !password ? ["กรุณาตั้งรหัสผ่าน"] : []),
    ...(fieldErrors.password ?? []),
  ];
  const firstNameErrors = [
    ...(showError("first_name") && firstNameError ? [firstNameError] : []),
    ...(fieldErrors.first_name ?? []),
  ];
  const lastNameErrors = [
    ...(showError("last_name") && lastNameError ? [lastNameError] : []),
    ...(fieldErrors.last_name ?? []),
  ];

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setAttempted(true);
    if (emailError || usernameError || passwordError) return;
    if (firstNameError || lastNameError) return;
    if (availabilityKnown === false) return;
    if (!acceptTerms) return;

    const ok = await submit(() =>
      register({
        email: email.trim().toLowerCase(),
        username: normalizedUsername,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        password,
        accept_terms: acceptTerms,
      }),
    );
    if (ok) {
      // No session yet on purpose: the inbox is the next stop, and the
      // user signs in themselves after confirming.
      router.replace(
        `/register/sent?email=${encodeURIComponent(email.trim().toLowerCase())}`,
      );
    }
  }

  return (
    <Card>
      <CardHeader title="สมัครสมาชิก" />
      <CardBody>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {formError ? (
            <p
              role="alert"
              className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
            >
              {formError}
            </p>
          ) : null}

          <Field label="อีเมล" errors={emailErrors} required>
            {(control) => (
              <Input
                {...control}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                onBlur={() => markTouched("email")}
              />
            )}
          </Field>

          <Field
            label="ชื่อผู้ใช้"
            errors={usernameErrors}
            hint="ชื่อสาธารณะของคุณ  คนอื่นเห็นชื่อนี้แทนอีเมลเสมอ"
            required
          >
            {(control) => (
              <div className="space-y-1.5">
                <Input
                  {...control}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  onBlur={() => markTouched("username")}
                />
                {!usernameError && normalizedUsername ? (
                  <p role="status" className="text-xs">
                    {availabilityKnown === true ? (
                      <span className="text-success">
                        ✓ ใช้ชื่อ @{normalizedUsername} ได้
                      </span>
                    ) : availabilityKnown === false ? (
                      <span className="text-danger">
                        ✗ ชื่อนี้ถูกใช้แล้วหรือถูกสงวนไว้ ลองชื่ออื่นดูนะ
                      </span>
                    ) : (
                      <span className="text-fg-muted">กำลังตรวจสอบ…</span>
                    )}
                  </p>
                ) : null}
              </div>
            )}
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="ชื่อจริง"
              errors={firstNameErrors}
              hint="ใช้พิมพ์บนใบประกาศนียบัตร ไม่แสดงต่อผู้อื่น"
              required
            >
              {(control) => (
                <Input
                  {...control}
                  autoComplete="given-name"
                  value={firstName}
                  onChange={(event) => setFirstName(event.target.value)}
                  onBlur={() => markTouched("first_name")}
                />
              )}
            </Field>
            <Field label="นามสกุล" errors={lastNameErrors} required>
              {(control) => (
                <Input
                  {...control}
                  autoComplete="family-name"
                  value={lastName}
                  onChange={(event) => setLastName(event.target.value)}
                  onBlur={() => markTouched("last_name")}
                />
              )}
            </Field>
          </div>

          <Field label="รหัสผ่าน" errors={passwordErrors} required>
            {(control) => (
              <div>
                <PasswordInput
                  {...control}
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  onBlur={() => markTouched("password")}
                />
                <PasswordStrengthMeter password={password} />
              </div>
            )}
          </Field>

          <p className="rounded-control bg-berry-soft/60 px-3.5 py-2.5 text-xs leading-relaxed text-fg-muted">
            สมัครแล้วได้อะไร {" "}
            <span className="font-medium text-berry-ink">
              บันทึกสูตรโปรด
            </span>{" "}
            เรียนคอร์สพร้อมเก็บความคืบหน้า และถามผู้ช่วย AI ได้ทันที ฟรี
          </p>

          <div className="space-y-1.5">
            <label className="flex items-start gap-2.5 text-sm text-fg">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(event) => setAcceptTerms(event.target.checked)}
                className="mt-1 size-4 shrink-0 cursor-pointer accent-accent"
              />
              <span className="leading-relaxed">
                ฉันได้อ่านและยอมรับ{" "}
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
                  นโยบายความเป็นส่วนตัว (PDPA)
                </Link>
                <span aria-hidden className="font-semibold text-danger">
                  {" "}
                  *
                </span>
              </span>
            </label>
            {attempted && !acceptTerms ? (
              <p role="alert" className="pl-6.5 text-sm text-danger">
                กรุณายอมรับข้อตกลงก่อนสมัครสมาชิก
              </p>
            ) : null}
            {(fieldErrors.accept_terms ?? []).map((message) => (
              <p key={message} role="alert" className="pl-6.5 text-sm text-danger">
                {message}
              </p>
            ))}
          </div>

          <Button type="submit" loading={submitting} className="w-full">
            สมัครสมาชิก
          </Button>
          <p className="text-center text-sm text-fg-muted">
            มีบัญชีแล้ว?{" "}
            <Link href="/login" className="font-medium text-fg underline">
              เข้าสู่ระบบ
            </Link>
          </p>
        </form>
      </CardBody>
    </Card>
  );
}
