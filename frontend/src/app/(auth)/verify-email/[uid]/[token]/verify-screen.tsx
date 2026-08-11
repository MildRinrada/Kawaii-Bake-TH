"use client";

/**
 * The landing page of the verification link in the email.
 *
 * The URL shape (`/verify-email/{uid}/{token}`) is dictated by the
 * backend's `FRONTEND_EMAIL_VERIFY_PATH`; this screen POSTs the pair to
 * `POST /auth/verify-email/` and walks the visitor to `/login` with the
 * one-time success flag. Verification is a real state change, so it runs
 * behind an explicit button - an email scanner that prefetches the link
 * must not consume anything by merely loading the page.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";

export function VerifyEmailScreen({
  uid,
  token,
}: {
  uid: string;
  token: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/verify-email/", { body: { uid, token } });
      // The login page reads this flag once and shows the confirmation.
      router.replace("/login?verified=1");
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 400
          ? "ลิงก์ยืนยันไม่ถูกต้องหรือหมดอายุแล้ว - เข้าสู่ระบบเพื่อขอส่งลิงก์ใหม่ได้จากหน้าตั้งค่า"
          : "ยืนยันไม่สำเร็จ ลองอีกครั้งนะ",
      );
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title="ยืนยันอีเมล" />
      <CardBody className="space-y-4 text-center">
        <Icon name="ui/check-circle" className="mx-auto size-12" />
        <p className="text-sm leading-relaxed text-fg">
          กดปุ่มด้านล่างเพื่อยืนยันว่าคุณเป็นเจ้าของอีเมลนี้
        </p>
        {error ? (
          <p
            role="alert"
            className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
          >
            {error}
          </p>
        ) : null}
        <Button loading={busy} onClick={() => void confirm()} className="w-full">
          ยืนยันอีเมลของฉัน
        </Button>
        <p className="text-sm text-fg-muted">
          <Link href="/login" className="font-medium text-fg underline">
            ไปหน้าเข้าสู่ระบบ
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}
