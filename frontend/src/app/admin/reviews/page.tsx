"use client";

/**
 * Community moderation.
 *
 * Three surfaces, three real staff capabilities:
 *
 * - **Reviews** — `PATCH /reviews/{id}/ {status}` (`active|hidden`, staff
 *   only) and `DELETE /reviews/{id}/` (soft delete). Reviews have no flat
 *   listing in this API; they are always read through the content they
 *   are attached to, which is why this tab starts with a content picker.
 * - **Q&A threads** — `PATCH /qa/threads/{id}/ {status}` and DELETE.
 * - **Gallery posts** — `PATCH /gallery/{id}/ {status}` and DELETE, which
 *   staff may perform on anyone's post.
 *
 * No moderation queue, report inbox or audit log is shown: the backend
 * has none.
 */

import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type {
  CourseListItem,
  GalleryPost,
  QaThread,
  RecipeListItem,
  Review,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
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
  FilterSelect,
  Pagination,
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

/* ------------------------------------------------------------------ */
/* Reviews (reached through a piece of content)                        */
/* ------------------------------------------------------------------ */

function ReviewModeration() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [target, setTarget] = useState<"recipes" | "courses">("recipes");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const recipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { scope: "all", ordering: "title", page_size: 100 },
        signal,
      }),
    [],
  );
  const courses = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: { scope: "all", ordering: "title", page_size: 100 },
        signal,
      }),
    [],
  );

  const options =
    target === "recipes"
      ? (recipes.data?.results ?? []).map((item) => ({
          value: item.slug,
          label: item.title,
        }))
      : (courses.data?.results ?? []).map((item) => ({
          value: item.slug,
          label: item.title,
        }));

  const reviews = useApiQuery(
    (signal) =>
      slug
        ? api.get<Paginated<Review>>(`/${target}/${slug}/reviews/`, {
            query: { page_size: 50 },
            signal,
          })
        : Promise.resolve(null),
    [target, slug],
  );

  async function setStatus(review: Review, status: "active" | "hidden") {
    setBusy(review.id);
    try {
      await api.patch(`/reviews/${review.id}/`, { body: { status } });
      toast(status === "hidden" ? "ซ่อนรีวิวแล้ว" : "แสดงรีวิวอีกครั้งแล้ว", "success");
      reviews.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(null);
    }
  }

  async function remove(review: Review) {
    try {
      await api.delete(`/reviews/${review.id}/`);
      toast("ลบรีวิวแล้ว", "success");
      reviews.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  return (
    <>
      <AdminPanel>
        <DataTableToolbar>
          <FilterSelect
            label="ประเภทเนื้อหา"
            value={target}
            options={[
              { value: "recipes", label: "สูตรอาหาร" },
              { value: "courses", label: "คอร์สเรียน" },
            ]}
            onChange={(value) => {
              setTarget(value as "recipes" | "courses");
              setSlug("");
            }}
          />
          <FilterSelect
            label="เลือกรายการ"
            value={slug}
            options={[{ value: "", label: "— เลือก —" }, ...options]}
            onChange={setSlug}
          />
        </DataTableToolbar>

        {!slug ? (
          <AdminEmpty
            title="เลือกสูตรหรือคอร์สก่อน"
            description="API ไม่มีรายการรีวิวรวมทั้งแพลตฟอร์ม — รีวิวอ่านผ่านเนื้อหาที่ถูกรีวิวเสมอ"
          />
        ) : reviews.error ? (
          <div className="p-4">
            <ErrorState error={reviews.error} onRetry={reviews.refetch} />
          </div>
        ) : (
          <DataTable
            caption="รีวิวของเนื้อหาที่เลือก"
            loading={reviews.loading}
            rows={reviews.data?.results ?? []}
            rowKey={(row) => row.id}
            empty={<AdminEmpty title="ยังไม่มีรีวิวสำหรับรายการนี้" />}
            columns={[
              {
                key: "user",
                header: "ผู้เขียน",
                render: (row) => (
                  <span className="text-fg-muted">{row.user.username}</span>
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
                  <span className="line-clamp-2">{row.comment || "—"}</span>
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
        )}
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
                  {row.recipe?.title ?? row.course?.title ?? "—"}
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
/* Gallery posts                                                       */
/* ------------------------------------------------------------------ */

function GalleryModeration() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [author, setAuthor] = useState("");
  const authorFilter = useDebounced(author);
  const [busy, setBusy] = useState<number | null>(null);

  const list = usePagedList<GalleryPost>("/gallery/", {
    author: authorFilter || undefined,
  });

  async function setStatus(post: GalleryPost, status: "published" | "unpublished") {
    setBusy(post.id);
    try {
      await api.patch(`/gallery/${post.id}/`, { body: { status } });
      toast("อัปเดตสถานะโพสต์แล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(null);
    }
  }

  async function remove(post: GalleryPost) {
    try {
      await api.delete(`/gallery/${post.id}/`);
      toast("ลบโพสต์แล้ว", "success");
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
              <span className="font-mono tabular-nums">{list.count}</span> โพสต์
            </span>
          }
        >
          {/* The gallery list filters by author username, not free text. */}
          <SearchInput
            value={author}
            onChange={setAuthor}
            placeholder="กรองด้วย username ผู้โพสต์…"
            label="กรองตามผู้โพสต์"
          />
        </DataTableToolbar>

        <DataTable
          caption="โพสต์ในแกลเลอรี"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          empty={<AdminEmpty title="ไม่พบโพสต์" />}
          columns={[
            {
              key: "image",
              header: "",
              className: "w-px",
              render: (row) =>
                row.images[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
                  <img
                    src={row.images[0].url}
                    alt=""
                    className="size-10 rounded border border-edge object-cover"
                  />
                ) : (
                  <span className="text-xs text-fg-subtle">—</span>
                ),
            },
            {
              key: "caption",
              header: "คำบรรยาย",
              render: (row) => (
                <span className="line-clamp-2">{row.caption || "—"}</span>
              ),
            },
            {
              key: "author",
              header: "ผู้โพสต์",
              render: (row) => (
                <span className="text-fg-muted">{row.author_handle}</span>
              ),
            },
            {
              key: "target",
              header: "เกี่ยวกับ",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.recipe?.title ?? row.course?.title ?? "—"}
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
                      setStatus(
                        row,
                        row.status === "published" ? "unpublished" : "published",
                      )
                    }
                  >
                    {row.status === "published" ? "ซ่อน" : "แสดง"}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() =>
                      confirm.ask({
                        title: "ลบโพสต์นี้?",
                        body: "โพสต์และรูปภาพทั้งหมดจะถูกลบออกจากแกลเลอรี",
                        confirmLabel: "ลบโพสต์",
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
        description="รีวิว กระทู้ถาม-ตอบ และแกลเลอรี — ทุกคำสั่งใช้สิทธิ์ staff ที่ระบบหลังบ้านตรวจสอบเองอีกชั้น"
      />
      <Tabs
        items={[
          { key: "reviews", label: "รีวิว", content: <ReviewModeration /> },
          { key: "qa", label: "ถาม-ตอบ", content: <ThreadModeration /> },
          { key: "gallery", label: "แกลเลอรี", content: <GalleryModeration /> },
        ]}
      />
    </>
  );
}
