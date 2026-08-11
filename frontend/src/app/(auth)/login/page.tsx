"use client";

import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/lib/auth/auth-context";
import { useFormSubmit } from "@/lib/forms/use-form";

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { submitting, formError, fieldErrors, submit } = useFormSubmit();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const ok = await submit(() => login(email, password));
    if (ok) router.replace(searchParams.get("next") ?? "/");
  }

  // One-time flag set by the email-verification screen.
  const justVerified = searchParams.get("verified") === "1";

  return (
    <Card>
      <CardHeader title="เข้าสู่ระบบ" />
      <CardBody>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {justVerified ? (
            <p
              role="status"
              className="rounded-control bg-success-subtle px-3 py-2 text-sm text-success"
            >
              ยืนยันอีเมลเรียบร้อยแล้ว - เข้าสู่ระบบเพื่อเริ่มใช้งานได้เลย
            </p>
          ) : null}
          {formError ? (
            <p role="alert" className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger">
              {formError}
            </p>
          ) : null}
          <Field label="อีเมล" errors={fieldErrors.email} required>
            {(control) => (
              <Input
                {...control}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            )}
          </Field>
          <Field label="รหัสผ่าน" errors={fieldErrors.password} required>
            {(control) => (
              <PasswordInput
                {...control}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>
          <Button type="submit" loading={submitting} className="w-full">
            เข้าสู่ระบบ
          </Button>
          <p className="text-center text-sm text-fg-muted">
            ยังไม่มีบัญชี?{" "}
            <Link href="/register" className="font-medium text-fg underline">
              สมัครสมาชิก
            </Link>
          </p>
        </form>
      </CardBody>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
