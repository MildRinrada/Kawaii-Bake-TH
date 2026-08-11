"use client";

/**
 * The stop after registration: "confirm your email first".
 *
 * Registration no longer signs the user in - the account exists but its
 * inbox holds the next step. There is deliberately no resend button
 * here: the resend endpoint requires a session this visitor does not
 * have yet, and a button that always fails is worse than instructions
 * that are true (signing in later offers resend from settings).
 */

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";

function SentContent() {
  const email = useSearchParams().get("email");

  return (
    <Card>
      <CardHeader title="เช็คอีเมลของคุณ" />
      <CardBody className="space-y-4 text-center">
        <Icon name="ui/bell" className="mx-auto size-12" />
        <p className="text-sm leading-relaxed text-fg">
          สมัครสมาชิกสำเร็จแล้ว! เราส่งลิงก์ยืนยันไปที่{" "}
          {email ? (
            <strong className="font-medium">{email}</strong>
          ) : (
            "อีเมลของคุณ"
          )}{" "}
          - เปิดอีเมลแล้วกดลิงก์เพื่อยืนยันว่าคุณเป็นเจ้าของ
        </p>
        <p className="text-sm leading-relaxed text-fg-muted">
          ยืนยันเสร็จแล้วระบบจะพาไปหน้าเข้าสู่ระบบ
          เพื่อให้คุณเข้าใช้งานด้วยตัวเอง
        </p>
        <p className="text-xs leading-relaxed text-fg-subtle">
          ไม่เจออีเมล? ลองดูในกล่องสแปม
          หรือเข้าสู่ระบบภายหลังเพื่อขอส่งลิงก์ใหม่จากหน้าตั้งค่า
        </p>
        <Link href="/login" className="inline-block">
          <Button variant="secondary">ไปหน้าเข้าสู่ระบบ</Button>
        </Link>
      </CardBody>
    </Card>
  );
}

export default function RegisterSentPage() {
  return (
    <Suspense>
      <SentContent />
    </Suspense>
  );
}
