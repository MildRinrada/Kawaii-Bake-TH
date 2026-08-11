"use client";

/**
 * Community moderation.
 *
 * Two surfaces, two real staff capabilities:
 *
 * - **Reviews**  `GET /admin/reviews/` (staff-only) lists every review
 *   across recipes and courses in one flat, filterable table, and
 *   `PATCH /reviews/{id}/ {status}` (`active|hidden`) plus
 *   `DELETE /reviews/{id}/` (soft delete) moderate them. There is
 *   deliberately no way to edit review text: staff moderate visibility,
 *   never content.
 * - **Q&A threads**  `PATCH /qa/threads/{id}/ {status}` and DELETE.
 *
 * Gallery posts moved to their own page (`/admin/posts`), which also
 * hosts the staff composer. No moderation queue, report inbox or audit
 * log is shown: the backend has none.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type { AdminReview, QaThread } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Rating } from "@/components/ui/rating";
import { Tabs } from "@/components/ui/tabs";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  FilterBar,
  FilterSelect,
  Pagination,
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

/* ------------------------------------------------------------------ */
/* Reviews (flat cross-content list)                                   */
/* ------------------------------------------------------------------ */

const RATINGS = [
  { value: "", label: "ทั้งหมด" },
  { value: "5", label: "5 ดาว" },
  { value: "4", label: "4 ดาว" },
  { value: "3", label: "3 ดาว" },
  { value: "2", label: "2 ดาว" },
  { value: "1", label: "1 ดาว" },
];

// Without a `status` param the backend returns active + hidden and never
// deleted rows; "ถูกลบ" opts into the soft-deleted slice explicitly.
const STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "active", label: "แสดงอยู่" },
  { value: "hidden", label: "ซ่อนอยู่" },
  { value: "deleted", label: "ถูกลบ" },
];

const TARGETS = [
  { value: "", label: "ทั้งหมด" },
  { value: "recipe", label: "สูตร" },
  { value: "course", label: "คอร์ส" },
];

/** Public URL of the reviewed content, or null when the slug is missing. */
function reviewedUrl(review: AdminReview): string | null {
  if (review.target === "recipe" && review.recipe_slug) {
    return `/recipes/${encodeURIComponent(review.recipe_slug)}`;
  }
  if (review.target === "course" && review.course_slug) {
    return `/courses/${encodeURIComponent(review.course_slug)}`;
  }
  return null;
}

function ReviewModeration() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [rating, setRating] = useState("");
  const [status, setStatus] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  // Empty filters are omitted entirely: the endpoint rejects unknown or
  // blank query keys with a 400 instead of guessing.
  const list = usePagedList<AdminReview>("/admin/reviews/", {
    search: search || undefined,
    rating: rating || undefined,
    status: status || undefined,
    target: target || undefined,
  });

  async function setReviewStatus(review: AdminReview, next: "active" | "hidden") {
    setBusy(review.id);
    try {
      await api.patch(`/reviews/${review.id}/`, { body: { status: next } });
      toast(next === "hidden" ? "ซ่อนรีวิวแล้ว" : "แสดงรีวิวอีกครั้งแล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(null);
    }
  }

  async function remove(review: AdminReview) {
    try {
      await api.delete(`/reviews/${review.id}/`);
      toast("ลบรีวิวแล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
    <>
      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> รีวิว
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาความเห็นหรือ username ผู้เขียน…"
            label="ค้นหารีวิว"
          />
          <FilterBar>
            <FilterSelect
              label="คะแนน"
              value={rating}
              options={RATINGS}
              onChange={setRating}
            />
            <FilterSelect
              label="สถานะ"
              value={status}
              options={STATUSES}
              onChange={setStatus}
            />
            <FilterSelect
              label="ประเภท"
              value={target}
              options={TARGETS}
              onChange={setTarget}
            />
          </FilterBar>
        </DataTableToolbar>

        <DataTable
          caption="รีวิวทั้งหมดในระบบ"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          empty={
            <AdminEmpty
              title="ไม่พบรีวิวที่ตรงกับเงื่อนไข"
              description="ลองล้างคำค้นหรือเปลี่ยนตัวกรอง"
            />
          }
          columns={[
            {
              key: "user",
              header: "ผู้เขียน",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">
                    {row.user.display_name || row.user.username}
                  </p>
                  <p className="line-clamp-1 text-xs text-fg-subtle">
                    @{row.user.username}
                  </p>
                </div>
              ),
            },
            {
              key: "rating",
              header: "คะแนน",
              render: (row) => <Rating average={row.rating} />,
            },
            {
              key: "comment",
              header: "ความเห็น",
              render: (row) => (
                <span className="line-clamp-2">{row.comment || ""}</span>
              ),
            },
            {
              key: "reviewed",
              header: "รีวิวของ",
              render: (row) => {
                const title =
                  row.target === "recipe" ? row.recipe_title : row.course_title;
                const url = reviewedUrl(row);
                return (
                  <div className="flex min-w-0 items-center gap-1.5">
                    <Badge tone={row.target === "recipe" ? "peach" : "lavender"}>
                      {row.target === "recipe" ? "สูตร" : "คอร์ส"}
                    </Badge>
                    {url ? (
                      <Link
                        href={url}
                        target="_blank"
                        className="line-clamp-1 text-sm text-fg underline-offset-2 hover:underline"
                      >
                        {title ?? url}
                      </Link>
                    ) : (
                      <span className="line-clamp-1 text-sm text-fg-muted">
                        {title ?? ""}
                      </span>
                    )}
                  </div>
                );
              },
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => <StatusBadge status={row.status} />,
            },
            {
              key: "created",
              header: "เมื่อ",
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
              // Staff moderate visibility, never content: there is no edit
              // button by design. A soft-deleted review is a tombstone
              // it stays readable for the record but offers no actions.
              render: (row) =>
                row.status === "deleted" ? (
                  <span className="text-xs text-fg-subtle">ลบแล้ว</span>
                ) : (
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy === row.id}
                      onClick={() =>
                        setReviewStatus(
                          row,
                          row.status === "hidden" ? "active" : "hidden",
                        )
                      }
                    >
                      {row.status === "hidden" ? "แสดงอีกครั้ง" : "ซ่อน"}
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() =>
                        confirm.ask({
                          title: "ลบรีวิวนี้?",
                          body: "รีวิวจะถูกลบแบบ soft delete และผู้เขียนสามารถรีวิวใหม่ได้อีกครั้ง",
                          confirmLabel: "ลบรีวิว",
                          danger: true,
                          action: () => remove(row),
                        })
                      }
                    >
                      ลบ
                    </Button>
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
      {confirm.dialog}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Q&A threads                                                         */
/* ------------------------------------------------------------------ */

function ThreadModeration() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [busy, setBusy] = useState<number | null>(null);

  const list = usePagedList<QaThread>("/qa/threads/", {
    search: search || undefined,
  });

  async function setStatus(thread: QaThread, status: "active" | "hidden") {
    setBusy(thread.id);
    try {
      await api.patch(`/qa/threads/${thread.id}/`, { body: { status } });
      toast(status === "hidden" ? "ซ่อนกระทู้แล้ว" : "แสดงกระทู้อีกครั้งแล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(null);
    }
  }

  async function remove(thread: QaThread) {
    try {
      await api.delete(`/qa/threads/${thread.id}/`);
      toast("ลบกระทู้แล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
    <>
      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> กระทู้
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหากระทู้…"
            label="ค้นหากระทู้"
          />
        </DataTableToolbar>

        <DataTable
          caption="กระทู้ถาม-ตอบ"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          empty={<AdminEmpty title="ไม่พบกระทู้" />}
          columns={[
            {
              key: "title",
              header: "หัวข้อ",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title}</p>
                  <p className="line-clamp-1 text-xs text-fg-muted">{row.body}</p>
                </div>
              ),
            },
            {
              key: "author",
              header: "ผู้ถาม",
              render: (row) => (
                <span className="text-fg-muted">{row.author_handle}</span>
              ),
            },
            {
              key: "target",
              header: "เกี่ยวกับ",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.recipe?.title ?? row.course?.title ?? ""}
                </span>
              ),
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => <StatusBadge status={row.status} />,
            },
            {
              key: "created",
              header: "เมื่อ",
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
                    disabled={busy === row.id}
                    onClick={() =>
                      setStatus(row, row.status === "hidden" ? "active" : "hidden")
                    }
                  >
                    {row.status === "hidden" ? "แสดงอีกครั้ง" : "ซ่อน"}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() =>
                      confirm.ask({
                        title: "ลบกระทู้นี้?",
                        body: `“${row.title}” และคำตอบทั้งหมดจะหายไปจากหน้าเว็บ`,
                        confirmLabel: "ลบกระทู้",
                        danger: true,
                        action: () => remove(row),
                      })
                    }
                  >
                    ลบ
                  </Button>
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
      {confirm.dialog}
    </>
  );
}

/* ------------------------------------------------------------------ */

export default function AdminModerationPage() {
  return (
    <>
      <AdminPageHeader
        title="การกลั่นกรองชุมชน"
        description="รีวิวทุกสูตรและคอร์สในตารางเดียว พร้อมกระทู้ถาม-ตอบ  ทุกคำสั่งใช้สิทธิ์ staff ที่ระบบหลังบ้านตรวจสอบเองอีกชั้น"
      />
      <Tabs
        items={[
          { key: "reviews", label: "รีวิว", content: <ReviewModeration /> },
          { key: "qa", label: "ถาม-ตอบ", content: <ThreadModeration /> },
        ]}
      />
    </>
  );
}
