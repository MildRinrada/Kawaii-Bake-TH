"use client";

/**
 * Quiz management  the same lifecycle the recipes and courses pages
 * use, against `/quizzes/` (`scope=all` for the staff slice).
 *
 * Attempt statistics are not shown: `/quizzes/{slug}/attempts/` returns
 * the caller's own attempts, not the cohort's.
 */

import { useState } from "react";

import type { QuizListItem } from "@/lib/api/models";
import { usePagedList } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  FilterBar,
  FilterSelect,
  Pagination,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import {
  describeAdminError,
  runTransition,
  type Transition,
} from "@/components/admin/lifecycle";

const SCOPES = [
  { value: "all", label: "ทั้งหมด (staff)" },
  { value: "public", label: "เฉพาะที่เผยแพร่" },
];

const ORDERINGS = [
  { value: "newest", label: "ใหม่ล่าสุด" },
  { value: "oldest", label: "เก่าสุด" },
  { value: "title", label: "ชื่อ ก–ฮ" },
];

export default function AdminQuizzesPage() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [scope, setScope] = useState("all");
  const [ordering, setOrdering] = useState("newest");
  const [busy, setBusy] = useState<string | null>(null);

  const list = usePagedList<QuizListItem>("/quizzes/", { scope, ordering });

  async function transition(slug: string, action: Transition) {
    setBusy(slug);
    try {
      await runTransition("/quizzes", slug, action);
      toast("อัปเดตสถานะแบบทดสอบแล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(null);
    }
  }

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="แบบทดสอบ"
        description="จัดการแบบทดสอบทุกสถานะ พร้อมจำนวนคำถามและเกณฑ์ผ่าน"
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> ชุด
            </span>
          }
        >
          <FilterBar>
            <FilterSelect
              label="ขอบเขต"
              value={scope}
              options={SCOPES}
              onChange={setScope}
            />
            <FilterSelect
              label="เรียงตาม"
              value={ordering}
              options={ORDERINGS}
              onChange={setOrdering}
            />
          </FilterBar>
        </DataTableToolbar>

        <DataTable
          caption="รายการแบบทดสอบ"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.slug}
          empty={<AdminEmpty title="ยังไม่มีแบบทดสอบในระบบ" />}
          columns={[
            {
              key: "title",
              header: "ชื่อชุด",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title}</p>
                  <p className="font-mono text-xs text-fg-subtle">{row.slug}</p>
                </div>
              ),
            },
            {
              key: "owner",
              header: "เจ้าของ",
              render: (row) => (
                <span className="text-fg-muted">{row.owner.username}</span>
              ),
            },
            {
              key: "questions",
              header: "คำถาม",
              numeric: true,
              render: (row) => row.question_count,
            },
            {
              key: "pass",
              header: "เกณฑ์ผ่าน",
              numeric: true,
              render: (row) => `${row.pass_percent}%`,
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => <StatusBadge status={row.status} />,
            },
            {
              key: "visibility",
              header: "การมองเห็น",
              render: (row) => <StatusBadge status={row.visibility} />,
            },
            {
              key: "created",
              header: "สร้างเมื่อ",
              render: (row) => (
                <span className="whitespace-nowrap text-xs text-fg-muted">
                  {relativeThai(row.created_at)}
                </span>
              ),
            },
            {
              key: "actions",
              header: "จัดการ",
              className: "w-px",
              render: (row) => (
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busy === row.slug}
                    onClick={() =>
                      transition(
                        row.slug,
                        row.status === "published" ? "unpublish" : "publish",
                      )
                    }
                  >
                    {row.status === "published" ? "ถอนออก" : "เผยแพร่"}
                  </Button>
                  {row.status !== "archived" ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        confirm.ask({
                          title: "เก็บแบบทดสอบเข้าคลัง?",
                          body: `“${row.title}” จะไม่แสดงให้ผู้เรียนอีก แต่ผลการทำที่บันทึกไว้ยังอยู่ครบ`,
                          confirmLabel: "เก็บเข้าคลัง",
                          action: () => transition(row.slug, "archive"),
                        })
                      }
                    >
                      เก็บเข้าคลัง
                    </Button>
                  ) : null}
                </div>
              ),
            },
          ]}
        />

        <Pagination
          page={list.page}
          pageSize={list.pageSize}
          count={list.count}
          onPage={list.setPage}
        />
      </AdminPanel>

      <p className="mt-2 text-xs text-fg-muted">
        ไม่มีสถิติการทำแบบทดสอบรวม เพราะ{" "}
        <code className="font-mono">GET /quizzes/&#123;slug&#125;/attempts/</code>{" "}
        คืนเฉพาะผลของผู้เรียกเอง
      </p>

      {confirm.dialog}
    </>
  );
}
