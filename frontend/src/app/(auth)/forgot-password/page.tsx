"use client";

/**
 * "ลืมรหัสผ่าน" - ask for a reset link.
 *
 * Same two-column surface as sign-in, because it is the same errand seen
 * one step later; the column explains what is about to happen instead of
 * repeating the pitch, since somebody here already has an account.
 *
 * The endpoint answers **202 for every address**, known or not, so this
 * screen shows the same confirmation either way. That is the point: a
 * different answer for a registered address would make this page a
 * directory of who has an account here. The copy therefore says what was
 * *done* ("ถ้ามีบัญชี... เราส่งลิงก์ไปแล้ว"), never what was found.
 *
 * Accounts created through Google have no password to reset; the backend
 * already excludes them from reset mail, and the confirmation's wording
 * covers that case without naming it.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { AuthAside, AuthLayout, type AuthPoint } from "@/components/auth/auth-aside";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { useFormSubmit } from "@/lib/forms/use-form";

/** What is about to happen, so nobody has to wonder mid-flow. */
const STEPS: AuthPoint[] = [
  {
    icon: "note",
    title: "กรอกอีเมลที่ใช้สมัคร",
    body: "อีเมลเดียวกับที่เข้าสู่ระบบตามปกติ",
  },
  {
    icon: "bell",
    title: "เปิดลิงก์ในอีเมล",
    body: "ลิงก์ใช้ได้ 1 ชั่วโมง แล้วหมดอายุเพื่อความปลอดภัย",
  },
  {
    icon: "lock",
    title: "ตั้งรหัสผ่านใหม่",
    body: "อุปกรณ์อื่นที่ค้างอยู่จะถูกออกจากระบบให้อัตโนมัติ",
  },
];

export default function ForgotPasswordPage() {
  const { submitting, formError, fieldErrors, submit } = useFormSubmit();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const ok = await submit(async () => {
      await api.post("/auth/password-reset/", {
        body: { email: email.trim().toLowerCase() },
      });
    });
    if (ok) setSent(true);
  }

  return (
    <AuthLayout
      aside={
        <AuthAside
          title={sent ? "เช็กอีเมลได้เลย" : "ลืมรหัสผ่านใช่ไหม"}
          lead={
            sent
              ? "ทำตามสามขั้นนี้แล้วกลับมาเข้าสู่ระบบได้เลย"
              : "ไม่เป็นไร ตั้งใหม่ได้ในสามขั้นตอน"
          }
          points={STEPS}
          photo="cookies"
          animateKey={sent ? "sent" : "ask"}
        />
      }
    >
      <Card className="w-full">
        {sent ? (
          <CardBody className="space-y-4 text-center">
            <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-success-subtle">
              <Icon name="ui/check" tint className="size-7 text-success" />
            </span>
            <h2 className="font-display text-lg font-medium text-fg">
              ส่งลิงก์แล้ว
            </h2>
            <p className="text-sm leading-relaxed text-fg-muted">
              ถ้า <strong className="font-medium text-fg">{email.trim()}</strong>{" "}
              มีบัญชีที่ตั้งรหัสผ่านไว้ เราส่งลิงก์ตั้งรหัสผ่านใหม่ไปให้แล้ว
              ลิงก์ใช้ได้ 1 ชั่วโมง
            </p>
            <p className="rounded-control bg-surface-sunken px-3.5 py-2.5 text-left text-sm leading-relaxed text-fg-muted">
              ไม่เจออีเมล? ลองดูในกล่องสแปม  ถ้าสมัครไว้ด้วยปุ่ม Google
              บัญชีจะไม่มีรหัสผ่านให้ตั้ง ให้กดเข้าสู่ระบบด้วย Google แทน
            </p>
            <div className="flex flex-col gap-2">
              <Link href="/login" className="block">
                <Button className="w-full">กลับไปหน้าเข้าสู่ระบบ</Button>
              </Link>
              <button
                type="button"
                onClick={() => setSent(false)}
                className="text-sm text-fg-muted underline underline-offset-2 hover:text-fg"
              >
                กรอกอีเมลอื่นอีกครั้ง
              </button>
            </div>
          </CardBody>
        ) : (
          <CardBody className="space-y-4">
            <div className="space-y-1">
              <h2 className="font-display text-lg font-medium text-fg">
                ขอลิงก์ตั้งรหัสผ่านใหม่
              </h2>
              <p className="text-sm text-fg-muted">
                กรอกอีเมลที่ใช้สมัคร แล้วเราจะส่งลิงก์ไปให้
              </p>
            </div>
            <form
              onSubmit={onSubmit}
              noValidate
              aria-label="ขอลิงก์ตั้งรหัสผ่านใหม่"
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
              <Button
                type="submit"
                loading={submitting}
                disabled={!email.trim()}
                className="w-full"
              >
                ส่งลิงก์ตั้งรหัสผ่านใหม่
              </Button>
              <p className="text-center text-sm text-fg-muted">
                นึกออกแล้ว?{" "}
                <Link href="/login" className="font-medium text-fg underline">
                  กลับไปเข้าสู่ระบบ
                </Link>
              </p>
            </form>
          </CardBody>
        )}
      </Card>
    </AuthLayout>
  );
}
