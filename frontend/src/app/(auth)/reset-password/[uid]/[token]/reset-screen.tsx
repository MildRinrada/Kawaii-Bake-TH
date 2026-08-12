"use client";

/**
 * Set a new password from an emailed link.
 *
 * The token is checked by *using* it: there is no "is this link still
 * good?" endpoint, and inventing one would hand anyone with a stolen
 * link a free validity oracle. So the form renders, and an expired link
 * says so on submit - `invalid_token`, translated, with the way to ask
 * for a fresh one.
 *
 * Confirming the password succeeds and drops every other session
 * server-side, which is the point of a reset: whoever knew the old
 * password is signed out. The user still signs in themselves afterwards.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  AuthAside,
  AuthLayout,
  type AuthPoint,
} from "@/components/auth/auth-aside";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password-input";
import {
  PasswordChecklist,
  passwordMeetsRules,
} from "@/components/ui/password-strength";
import { useFormSubmit } from "@/lib/forms/use-form";

/** What the visitor should know before choosing a password. */
const NOTES: AuthPoint[] = [
  {
    icon: "lock",
    title: "อย่างน้อย 8 ตัวอักษร",
    body: "ยาวกว่านั้นยิ่งดี ผสมตัวเลขหรือสัญลักษณ์ได้ยิ่งปลอดภัย",
  },
  {
    icon: "shield",
    title: "อย่าใช้ซ้ำกับเว็บอื่น",
    body: "ถ้าที่อื่นข้อมูลรั่ว บัญชีที่นี่จะยังปลอดภัย",
  },
  {
    icon: "refresh",
    title: "อุปกรณ์อื่นจะถูกออกจากระบบ",
    body: "ใครที่รู้รหัสเดิมจะใช้ต่อไม่ได้ทันที",
  },
];

export function ResetPasswordScreen({
  uid,
  token,
}: {
  uid: string;
  token: string;
}) {
  const router = useRouter();
  const { submitting, formError, fieldErrors, submit } = useFormSubmit();
  const [password, setPassword] = useState("");
  const [expired, setExpired] = useState(false);

  const ready = passwordMeetsRules(password);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready) return;
    const ok = await submit(async () => {
      try {
        await api.post("/auth/password-reset/confirm/", {
          body: { uid, token, new_password: password },
        });
      } catch (error) {
        if (error instanceof ApiError && error.code === "invalid_token") {
          setExpired(true);
        }
        throw error;
      }
    });
    if (ok) router.replace("/login?reset=1");
  }

  return (
    <AuthLayout
      aside={
        <AuthAside
          title="ตั้งรหัสผ่านใหม่"
          lead="อีกขั้นเดียวก็กลับมาทำขนมต่อได้"
          points={NOTES}
          photo="chocolate"
        />
      }
    >
      <Card className="w-full">
        <CardBody className="space-y-4">
          <div className="space-y-1">
            <h2 className="font-display text-lg font-medium text-fg">
              ตั้งรหัสผ่านใหม่
            </h2>
            <p className="text-sm text-fg-muted">
              ตั้งเสร็จแล้วอุปกรณ์อื่นที่ค้างอยู่จะถูกออกจากระบบทั้งหมด
            </p>
          </div>
          <form
            onSubmit={onSubmit}
            noValidate
            aria-label="ตั้งรหัสผ่านใหม่"
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
            <Field
              label="รหัสผ่านใหม่"
              errors={fieldErrors.new_password}
              required
            >
              {(control) => (
                <div>
                  <PasswordInput
                    {...control}
                    name="new-password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <PasswordChecklist password={password} />
                </div>
              )}
            </Field>
            <Button
              type="submit"
              loading={submitting}
              disabled={!ready}
              className="w-full"
            >
              บันทึกรหัสผ่านใหม่
            </Button>
            {expired ? (
              <p className="text-center text-sm text-fg-muted">
                <Link
                  href="/forgot-password"
                  className="font-medium text-accent underline underline-offset-2"
                >
                  ขอลิงก์ใหม่อีกครั้ง
                </Link>
              </p>
            ) : null}

          </form>
        </CardBody>
      </Card>
    </AuthLayout>
  );
}
