"use client";

/**
 * Sign-in: the same card as sign-up, two fields shorter.
 *
 * Deliberately identical furniture - heading, Google button, divider,
 * field spacing, footer link - because the two screens are one decision
 * seen from either side, and the slider between them makes any
 * difference in chrome look like a glitch rather than a design.
 *
 * The failure message is one sentence for both causes ("อีเมลหรือ
 * รหัสผ่านไม่ถูกต้อง"). That is the backend's wording too: telling the
 * caller *which* half was wrong turns the endpoint into an
 * account-existence oracle. Attempts are counted server-side, and after
 * a few misses this form starts pointing at the recovery path rather
 * than letting someone keep guessing.
 */

import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { GoogleSignIn } from "@/components/auth/google-sign-in";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/lib/auth/auth-context";
import { useFormSubmit } from "@/lib/forms/use-form";

/** Misses before the form starts suggesting the reset link. */
const NUDGE_AFTER = 2;

export function LoginForm({
  onSwitchToRegister,
}: {
  /** Slide across to sign-up instead of navigating away. */
  onSwitchToRegister: () => void;
}) {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { submitting, formError, fieldErrors, submit } = useFormSubmit();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [failures, setFailures] = useState(0);

  const destination = searchParams.get("next") ?? "/";

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const ok = await submit(() => login(email, password, remember));
    if (ok) {
      router.replace(destination);
      return;
    }
    setFailures((count) => count + 1);
  }

  // One-time flags set by the verification and reset screens.
  const justVerified = searchParams.get("verified") === "1";
  const justReset = searchParams.get("reset") === "1";

  return (
    <Card className="w-full">
      <CardBody className="space-y-4">
        {/* The card says what it is on its own: on a narrow screen the
            pitch column's heading is far above the fold. */}
        <h2 className="font-display text-lg font-medium text-fg">เข้าสู่ระบบ</h2>

        {/* Same account either way: the button that created an account
            is the button that signs it back in. */}
        <GoogleSignIn
          label="เข้าสู่ระบบ"
          onSignedIn={() => router.replace(destination)}
        />

        <form
          onSubmit={onSubmit}
          noValidate
          aria-label="เข้าสู่ระบบ"
          className="space-y-4"
        >
          {justVerified ? (
            <p
              role="status"
              className="rounded-control bg-success-subtle px-3 py-2 text-sm text-success"
            >
              ยืนยันอีเมลเรียบร้อยแล้ว - เข้าสู่ระบบเพื่อเริ่มใช้งานได้เลย
            </p>
          ) : null}
          {justReset ? (
            <p
              role="status"
              className="rounded-control bg-success-subtle px-3 py-2 text-sm text-success"
            >
              ตั้งรหัสผ่านใหม่เรียบร้อยแล้ว - เข้าสู่ระบบด้วยรหัสผ่านใหม่ได้เลย
            </p>
          ) : null}
          {formError ? (
            <p
              role="alert"
              className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
            >
              {formError}
            </p>
          ) : null}
          <Field label="อีเมล" errors={fieldErrors.email} required>
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
              />
            )}
          </Field>
          <Field
            label="รหัสผ่าน"
            errors={fieldErrors.password}
            required
            action={
              <Link
                href="/forgot-password"
                className="text-sm text-fg-muted underline underline-offset-2 hover:text-fg"
              >
                ลืมรหัสผ่าน?
              </Link>
            }
          >
            {(control) => (
              <PasswordInput
                {...control}
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>

          {/* Default on: this is a recipe site people open mid-bake with
              floury hands, not a bank. Unchecking gives a session that
              dies with the browser. */}
          <label className="flex items-center gap-2.5 text-sm text-fg">
            <input
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
              className="size-4 shrink-0 cursor-pointer accent-accent"
            />
            จำฉันไว้ 30 วัน
          </label>

          <Button type="submit" loading={submitting} className="w-full">
            เข้าสู่ระบบ
          </Button>

          {failures > NUDGE_AFTER ? (
            <p className="text-center text-sm text-fg-muted">
              จำรหัสผ่านไม่ได้?{" "}
              <Link
                href="/forgot-password"
                className="font-medium text-accent underline underline-offset-2"
              >
                ตั้งรหัสผ่านใหม่
              </Link>
            </p>
          ) : null}

          <p className="text-center text-sm text-fg-muted">
            ยังไม่มีบัญชี?{" "}
            <Link
              href="/register"
              onClick={(event) => {
                if (event.metaKey || event.ctrlKey || event.shiftKey) return;
                event.preventDefault();
                onSwitchToRegister();
              }}
              className="font-medium text-fg underline"
            >
              สมัครสมาชิก
            </Link>
          </p>
        </form>
      </CardBody>
    </Card>
  );
}
