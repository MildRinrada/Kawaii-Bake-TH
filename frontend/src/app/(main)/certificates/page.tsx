"use client";

/**
 * Certificate & achievement centre.
 *
 * Everything here is backed by real endpoints: the issued ledger
 * (`/me/certificates/`), course completion facts (`/me/progress/`), and
 * issuing (`POST /courses/{slug}/certificate/`). A completed course is
 * shown as **pending** — never as an issued credential — until the
 * backend actually issues one. There is no server-side certificate
 * file, so the document is rendered from its stored fields and the
 * download path is the browser's print/Save-as-PDF, labelled as such.
 * Verification links point at the real anonymous verification endpoint
 * through `/verify/{token}`.
 */

import Link from "next/link";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Certificate, MyCourseProgress } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { useToast } from "@/components/ui/toast";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CertificateSheet,
  formatThaiDate,
} from "@/components/content/certificate-sheet";
import { cn } from "@/lib/cn";

type Filter = "all" | "earned" | "pending" | "in_progress";

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "ทั้งหมด" },
  { value: "earned", label: "ได้รับแล้ว" },
  { value: "pending", label: "รอออกใบ" },
  { value: "in_progress", label: "กำลังเรียน" },
];

function verificationUrl(token: string): string {
  return `${window.location.origin}/verify/${token}`;
}

/* ------------------------------------------------------------------ */
/* Full-screen viewer                                                  */
/* ------------------------------------------------------------------ */

function CertificateViewer({
  certificate,
  onClose,
}: {
  certificate: Certificate;
  onClose: () => void;
}) {
  const { toast } = useToast();

  async function copy(text: string, message: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast(message, "success");
    } catch {
      toast("คัดลอกไม่สำเร็จ", "danger");
    }
  }

  async function share() {
    const url = verificationUrl(certificate.verification_token);
    if (navigator.share) {
      try {
        await navigator.share({
          url,
          title: `ใบประกาศนียบัตร — ${certificate.course_title}`,
        });
        return;
      } catch {
        // Share sheet dismissed — fall through to copying.
      }
    }
    await copy(url, "คัดลอกลิงก์ตรวจสอบแล้ว");
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`ใบประกาศนียบัตร ${certificate.course_title}`}
      className="fixed inset-0 z-50 flex flex-col bg-canvas"
    >
      <div className="kb-no-print flex items-center justify-between border-b border-edge px-4 py-3 sm:px-6">
        <p className="font-display truncate font-medium text-fg">
          {certificate.course_title}
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label="ปิดใบประกาศนียบัตร"
          className="flex size-11 items-center justify-center rounded-full hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/close" className="size-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="kb-print-target">
            <CertificateSheet certificate={certificate} />
          </div>

          <dl className="kb-no-print grid gap-x-6 gap-y-3 rounded-surface bg-surface-sunken/60 p-5 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-fg-subtle">ผู้รับ</dt>
              <dd className="text-fg">{certificate.student_name}</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">คอร์ส</dt>
              <dd className="text-fg">{certificate.course_title}</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">เรียนจบเมื่อ</dt>
              <dd className="text-fg">{formatThaiDate(certificate.completed_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">ออกใบเมื่อ</dt>
              <dd className="text-fg">{formatThaiDate(certificate.issued_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">เลขที่ใบประกาศ</dt>
              <dd className="font-mono text-fg">{certificate.certificate_number}</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">สถานะ</dt>
              <dd>
                {certificate.status === "revoked" ? (
                  <Badge tone="danger"><Icon name="ui/close" className="size-3.5" /> ถูกเพิกถอน</Badge>
                ) : (
                  <Badge tone="mint"><Icon name="ui/check" className="size-3.5" /> ตรวจสอบได้</Badge>
                )}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-fg-subtle">ผู้ออกใบ</dt>
              <dd className="text-fg">KawaiiBake</dd>
            </div>
          </dl>

          <p className="kb-no-print text-center text-xs text-fg-subtle">
            ใครก็ตรวจสอบใบนี้ได้ที่ลิงก์ตรวจสอบ โดยไม่ต้องเข้าสู่ระบบ
          </p>
        </div>
      </div>

      <div className="kb-no-print border-t border-edge bg-surface px-4 py-4 sm:px-6">
        <div className="mx-auto flex w-full max-w-3xl flex-wrap justify-center gap-2.5">
          <Button onClick={() => window.print()}><Icon name="ui/print" className="size-4" /> พิมพ์ / บันทึกเป็น PDF</Button>
          <Button variant="secondary" onClick={() => void share()}>
            <Icon name="ui/share" className="size-4" /> แชร์
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              void copy(
                verificationUrl(certificate.verification_token),
                "คัดลอกลิงก์ตรวจสอบแล้ว",
              )
            }
          >
            <Icon name="ui/link" className="size-4" /> คัดลอกลิงก์ตรวจสอบ
          </Button>
          <Button
            variant="ghost"
            onClick={() =>
              void copy(certificate.certificate_number, "คัดลอกเลขที่ใบประกาศแล้ว")
            }
          >
            คัดลอกเลขที่
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Cards                                                               */
/* ------------------------------------------------------------------ */

function CertificateCard({
  certificate,
  onOpen,
}: {
  certificate: Certificate;
  onOpen: () => void;
}) {
  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <button
        type="button"
        onClick={onOpen}
        aria-label={`เปิดใบประกาศนียบัตร ${certificate.course_title}`}
        className="block w-full bg-butter-soft/40 p-3 transition-transform duration-150 hover:scale-[1.01] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        <CertificateSheet certificate={certificate} />
      </button>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <div className="flex items-start justify-between gap-2">
          <h2 className="font-display line-clamp-2 font-medium text-fg">
            {certificate.course_title}
          </h2>
          {certificate.status === "revoked" ? (
            <Badge tone="danger"><Icon name="ui/close" className="size-3.5" /> ถูกเพิกถอน</Badge>
          ) : (
            <Badge tone="mint"><Icon name="ui/check" className="size-3.5" /> ได้รับแล้ว</Badge>
          )}
        </div>
        <p className="text-xs text-fg-subtle">
          ออกให้เมื่อ {formatThaiDate(certificate.issued_at)}
        </p>
        <p className="font-mono text-xs text-fg-subtle">
          {certificate.certificate_number}
        </p>
        <Button size="sm" className="mt-auto w-full" onClick={onOpen}>
          ดูใบประกาศนียบัตร
        </Button>
      </div>
    </Card>
  );
}

function PendingCard({
  course,
  onIssued,
}: {
  course: MyCourseProgress;
  onIssued: () => void;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);

  async function issue() {
    setBusy(true);
    try {
      await api.post(`/courses/${course.slug}/certificate/`);
      toast("ออกใบประกาศนียบัตรเรียบร้อย", "success");
      onIssued();
    } catch (error) {
      if (error instanceof ApiError && error.code === "course_not_completed") {
        toast("ต้องเรียนให้ครบทุกบทก่อนนะ", "danger");
      } else {
        toast("ออกใบประกาศไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex h-full flex-col border-butter-ink/20 bg-butter-soft/30">
      <CardBody className="flex flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <Badge tone="butter"><Icon name="ui/timer" className="size-3.5" /> รอออกใบ</Badge>
        </div>
        <h2 className="font-display font-medium text-fg">{course.title}</h2>
        <p className="text-sm text-fg-muted">
          เรียนจบครบ {course.total_lessons} บทเรียนแล้ว
          {course.completed_at
            ? ` เมื่อ ${formatThaiDate(course.completed_at)}`
            : ""}{" "}
          — ยังไม่ได้ออกใบประกาศ
        </p>
        <Button
          size="sm"
          loading={busy}
          className="mt-auto w-full"
          onClick={() => void issue()}
        >
          ขอรับใบประกาศนียบัตร
        </Button>
      </CardBody>
    </Card>
  );
}

function InProgressCard({ course }: { course: MyCourseProgress }) {
  return (
    <Card className="flex h-full flex-col">
      <CardBody className="flex flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <Icon name="ui/book" className="size-8 text-fg-subtle" />
          <Badge tone="lavender">กำลังเรียน</Badge>
        </div>
        <h2 className="font-display font-medium text-fg">{course.title}</h2>
        <p className="text-sm text-fg-muted">
          เรียนแล้ว {course.completed_lessons} จาก {course.total_lessons} บทเรียน
        </p>
        <div className="flex items-center gap-3">
          <ProgressBar
            percent={course.percentage}
            label={`ความคืบหน้า ${course.title}`}
          />
          <span className="shrink-0 text-sm font-medium text-lavender-ink">
            {course.percentage}%
          </span>
        </div>
        <Link href={`/courses/${course.slug}`} className="mt-auto block">
          <Button size="sm" variant="secondary" className="w-full">
            เรียนต่อ →
          </Button>
        </Link>
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function CertificatesContent() {
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<number | null>(null);

  const certificates = useApiQuery(
    (signal) =>
      api.get<Paginated<Certificate>>("/me/certificates/", {
        query: { page_size: 50 },
        signal,
      }),
    [],
  );
  const progress = useApiQuery(
    (signal) =>
      api.get<{ courses: MyCourseProgress[] }>("/me/progress/", { signal }),
    [],
  );

  const issued = certificates.data?.results ?? [];
  const courses = progress.data?.courses ?? [];
  const certifiedTitles = new Set(issued.map((item) => item.course_title));

  // A completed course without a certificate is *pending*, never issued.
  const pending = courses.filter(
    (course) => course.completed_at && !certifiedTitles.has(course.title),
  );
  const inProgress = courses.filter((course) => !course.completed_at);
  const completedCount = courses.filter((course) => course.completed_at).length;
  const latest = issued[0];
  const openCertificate = issued.find((item) => item.id === openId) ?? null;

  const loading = certificates.loading || progress.loading;
  const showEarned = filter === "all" || filter === "earned";
  const showPending = filter === "all" || filter === "pending";
  const showInProgress = filter === "all" || filter === "in_progress";
  const nothingAtAll =
    issued.length === 0 && pending.length === 0 && inProgress.length === 0;

  function refetchAll() {
    certificates.refetch();
    progress.refetch();
  }

  if (loading) {
    return (
      <>
        <PageHeader title="ใบประกาศนียบัตรของฉัน" />
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-72 w-full rounded-surface" />
          ))}
        </div>
      </>
    );
  }
  if (certificates.error) {
    return (
      <>
        <PageHeader title="ใบประกาศนียบัตรของฉัน" />
        <ErrorState error={certificates.error} onRetry={refetchAll} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="ใบประกาศนียบัตรของฉัน"
        description="หลักฐานการเรียนจบคอร์สใน KawaiiBake — ตรวจสอบได้จริงทุกใบ"
      />

      {/* Achievement summary — every figure from real data */}
      {!nothingAtAll ? (
        <div className="mb-7 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-surface bg-butter-soft/40 px-5 py-4 text-sm">
          <p className="flex items-baseline gap-1.5">
            <Icon name="ui/scroll" className="size-4" />
            <strong className="font-display text-lg text-fg">
              {issued.length}
            </strong>
            <span className="text-fg-muted">ใบประกาศที่ได้รับ</span>
          </p>
          <p className="flex items-baseline gap-1.5">
            <Icon name="ui/graduation" className="size-4" />
            <strong className="font-display text-lg text-fg">
              {completedCount}
            </strong>
            <span className="text-fg-muted">คอร์สที่เรียนจบ</span>
          </p>
          {latest ? (
            <p className="text-fg-muted">
              <Icon name="ui/sparkle" className="size-3.5 align-[-2px]" /> ล่าสุด{" "}
              {formatThaiDate(latest.issued_at)}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Filters — only states this account actually has */}
      {!nothingAtAll ? (
        <div
          className="mb-6 flex flex-wrap items-center gap-2"
          role="group"
          aria-label="กรองตามสถานะ"
        >
          {FILTERS.filter(
            (item) =>
              item.value === "all" ||
              (item.value === "earned" && issued.length > 0) ||
              (item.value === "pending" && pending.length > 0) ||
              (item.value === "in_progress" && inProgress.length > 0),
          ).map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={filter === item.value}
              onClick={() => setFilter(item.value)}
              className={cn(
                "rounded-full px-3.5 py-1.5 text-sm transition-colors",
                "focus-visible:outline-2 focus-visible:outline-focus",
                filter === item.value
                  ? "bg-accent font-medium text-fg-inverted shadow-raised"
                  : "bg-surface text-fg-muted shadow-raised hover:text-fg",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}

      {nothingAtAll ? (
        <EmptyState
          icon={<Icon name="ui/scroll" className="size-8 text-fg-subtle" />}
          title="ยังไม่มีใบประกาศนียบัตร"
          description="เรียนคอร์สให้จบครบทุกบทเรียน แล้วขอรับใบประกาศนียบัตรที่ตรวจสอบได้จริง"
          action={
            <Link href="/courses">
              <Button>ดูคอร์สเรียน</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-10">
          {showEarned && issued.length > 0 ? (
            <section aria-label="ใบประกาศที่ได้รับ">
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {issued.map((certificate) => (
                  <CertificateCard
                    key={certificate.id}
                    certificate={certificate}
                    onOpen={() => setOpenId(certificate.id)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {showPending && pending.length > 0 ? (
            <section aria-label="คอร์สที่เรียนจบแล้วแต่ยังไม่ได้ใบประกาศ">
              <h2 className="font-display mb-1 text-lg font-medium text-fg">
                เรียนจบแล้ว รอออกใบประกาศ
              </h2>
              <p className="mb-4 text-sm text-fg-muted">
                เรียนจบคอร์สแล้ว แต่ยังไม่ได้ออกใบประกาศ — กดขอรับได้เลย
              </p>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {pending.map((course) => (
                  <PendingCard
                    key={course.slug}
                    course={course}
                    onIssued={refetchAll}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {showInProgress && inProgress.length > 0 ? (
            <section aria-label="คอร์สที่กำลังเรียน">
              <h2 className="font-display mb-1 text-lg font-medium text-fg">
                กำลังเรียนอยู่
              </h2>
              <p className="mb-4 text-sm text-fg-muted">
                เรียนให้ครบทุกบทเรียนเพื่อรับใบประกาศนียบัตร
              </p>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {inProgress.map((course) => (
                  <InProgressCard key={course.slug} course={course} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}

      {openCertificate ? (
        <CertificateViewer
          certificate={openCertificate}
          onClose={() => setOpenId(null)}
        />
      ) : null}
    </>
  );
}

export default function CertificatesPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <CertificatesContent />
      </RequireAuth>
    </PageContainer>
  );
}
