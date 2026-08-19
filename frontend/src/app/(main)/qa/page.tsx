"use client";

/**
 * คำถามที่พบบ่อย (FAQ) - general how-does-the-platform-work answers.
 *
 * Static, honest content: every answer describes behaviour that exists
 * today and links only to real pages (no self-service password reset
 * exists, so that answer routes through /support where the team can
 * send a reset link). Recipe/course questions belong to the community
 * board at `/threads` - this page covers everything the support inbox
 * would otherwise repeat.
 */

import Link from "next/link";
import type { Route } from "next";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon, type UiIconName } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";

type FaqItem = {
  q: string;
  a: string;
  links?: Array<{ href: Route; label: string }>;
};

type FaqSection = {
  key: string;
  icon: UiIconName;
  title: string;
  items: FaqItem[];
};

const SECTIONS: FaqSection[] = [
  {
    key: "account",
    icon: "user",
    title: "บัญชีและการเข้าสู่ระบบ",
    items: [
      {
        q: "สมัครสมาชิกต้องทำอย่างไร?",
        a: "กด “สมัครสมาชิก” ที่มุมขวาบน กรอกชื่อผู้ใช้ อีเมล และรหัสผ่าน จากนั้นระบบจะส่งอีเมลยืนยันไปให้ กดลิงก์ในอีเมลแล้วเริ่มใช้งานได้เลย",
        links: [{ href: "/register", label: "ไปสมัครสมาชิก" }],
      },
      {
        q: "อีเมลยืนยันไม่เข้า ทำอย่างไรดี?",
        a: "เช็คโฟลเดอร์สแปม/อีเมลขยะก่อน ถ้ายังไม่พบ ติดต่อทีมงานผ่านศูนย์ช่วยเหลือเพื่อให้ส่งอีเมลยืนยันอีกครั้ง",
        links: [{ href: "/support", label: "ศูนย์ช่วยเหลือ" }],
      },
      {
        q: "ลืมรหัสผ่าน ต้องทำอย่างไร?",
        a: "แจ้งทีมงานผ่านศูนย์ช่วยเหลือพร้อมอีเมลที่ใช้สมัคร ทีมงานจะส่งลิงก์ตั้งรหัสผ่านใหม่ไปที่อีเมลของคุณ",
        links: [{ href: "/support", label: "ติดต่อทีมงาน" }],
      },
      {
        q: "เปลี่ยนชื่อที่แสดง รูปโปรไฟล์ หรือรหัสผ่านได้ที่ไหน?",
        a: "ที่หน้าตั้งค่า แก้ไขข้อมูลโปรไฟล์และความปลอดภัยของบัญชีได้ทั้งหมดจากที่เดียว",
        links: [{ href: "/settings", label: "ไปหน้าตั้งค่า" }],
      },
    ],
  },
  {
    key: "courses",
    icon: "graduation",
    title: "คอร์สเรียนและใบประกาศนียบัตร",
    items: [
      {
        q: "ลงเรียนคอร์สต้องเสียเงินไหม?",
        a: "ทุกคอร์สบน KawaiiBake เรียนฟรี เพียงเข้าสู่ระบบแล้วกด “ลงเรียน” ในหน้าคอร์สที่สนใจ",
        links: [{ href: "/courses", label: "ดูคอร์สทั้งหมด" }],
      },
      {
        q: "ระบบนับความคืบหน้าการเรียนอย่างไร?",
        a: "เมื่อเรียนจบแต่ละบทให้กดทำเครื่องหมายว่าเรียนจบ พอครบทุกบทที่เผยแพร่ คอร์สจะนับว่าเรียนจบโดยอัตโนมัติ",
      },
      {
        q: "ใบประกาศนียบัตรได้รับเมื่อไหร่?",
        a: "เมื่อเรียนจบคอร์สแล้ว รับใบประกาศของคอร์สนั้นได้ทันทีที่หน้าใบประกาศนียบัตรของคุณ",
        links: [{ href: "/certificates", label: "หน้าใบประกาศนียบัตร" }],
      },
      {
        q: "เลิกเรียนกลางคันแล้วประวัติการเรียนหายไหม?",
        a: "ไม่หาย ประวัติบทเรียนที่เรียนจบยังอยู่ครบ กลับมาลงเรียนใหม่เมื่อไหร่ก็เรียนต่อจากจุดเดิมได้",
      },
    ],
  },
  {
    key: "recipes",
    icon: "chef-hat",
    title: "สูตรขนมและการเผยแพร่",
    items: [
      {
        q: "แชร์สูตรของตัวเองได้ไหม?",
        a: "ได้ สมาชิกทุกคนสร้างสูตรได้จากหน้าสูตรขนม บันทึกเป็นฉบับร่างไว้ก่อน แล้วค่อยเผยแพร่เมื่อพร้อม",
        links: [{ href: "/recipes", label: "ไปหน้าสูตรขนม" }],
      },
      {
        q: "รูปหน้าปกใช้ไฟล์แบบไหนได้บ้าง?",
        a: "ไฟล์ภาพทั่วไป เช่น JPG, PNG หรือ WebP (ไม่รองรับ SVG) แนะนำภาพแนวนอนเพื่อให้แสดงผลสวยบนการ์ด",
      },
      {
        q: "รีวิวสูตรหรือคอร์สได้อย่างไร?",
        a: "เข้าไปที่หน้าสูตรหรือคอร์สนั้น ๆ แล้วให้คะแนนพร้อมเขียนรีวิวได้ในส่วนรีวิวด้านล่างของหน้า",
      },
    ],
  },
  {
    key: "community",
    icon: "chat",
    title: "ชุมชนและกระทู้ถาม-ตอบ",
    items: [
      {
        q: "โพสต์อวดผลงานกับชุมชนได้ที่ไหน?",
        a: "ที่หน้าชุมชน กด “สร้างโพสต์” แนบรูปผลงานพร้อมคำบรรยายได้เลย",
        links: [{ href: "/community", label: "ไปหน้าชุมชน" }],
      },
      {
        q: "มีคำถามเกี่ยวกับสูตรหรือคอร์ส ถามใครได้บ้าง?",
        a: "ตั้งกระทู้ในหน้ากระทู้ถาม-ตอบ โดยเลือกสูตรหรือคอร์สที่จะถาม ชุมชนและผู้สอนจะช่วยตอบ หรือถามผู้ช่วย AI ได้ตลอด 24 ชั่วโมง",
        links: [
          { href: "/threads", label: "กระทู้ถาม-ตอบ" },
          { href: "/assistant", label: "ผู้ช่วย AI" },
        ],
      },
      {
        q: "“คำตอบที่ดีที่สุด” ในกระทู้คืออะไร?",
        a: "ผู้ตั้งกระทู้เลือกคำตอบที่ช่วยแก้ปัญหาได้จริงหนึ่งคำตอบ กระทู้จะติดป้ายว่ามีคำตอบที่เลือกแล้ว และผู้ตอบจะได้รับการแจ้งเตือน",
      },
    ],
  },
  {
    key: "privacy",
    icon: "shield",
    title: "การแจ้งเตือนและความเป็นส่วนตัว",
    items: [
      {
        q: "ปิดการแจ้งเตือนบางประเภทได้ไหม?",
        a: "ได้ ที่หน้าตั้งค่า ส่วน “การแจ้งเตือนในแอป” เลือกเปิด-ปิดได้เป็นรายประเภท",
        links: [{ href: "/settings", label: "ตั้งค่าการแจ้งเตือน" }],
      },
      {
        q: "ข้อมูลส่วนตัวถูกเปิดเผยแค่ไหน?",
        a: "โปรไฟล์สาธารณะแสดงเฉพาะชื่อที่แสดงและผลงานของคุณ อีเมลกับชื่อ-นามสกุลจริงไม่แสดงต่อสาธารณะ อ่านรายละเอียดได้ในนโยบายความเป็นส่วนตัว",
        links: [
          { href: "/legal?doc=privacy" as Route, label: "นโยบายความเป็นส่วนตัว" },
        ],
      },
      {
        q: "พบโพสต์หรือเนื้อหาไม่เหมาะสม แจ้งได้ที่ไหน?",
        a: "แจ้งทีมงานผ่านศูนย์ช่วยเหลือ ทีมงานจะตรวจสอบและซ่อนเนื้อหาที่ผิดกติกา",
        links: [{ href: "/support", label: "แจ้งทีมงาน" }],
      },
    ],
  },
  {
    key: "troubleshooting",
    icon: "alert",
    title: "ปัญหาการใช้งาน",
    items: [
      {
        q: "เว็บช้า ภาพไม่ขึ้น หรือเจอข้อผิดพลาด ทำอย่างไร?",
        a: "ลองรีเฟรชหน้าอีกครั้งก่อน ถ้ายังพบปัญหา เขียนเล่าอาการ (หน้าที่เกิด เวลา และข้อความแจ้งเตือนถ้ามี) ส่งมาที่อีเมลทีมงานในศูนย์ช่วยเหลือ",
        links: [{ href: "/support", label: "ศูนย์ช่วยเหลือ" }],
      },
      {
        q: "ใช้งานบนมือถือได้ไหม?",
        a: "ได้ ทุกหน้าของเว็บรองรับหน้าจอมือถือ ไม่ต้องติดตั้งแอปเพิ่ม",
      },
    ],
  },
];

const TOTAL_COUNT = SECTIONS.reduce(
  (sum, section) => sum + section.items.length,
  0,
);

export default function FaqPage() {
  const [queryInput, setQueryInput] = useState("");
  const query = queryInput.trim().toLowerCase();

  const sections = SECTIONS.map((section) => ({
    ...section,
    items: query
      ? section.items.filter((item) =>
          `${item.q} ${item.a}`.toLowerCase().includes(query),
        )
      : section.items,
  })).filter((section) => section.items.length > 0);
  const matchCount = sections.reduce(
    (sum, section) => sum + section.items.length,
    0,
  );

  return (
    <PageContainer>
      <PageHeader
        title="คำถามที่พบบ่อย (FAQ)"
        description="คำตอบสั้น ๆ สำหรับคำถามการใช้งานทั่วไป - ส่วนคำถามเทคนิคการอบหรือเนื้อหาคอร์ส ตั้งกระทู้ถามชุมชนได้เลย"
      />

      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            type="search"
            value={queryInput}
            placeholder="ค้นหาคำถาม เช่น ใบประกาศ, ลืมรหัสผ่าน…"
            aria-label="ค้นหาคำถามที่พบบ่อย"
            className="max-w-md rounded-full"
            onChange={(event) => setQueryInput(event.target.value)}
          />
          <p className="text-sm text-fg-subtle">
            {query
              ? `พบ ${matchCount} จาก ${TOTAL_COUNT} คำถาม`
              : `ทั้งหมด ${TOTAL_COUNT} คำถาม`}
          </p>
        </div>

        {sections.length === 0 ? (
          <EmptyState
            icon={<Icon name="ui/search" className="size-8 text-fg-subtle" />}
            title="ไม่พบคำถามที่ค้นหา"
            description="ลองเปลี่ยนคำค้น หรือตั้งกระทู้ถามชุมชน / ติดต่อทีมงานด้านล่างได้เลย"
          />
        ) : (
          sections.map((section) => (
            <section key={section.key} aria-label={section.title}>
              <h2 className="font-display mb-3 flex items-center gap-2 text-lg font-medium text-fg">
                <span
                  aria-hidden
                  className="flex size-8 items-center justify-center rounded-full bg-accent-subtle text-accent"
                >
                  <Icon name={`ui/${section.icon}`} className="size-4" />
                </span>
                {section.title}
              </h2>
              <div className="space-y-2">
                {section.items.map((item) => (
                  <details
                    key={item.q}
                    open={query ? true : undefined}
                    className="group rounded-control border border-edge bg-surface open:border-edge-strong"
                  >
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-fg [&::-webkit-details-marker]:hidden">
                      {item.q}
                      <Icon
                        name="ui/chevron-down"
                        className="size-4 shrink-0 text-fg-subtle transition-transform group-open:rotate-180"
                      />
                    </summary>
                    <div className="border-t border-edge px-4 py-3">
                      <p className="text-sm text-fg-muted">{item.a}</p>
                      {item.links?.length ? (
                        <p className="mt-2 flex flex-wrap gap-2">
                          {item.links.map((link) => (
                            <Link
                              key={`${link.href}${link.label}`}
                              href={link.href}
                              className="text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
                            >
                              {link.label} →
                            </Link>
                          ))}
                        </p>
                      ) : null}
                    </div>
                  </details>
                ))}
              </div>
            </section>
          ))
        )}

        <Card className="kb-hero border-none">
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-display font-medium text-fg">
                ยังไม่เจอคำตอบที่ตามหา?
              </p>
              <p className="text-sm text-fg-muted">
                ถามชุมชนกับผู้สอนในกระทู้ หรือเขียนเล่าปัญหามาหาทีมงานโดยตรง
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href="/threads">
                <Button size="sm">ตั้งกระทู้ถามชุมชน</Button>
              </Link>
              <Link href="/support">
                <Button size="sm" variant="secondary">
                  ติดต่อทีมงาน
                </Button>
              </Link>
            </div>
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}
