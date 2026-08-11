"use client";

/**
 * Public certificate verification  the employer-facing view.
 *
 * Anonymous by design: it reads `GET /certificates/{token}/`, which the
 * backend serves without a session and which deliberately returns only
 * the printable snapshot (handle as printed, course, dates, verdict) 
 * never an email or user id. An unknown or malformed token is a plain
 * 404, so this page cannot be used to probe for certificates.
 */

import Link from "next/link";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { components } from "@/lib/api/types";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CertificateSheet,
  formatThaiDate,
} from "@/components/content/certificate-sheet";

type Verification = components["schemas"]["CertificateVerification"];

export function VerifyScreen({ token }: { token: string }) {
  const { data, loading, error, refetch } = useApiQuery(
    (signal) =>
      api.get<Verification>(`/certificates/${token}/`, { signal }),
    [token],
  );

  if (loading) {
    return (
      <PageContainer aria-busy="true">
        <Skeleton className="mx-auto mt-6 h-8 w-64" />
        <Skeleton className="mx-auto mt-6 aspect-[1.414/1] w-full max-w-2xl rounded-surface" />
      </PageContainer>
    );
  }

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <PageContainer>
        <div className="mx-auto max-w-xl py-10 text-center">
          {notFound ? (
            <>
              <Icon name="ui/search" className="mx-auto size-12 text-fg-subtle" />
              <h1 className="font-display mt-4 text-2xl font-medium text-fg">
                ไม่พบใบประกาศนียบัตรนี้
              </h1>
              <p className="mt-2 text-sm text-fg-muted">
                ลิงก์ตรวจสอบอาจไม่ถูกต้อง หรือใบประกาศนี้ไม่มีอยู่ในระบบ
                KawaiiBake  ลองตรวจสอบลิงก์อีกครั้งกับผู้ที่ส่งมาให้คุณ
              </p>
              <Link href="/" className="mt-6 inline-block">
                <Button variant="secondary">กลับหน้าแรก</Button>
              </Link>
            </>
          ) : (
            <ErrorState error={error} onRetry={refetch} />
          )}
        </div>
      </PageContainer>
    );
  }

  if (!data) return null;

  const revoked = data.status === "revoked";

  return (
    <PageContainer>
      <div className="mx-auto max-w-3xl py-6">
        <div
          className={`mb-6 rounded-surface px-5 py-4 text-center ${
            revoked ? "bg-danger-subtle" : "bg-mint-soft"
          }`}
        >
          <p
            className={`font-display flex items-center justify-center gap-1.5 text-lg font-medium ${
              revoked ? "text-danger" : "text-mint-ink"
            }`}
          >
            <Icon name={revoked ? "ui/close" : "ui/check"} className="size-5" />
            {revoked
              ? "ใบประกาศนียบัตรนี้ถูกเพิกถอนแล้ว"
              : "ใบประกาศนียบัตรนี้ถูกต้อง"}
          </p>
          <p className="mt-1 text-sm text-fg-muted">
            {revoked
              ? "KawaiiBake ได้เพิกถอนใบประกาศฉบับนี้ จึงไม่ถือเป็นหลักฐานการเรียนจบอีกต่อไป"
              : "ตรวจสอบกับระบบของ KawaiiBake แล้ว  เป็นใบประกาศที่ออกให้จริง"}
          </p>
        </div>

        <CertificateSheet
          certificate={{ ...data, completed_at: undefined }}
        />

        <dl className="mt-6 grid gap-x-6 gap-y-3 rounded-surface bg-surface-sunken/60 p-5 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-fg-subtle">ผู้รับ</dt>
            <dd className="text-fg">{data.student_name}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-subtle">คอร์ส</dt>
            <dd className="text-fg">{data.course_title}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-subtle">ออกใบเมื่อ</dt>
            <dd className="text-fg">{formatThaiDate(data.issued_at)}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-subtle">เลขที่ใบประกาศ</dt>
            <dd className="font-mono text-fg">{data.certificate_number}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-subtle">ผู้ออกใบ</dt>
            <dd className="text-fg">KawaiiBake</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-subtle">สถานะ</dt>
            <dd>
              {revoked ? (
                <Badge tone="danger">ถูกเพิกถอน</Badge>
              ) : (
                <Badge tone="mint">ใช้งานได้</Badge>
              )}
            </dd>
          </div>
        </dl>

        <Card className="mt-6 p-5 text-center">
          <p className="text-sm text-fg-muted">
            KawaiiBake คือแพลตฟอร์มเรียนทำเบเกอรี่ภาษาไทย
            ใบประกาศทุกใบออกให้เมื่อผู้เรียนเรียนจบครบทุกบทเรียนจริงเท่านั้น
          </p>
          <Link href="/courses" className="mt-3 inline-block">
            <Button variant="secondary" size="sm">
              ดูคอร์สเรียนของ KawaiiBake
            </Button>
          </Link>
        </Card>
      </div>
    </PageContainer>
  );
}
