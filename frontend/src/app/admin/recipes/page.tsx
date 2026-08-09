"use client";

/**
 * Recipe management.
 *
 * Reads `GET /recipes/?scope=all` — the staff-only slice that includes
 * drafts, unlisted and archived rows (a non-staff caller is silently
 * narrowed to the public set by the backend, which is why this page is
 * safe even if the client-side gate is bypassed).
 *
 * Writes are the endpoints that already exist: publish / unpublish /
 * archive and DELETE. There is no server-side `status` filter, so this
 * page offers the scope switch the API really has instead of a status
 * dropdown that would only filter the current page.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type { Category, RecipeDetail, RecipeListItem } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
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
  DetailPanel,
  DetailRow,
  FilterBar,
  FilterSelect,
  Pagination,
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import {
  describeAdminError,
  runTransition,
  type Transition,
} from "@/components/admin/lifecycle";

const DIFFICULTIES = [
  { value: "", label: "ทุกระดับ" },
  { value: "easy", label: "ง่าย" },
  { value: "medium", label: "ปานกลาง" },
  { value: "hard", label: "ยาก" },
  { value: "expert", label: "ระดับเชี่ยวชาญ" },
];

const SCOPES = [
  { value: "all", label: "ทั้งหมด (staff)" },
  { value: "public", label: "เฉพาะที่เผยแพร่" },
];

const ORDERINGS = [
  { value: "newest", label: "ใหม่ล่าสุด" },
  { value: "oldest", label: "เก่าสุด" },
  { value: "title", label: "ชื่อ ก–ฮ" },
  { value: "popular", label: "ยอดนิยม" },
];

export default function AdminRecipesPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [difficulty, setDifficulty] = useState("");
  const [category, setCategory] = useState("");
  const [scope, setScope] = useState("all");
  const [ordering, setOrdering] = useState("newest");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const list = usePagedList<RecipeListItem>("/recipes/", {
    scope,
    ordering,
    search: search || undefined,
    difficulty: difficulty || undefined,
    category: category || undefined,
  });

  const detail = useApiQuery(
    (signal) =>
      selected
        ? api.get<RecipeDetail>(`/recipes/${selected}/`, { signal })
        : Promise.resolve(null),
    [selected],
  );

  async function transition(slug: string, action: Transition) {
    setBusy(true);
    try {
      await runTransition("/recipes", slug, action);
      toast("อัปเดตสถานะเรียบร้อย", "success");
      list.refetch();
      if (selected === slug) detail.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  async function destroy(slug: string, title: string) {
    try {
      await api.delete(`/recipes/${slug}/`);
      toast(`ลบสูตร “${title}” แล้ว`, "success");
      setSelected(null);
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
        title="สูตรอาหาร"
        description="จัดการสูตรทุกสถานะ — ฉบับร่าง เผยแพร่ ไม่แสดงในรายการ และที่เก็บเข้าคลัง"
        actions={
          <Link href="/admin/recipes/new">
            <Button size="sm">+ เพิ่มสูตรใหม่</Button>
          </Link>
        }
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> รายการ
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาชื่อสูตร…"
            label="ค้นหาสูตร"
          />
          <FilterBar>
            <FilterSelect
              label="ขอบเขต"
              value={scope}
              options={SCOPES}
              onChange={setScope}
            />
            <FilterSelect
              label="ระดับ"
              value={difficulty}
              options={DIFFICULTIES}
              onChange={setDifficulty}
            />
            <FilterSelect
              label="หมวด"
              value={category}
              options={[
                { value: "", label: "ทุกหมวด" },
                ...(categories.data ?? []).map((item) => ({
                  value: item.slug,
                  label: item.name,
                })),
              ]}
              onChange={setCategory}
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
          caption="รายการสูตรอาหารทั้งหมด"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.slug}
          onRowClick={(row) => setSelected(row.slug)}
          empty={
            <AdminEmpty
              title="ไม่พบสูตรที่ตรงกับเงื่อนไข"
              description="ลองล้างคำค้นหรือเปลี่ยนตัวกรอง"
            />
          }
          columns={[
            {
              key: "title",
              header: "ชื่อสูตร",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title}</p>
                  <p className="font-mono text-xs text-fg-subtle">{row.slug}</p>
                </div>
              ),
            },
            {
              key: "author",
              header: "ผู้เขียน",
              render: (row) => (
                <span className="text-fg-muted">{row.author.username}</span>
              ),
            },
            {
              key: "categories",
              header: "หมวด",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.categories.map((item) => item.name).join(", ") || "—"}
                </span>
              ),
            },
            {
              key: "difficulty",
              header: "ระดับ",
              render: (row) => (
                <span className="text-xs text-fg-muted">{row.difficulty}</span>
              ),
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
                <Link
                  href={`/admin/recipes/${encodeURIComponent(row.slug)}/edit`}
                  // The row itself opens the detail drawer; this must not.
                  onClick={(event) => event.stopPropagation()}
                  className="rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                >
                  แก้ไข
                </Link>
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

      <DetailPanel
        open={selected !== null}
        title={detail.data?.title ?? "รายละเอียดสูตร"}
        onClose={() => setSelected(null)}
        footer={
          detail.data ? (
            <>
              <Link
                href={`/admin/recipes/${encodeURIComponent(detail.data.slug)}/edit`}
                className="mr-auto"
              >
                <Button size="sm" variant="secondary">
                  ✎ แก้ไขสูตร
                </Button>
              </Link>
              {detail.data.status !== "published" ? (
                <Button
                  size="sm"
                  loading={busy}
                  onClick={() => transition(detail.data!.slug, "publish")}
                >
                  เผยแพร่
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy}
                  onClick={() => transition(detail.data!.slug, "unpublish")}
                >
                  ถอนกลับเป็นฉบับร่าง
                </Button>
              )}
              {detail.data.status !== "archived" ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    confirm.ask({
                      title: "เก็บสูตรเข้าคลัง?",
                      body: `“${detail.data!.title}” จะหายจากหน้าเว็บสาธารณะ แต่ข้อมูลยังอยู่ครบและย้อนกลับได้`,
                      confirmLabel: "เก็บเข้าคลัง",
                      action: () => transition(detail.data!.slug, "archive"),
                    })
                  }
                >
                  เก็บเข้าคลัง
                </Button>
              ) : null}
              <Button
                size="sm"
                variant="danger"
                onClick={() =>
                  confirm.ask({
                    title: "ลบสูตรนี้ถาวร?",
                    body: `“${detail.data!.title}” จะถูกลบออกจากฐานข้อมูลอย่างถาวร กู้คืนไม่ได้ — ถ้าต้องการแค่ซ่อน ให้ใช้ “เก็บเข้าคลัง” แทน`,
                    confirmLabel: "ลบถาวร",
                    danger: true,
                    action: () =>
                      destroy(detail.data!.slug, detail.data!.title),
                  })
                }
              >
                ลบถาวร
              </Button>
            </>
          ) : null
        }
      >
        {detail.loading ? (
          <p className="text-fg-muted">กำลังโหลด…</p>
        ) : detail.error ? (
          <ErrorState error={detail.error} onRetry={detail.refetch} />
        ) : detail.data ? (
          <dl>
            <DetailRow label="slug">
              <span className="font-mono text-xs">{detail.data.slug}</span>
            </DetailRow>
            <DetailRow label="ผู้เขียน">
              {detail.data.author.display_name || detail.data.author.username}
            </DetailRow>
            <DetailRow label="สถานะ">
              <StatusBadge status={detail.data.status} />
            </DetailRow>
            <DetailRow label="การมองเห็น">
              <StatusBadge status={detail.data.visibility} />
            </DetailRow>
            <DetailRow label="ระดับ">{detail.data.difficulty}</DetailRow>
            <DetailRow label="เวลารวม">
              {detail.data.total_minutes} นาที
            </DetailRow>
            <DetailRow label="หมวดหมู่">
              {detail.data.categories.map((item) => item.name).join(", ") || "—"}
            </DetailRow>
            <DetailRow label="วัตถุดิบ">
              {detail.data.ingredients.length} รายการ
            </DetailRow>
            <DetailRow label="ขั้นตอน">{detail.data.steps.length} ขั้น</DetailRow>
            <DetailRow label="สร้างเมื่อ">
              {relativeThai(detail.data.created_at)}
            </DetailRow>
            <DetailRow label="สรุป">
              <span className="text-fg-muted">{detail.data.summary || "—"}</span>
            </DetailRow>
          </dl>
        ) : null}
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}
