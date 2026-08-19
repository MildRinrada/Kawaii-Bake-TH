"use client";

/**
 * The certificate template workspace - pick a course, open its design.
 *
 * This page is about **templates**, not issued paper: every course has
 * a certificate design (its own, or the built-in default), and the
 * designer at `/admin/certificates/{slug}/designer` edits it visually.
 * The registry of already-issued certificates lives one step away at
 * `/admin/certificates/issued`.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type {
  CertificateTemplateRow,
  CourseListItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  Pagination,
  SearchInput,
} from "@/components/admin/primitives";

function TemplateStatus({ row }: { row: CertificateTemplateRow | undefined }) {
  if (!row) return <Badge tone="neutral">ดีไซน์มาตรฐาน</Badge>;
  if (row.status === "published") return <Badge tone="success">เผยแพร่แล้ว</Badge>;
  return <Badge tone="warning">แบบร่าง</Badge>;
}

export default function AdminCertificateTemplatesPage() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);

  const courses = usePagedList<CourseListItem>("/courses/", {
    scope: "all",
    ordering: "title",
    search: search || undefined,
  });
  const templates = useApiQuery(
    (signal) =>
      api.get<CertificateTemplateRow[]>("/admin/certificates/templates/", {
        signal,
      }),
    [],
  );
  const bySlug = new Map(
    (templates.data ?? []).map((row) => [row.course_slug, row]),
  );

  if (courses.error) {
    return <ErrorState error={courses.error} onRetry={courses.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="ใบประกาศ"
        description="ออกแบบเทมเพลตใบประกาศของแต่ละคอร์สด้วยเครื่องมือแก้ไขภาพ - ลากวาง ปรับขนาด และเผยแพร่เมื่อพร้อม"
        actions={
          <Link href="/admin/certificates/issued">
            <Button size="sm" variant="secondary">
              ทะเบียนใบประกาศที่ออกแล้ว →
            </Button>
          </Link>
        }
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              คอร์สที่ยังไม่ปรับแต่งจะใช้ดีไซน์มาตรฐานของ KawaiiBake โดยอัตโนมัติ
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาชื่อคอร์ส…"
            label="ค้นหาคอร์ส"
          />
        </DataTableToolbar>

        <DataTable
          caption="เทมเพลตใบประกาศรายคอร์ส"
          loading={courses.loading || templates.loading}
          rows={courses.rows}
          rowKey={(row) => row.slug}
          empty={
            <AdminEmpty
              title="ไม่พบคอร์ส"
              description="ลองเปลี่ยนคำค้นหา หรือสร้างคอร์สก่อนแล้วค่อยออกแบบใบประกาศ"
            />
          }
          columns={[
            {
              key: "course",
              header: "คอร์ส",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title}</p>
                  <p className="font-mono text-xs text-fg-subtle">{row.slug}</p>
                </div>
              ),
            },
            {
              key: "template",
              header: "สถานะเทมเพลต",
              render: (row) => <TemplateStatus row={bySlug.get(row.slug)} />,
            },
            {
              key: "updated",
              header: "แก้ไขล่าสุด",
              render: (row) => {
                const template = bySlug.get(row.slug);
                return (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {template ? relativeThai(template.updated_at) : "-"}
                    {template?.updated_by ? (
                      <span className="text-fg-subtle">
                        {" "}
                        · @{template.updated_by}
                      </span>
                    ) : null}
                  </span>
                );
              },
            },
            {
              key: "published",
              header: "เผยแพร่ล่าสุด",
              render: (row) => {
                const template = bySlug.get(row.slug);
                return (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {template?.published_at
                      ? relativeThai(template.published_at)
                      : "-"}
                  </span>
                );
              },
            },
            {
              key: "actions",
              header: "การจัดการ",
              className: "w-px",
              render: (row) => (
                <Link
                  href={`/admin/certificates/${encodeURIComponent(row.slug)}/designer`}
                  className="whitespace-nowrap rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                >
                  แก้ไขเทมเพลต
                </Link>
              ),
            },
          ]}
        />

        <Pagination
          page={courses.page}
          pageSize={courses.pageSize}
          count={courses.count}
          onPage={courses.setPage}
        />
      </AdminPanel>
    </>
  );
}
