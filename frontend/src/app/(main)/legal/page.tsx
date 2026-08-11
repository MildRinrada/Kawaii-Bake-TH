"use client";

/**
 * The legal reading room: terms, privacy (PDPA), PDPA notice and cookie
 * policy on one public page.
 *
 * Content comes from `GET /legal/` - the documents live in the database
 * and staff edit them from the back office, so this page never hardcodes
 * a word of legal text. `?doc=` deep-links a specific document (the
 * registration form links straight to terms and privacy); the URL is the
 * tab state, so a copied link opens the same document.
 *
 * Bodies are plain text rendered as paragraphs - deliberately not HTML,
 * so the admin editor can never become an injection vector into a public
 * page.
 */

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

import { api } from "@/lib/api/client";
import type { Schemas } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { Card, CardBody } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { RichText } from "@/components/content/rich-text";
import { cn } from "@/lib/cn";

type LegalDocument = Schemas["LegalDocument"];

const KINDS = ["terms", "privacy", "pdpa", "cookie"] as const;
type Kind = (typeof KINDS)[number];

const KIND_LABELS: Record<Kind, string> = {
  terms: "ข้อตกลงการใช้งาน",
  privacy: "นโยบายความเป็นส่วนตัว",
  pdpa: "ประกาศ PDPA",
  cookie: "นโยบายคุกกี้",
};

function thaiDate(iso: string): string {
  return new Date(iso).toLocaleDateString("th-TH", { dateStyle: "long" });
}

function LegalContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const requested = searchParams.get("doc");
  const current: Kind = KINDS.includes(requested as Kind)
    ? (requested as Kind)
    : "terms";

  const document = useApiQuery(
    (signal) => api.get<LegalDocument>(`/legal/${current}/`, { signal }),
    [current],
  );

  function open(kind: Kind) {
    // The URL is the tab state; the params change re-renders us.
    router.replace(`/legal?doc=${kind}` as Route, { scroll: false });
  }

  return (
    <>
      <nav aria-label="เอกสารทางกฎหมาย" className="mb-6 flex flex-wrap gap-2">
        {KINDS.map((kind) => (
          <button
            key={kind}
            type="button"
            aria-current={kind === current ? "page" : undefined}
            onClick={() => open(kind)}
            className={cn(
              "rounded-full px-4 py-2 text-sm transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
              kind === current
                ? "bg-accent font-medium text-fg-inverted shadow-raised"
                : "bg-surface text-fg-muted shadow-raised hover:text-fg",
            )}
          >
            {KIND_LABELS[kind]}
          </button>
        ))}
      </nav>

      {document.loading ? (
        <Card aria-busy="true">
          <CardBody className="space-y-3">
            <Skeleton className="h-7 w-1/2" />
            <Skeleton className="h-40 w-full" />
          </CardBody>
        </Card>
      ) : document.error || !document.data ? (
        <ErrorState error={document.error} onRetry={document.refetch} />
      ) : (
        <Card>
          <CardBody className="space-y-4 sm:px-8 sm:py-7">
            <div>
              <h2 className="font-display text-xl font-medium text-fg">
                {document.data.title}
              </h2>
              <p className="mt-1 text-xs text-fg-subtle">
                ฉบับที่ {document.data.version} · แก้ไขล่าสุด{" "}
                {thaiDate(document.data.updated_at)}
              </p>
            </div>
            <RichText body={document.data.body} />
          </CardBody>
        </Card>
      )}
    </>
  );
}

export default function LegalPage() {
  return (
    <PageContainer className="max-w-3xl">
      <PageHeader
        title="ข้อตกลงและนโยบาย"
        description="เอกสารทั้งหมดที่กำกับการใช้งาน KawaiiBake - อ่านได้โดยไม่ต้องเข้าสู่ระบบ"
      />
      <Suspense>
        <LegalContent />
      </Suspense>
    </PageContainer>
  );
}
