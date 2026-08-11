"use client";

/**
 * Community post management.
 *
 * Reads `GET /gallery/`  for a staff caller this includes unpublished
 * (hidden) posts, and the `status` filter narrows to one slice. Writes
 * are `PATCH /gallery/{id}/ {status}` to hide/show and
 * `DELETE /gallery/{id}/`, which is a HARD delete: the post and every
 * uploaded image are gone for good, and the confirm dialog says so.
 *
 * Design rule, on purpose: admins can only DELETE or HIDE user posts,
 * never edit them  users edit their own posts from the post detail
 * page, so there is no edit affordance for other people's posts here.
 * The only authoring surface is the composer below, which posts under
 * the admin's *own* account via the exact component the community feed
 * uses (`POST /gallery/` + `POST /gallery/{id}/images/`).
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type { GalleryPost } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
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
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";
import { PostComposerForm } from "@/components/community/post-composer-form";

// `status` maps straight onto the gallery model's two states; the empty
// value omits the param so staff see published and unpublished together.
const STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "published", label: "แสดงอยู่" },
  { value: "unpublished", label: "ซ่อนอยู่" },
];

export default function AdminPostsPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [composerOpen, setComposerOpen] = useState(false);
  const [authorInput, setAuthorInput] = useState("");
  const author = useDebounced(authorInput);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const list = usePagedList<GalleryPost>("/gallery/", {
    author: author || undefined,
    status: status || undefined,
  });

  async function setPostStatus(
    post: GalleryPost,
    next: "published" | "unpublished",
  ) {
    setBusy(post.id);
    try {
      await api.patch(`/gallery/${post.id}/`, { body: { status: next } });
      toast(next === "unpublished" ? "ซ่อนโพสต์แล้ว" : "แสดงโพสต์อีกครั้งแล้ว", "success");
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
      toast("ลบโพสต์ถาวรแล้ว", "success");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="โพสต์ชุมชน"
        description="ดู ซ่อน หรือลบโพสต์ของทุกคนในแกลเลอรี  แก้ไขเนื้อหาโพสต์ได้เฉพาะเจ้าของเท่านั้น"
        actions={
          <Button
            size="sm"
            variant={composerOpen ? "secondary" : "primary"}
            onClick={() => setComposerOpen((open) => !open)}
          >
            {composerOpen ? "ปิดฟอร์มสร้างโพสต์" : "+ สร้างโพสต์"}
          </Button>
        }
      />

      {composerOpen ? (
        <AdminPanel
          title="สร้างโพสต์ใหม่"
          description="โพสต์จะเผยแพร่ในนามบัญชีของคุณเอง  ใช้เมื่อทีมงานต้องการโพสต์ในนามตัวเอง"
          className="mb-4"
        >
          <div className="px-4 py-4">
            <PostComposerForm
              autoFocus
              onCancel={() => setComposerOpen(false)}
              onPublished={() => {
                // The composer already toasts its own success message;
                // here we only fold the panel and show the fresh post.
                setComposerOpen(false);
                list.refetch();
              }}
            />
          </div>
        </AdminPanel>
      ) : null}

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> โพสต์
            </span>
          }
        >
          {/* The gallery list filters by the author's username, not free text. */}
          <SearchInput
            value={authorInput}
            onChange={setAuthorInput}
            placeholder="กรองตามชื่อผู้ใช้ผู้โพสต์…"
            label="กรองตามผู้โพสต์"
          />
          <FilterBar>
            <FilterSelect
              label="สถานะ"
              value={status}
              options={STATUSES}
              onChange={setStatus}
            />
          </FilterBar>
        </DataTableToolbar>

        <DataTable
          caption="โพสต์ชุมชนทั้งหมด"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          empty={
            <AdminEmpty
              title="ไม่พบโพสต์ที่ตรงกับเงื่อนไข"
              description="ลองล้างตัวกรองหรือเปลี่ยนสถานะ"
            />
          }
          columns={[
            {
              key: "image",
              header: "ภาพ",
              className: "w-14",
              // A post cannot exist without at least one image, so the
              // first one is always there to thumbnail.
              render: (row) => (
                // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
                <img
                  src={row.images[0]?.url}
                  alt=""
                  className="h-10 w-14 rounded object-cover"
                />
              ),
            },
            {
              key: "caption",
              header: "คำบรรยาย",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-2">{row.caption || ""}</p>
                  <Link
                    href={`/community/posts/${row.id}`}
                    target="_blank"
                    className="text-xs text-fg-muted underline-offset-2 hover:underline"
                  >
                    เปิดโพสต์
                  </Link>
                </div>
              ),
            },
            {
              key: "author",
              header: "ผู้โพสต์",
              render: (row) => (
                <div className="flex min-w-0 items-center gap-2">
                  <Avatar
                    src={row.author_avatar_url}
                    name={row.author_display_name}
                    size="sm"
                  />
                  <div className="min-w-0">
                    <p className="line-clamp-1 font-medium">
                      {row.author_display_name}
                    </p>
                    <p className="line-clamp-1 text-xs text-fg-subtle">
                      @{row.author_handle}
                    </p>
                  </div>
                </div>
              ),
            },
            {
              key: "target",
              header: "เกี่ยวกับ",
              render: (row) =>
                row.recipe || row.course ? (
                  <Badge tone={row.recipe ? "peach" : "lavender"}>
                    {row.recipe?.title ?? row.course?.title}
                  </Badge>
                ) : (
                  <span className="text-xs text-fg-subtle">-</span>
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
                      setPostStatus(
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
                        title: "ลบโพสต์นี้ถาวร?",
                        body: "โพสต์และรูปภาพทุกรูปจะถูกลบออกจากระบบอย่างถาวร กู้คืนไม่ได้  ถ้าต้องการแค่เอาออกจากหน้าเว็บ ให้ใช้ “ซ่อน” แทน",
                        confirmLabel: "ลบถาวร",
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
