"use client";

/**
 * ศูนย์ช่วยเหลือ - every real way to get help, on one page.
 *
 * Honest by construction: each card points at a channel that actually
 * exists (the FAQ, the question board, the AI assistant, the community,
 * the legal reading room). The contact address comes from `NEXT_PUBLIC_SUPPORT_EMAIL`
 * (falling back to the dev placeholder) - configuration, not a
 * fabricated inbox.
 */

import Link from "next/link";
import type { Route } from "next";

import { Card, CardBody } from "@/components/ui/card";
import { Icon, type UiIconName } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";

const SUPPORT_EMAIL =
  process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "support@kawaiibake.local";

const CHANNELS: Array<{
  href: Route;
  icon: UiIconName;
  title: string;
  description: string;
  action: string;
}> = [
  {
    href: "/qa",
    icon: "info",
    title: "คำถามที่พบบ่อย (FAQ)",
    description:
      "คำตอบเรื่องบัญชี คอร์ส ใบประกาศ และการใช้งานทั่วไป รวมไว้ที่เดียว ค้นหาได้ทันที",
    action: "ไปที่คำถามที่พบบ่อย",
  },
  {
    href: "/threads",
    icon: "chat",
    title: "กระทู้ถาม-ตอบ",
    description:
      "ติดปัญหาเรื่องสูตรหรือคอร์ส? ตั้งกระทู้ถามชุมชนและผู้สอนได้โดยตรง กระทู้เก่าค้นหาได้ทั้งหมด",
    action: "ไปที่กระทู้ถาม-ตอบ",
  },
  {
    href: "/assistant",
    icon: "bell",
    title: "ผู้ช่วย AI",
    description:
      "ตอบคำถามเรื่องการอบขนมเป็นภาษาไทยได้ทันที ตลอด 24 ชั่วโมง เหมาะกับคำถามเทคนิคเร่งด่วน",
    action: "คุยกับผู้ช่วย AI",
  },
  {
    href: "/community",
    icon: "star",
    title: "ชุมชนนักอบ",
    description:
      "แชร์ผลงาน ขอคำติชม และเรียนรู้จากเพื่อนนักอบคนอื่น ๆ ในบรรยากาศเป็นกันเอง",
    action: "ไปที่ชุมชน",
  },
  {
    href: "/legal",
    icon: "check-circle",
    title: "ข้อตกลงและนโยบาย",
    description:
      "ข้อตกลงการใช้งาน นโยบายความเป็นส่วนตัว (PDPA) และนโยบายคุกกี้ ฉบับเต็มอ่านได้ที่นี่",
    action: "อ่านนโยบายทั้งหมด",
  },
];

export default function SupportPage() {
  return (
    <PageContainer>
      <PageHeader
        title="ศูนย์ช่วยเหลือและติดต่อเรา"
        description="เลือกช่องทางที่ตรงกับเรื่องของคุณ - ทุกช่องทางด้านล่างมีคน(หรือ AI) คอยดูแลจริง"
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {CHANNELS.map((channel) => (
          <Card
            key={channel.href}
            className="transition-shadow hover:shadow-overlay"
          >
            <CardBody className="flex h-full flex-col">
              <span
                aria-hidden
                className="flex size-10 items-center justify-center rounded-full bg-accent-subtle text-accent"
              >
                <Icon name={`ui/${channel.icon}`} className="size-5" />
              </span>
              <h2 className="font-display mt-3 font-medium text-fg">
                {channel.title}
              </h2>
              <p className="mt-1 flex-1 text-sm text-fg-muted">
                {channel.description}
              </p>
              <Link
                href={channel.href}
                className="mt-3 text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
              >
                {channel.action} →
              </Link>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card className="mt-4">
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display font-medium text-fg">
              เรื่องบัญชีหรือปัญหาการใช้งาน
            </h2>
            <p className="mt-1 text-sm text-fg-muted">
              เข้าสู่ระบบไม่ได้ อีเมลยืนยันไม่มา หรือพบข้อผิดพลาดของระบบ -
              เขียนเล่าอาการมาที่อีเมลทีมงานได้เลย
            </p>
          </div>
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            className="rounded-full bg-accent px-5 py-2 text-sm font-medium text-fg-inverted shadow-raised hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            {SUPPORT_EMAIL}
          </a>
        </CardBody>
      </Card>
    </PageContainer>
  );
}
