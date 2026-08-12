"use client";

/**
 * Recipe management — the staff workspace over every recipe in the system.
 *
 * Reads `GET /recipes/?scope=all` — the staff-only slice that includes
 * drafts, unlisted and archived rows (a non-staff caller is silently
 * narrowed to the public set by the backend, which is why this page is
 * safe even if the client-side gate is bypassed).
 *
 * Writes are the endpoints that already exist: publish / unpublish /
 * archive and DELETE. Every filter here (`status`, `visibility`,
 * `author`, …) is server-side and narrow-only — the backend intersects
 * them with the visibility rule, so they can never widen what a viewer
 * sees. The summary cards are the same counts (`page_size=1`), never
 * client-side arithmetic over one page.
 *
 * Bulk actions orchestrate the existing per-recipe endpoints in
 * sequence — there is no bulk API, and this page does not pretend
 * otherwise: each selected row gets its own real request and failures
 * are reported per batch.
 */

import Link from "next/link";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type { Category, RecipeDetail, RecipeListItem } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { cn } from "@/lib/cn";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
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
  { value: "expert", label: "เชี่ยวชาญ" },
];

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "ง่าย",
  medium: "ปานกลาง",
  hard: "ยาก",
  expert: "เชี่ยวชาญ",
};

const SCOPES = [
  { value: "all", label: "ทั้งหมด (staff)" },
  { value: "public", label: "เฉพาะที่เผยแพร่" },
  { value: "mine", label: "สูตรของฉัน" },
];

const STATUSES = [
  { value: "", label: "ทุกสถานะ" },
  { value: "draft", label: "ฉบับร่าง" },
  { value: "published", label: "เผยแพร่" },
  { value: "archived", label: "เก็บเข้าคลัง" },
];

const VISIBILITIES = [
  { value: "", label: "ทุกการมองเห็น" },
  { value: "public", label: "สาธารณะ" },
  { value: "unlisted", label: "ไม่แสดงในรายการ" },
  { value: "private", label: "ส่วนตัว" },
];

const ORDERINGS = [
  { value: "newest", label: "ใหม่ล่าสุด" },
  { value: "oldest", label: "เก่าสุด" },
  { value: "title", label: "ชื่อ ก–ฮ" },
  { value: "popular", label: "ยอดนิยม" },
];

/** A real server count: `count` off a one-row page of the same endpoint. */
function useRecipeCount(query: Record<string, string>) {
  return useApiQuery<Paginated<RecipeListItem>>(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { ...query, scope: "all", page_size: 1 },
        signal,
      }),
    [JSON.stringify(query)],
  );
}

/** Compact metric card; clicking applies the matching list filter. */
function MiniStat({
  label,
  count,
  loading,
  active,
  onClick,
}: {
  label: string;
  count: number | undefined;
  loading: boolean;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-lg border px-3 py-2 text-left transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
        active
          ? "border-accent bg-accent-subtle"
          : "border-edge bg-surface hover:border-edge-strong",
      )}
    >
      <span className="block text-[11px] text-fg-subtle">{label}</span>
      <span className="mt-0.5 block font-mono text-lg tabular-nums leading-tight text-fg">
        {loading ? "…" : (count ?? "-")}
      </span>
    </button>
  );
}

/** Cover thumbnail with the brand-soft placeholder for coverless rows. */
function CoverThumb({
  url,
  className,
}: {
  url: string | null | undefined;
  className?: string;
}) {
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
    <img
      src={url}
      alt=""
      className={cn("rounded-md object-cover", className)}
    />
  ) : (
    <span
      aria-hidden
      className={cn("block rounded-md bg-berry-soft/60", className)}
    />
  );
}

export default function AdminRecipesPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [authorInput, setAuthorInput] = useState("");
  const author = useDebounced(authorInput);
  const [difficulty, setDifficulty] = useState("");
  const [category, setCategory] = useState("");
  const [scope, setScope] = useState("all");
  const [status, setStatus] = useState("");
  const [visibility, setVisibility] = useState("");
  const [ordering, setOrdering] = useState("newest");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const list = usePagedList<RecipeListItem>("/recipes/", {
    scope,
    ordering,
    search: search || undefined,
    status: status || undefined,
    visibility: visibility || undefined,
    author: author || undefined,
    difficulty: difficulty || undefined,
    category: category || undefined,
  });

  // A selection only means something against the rows it was made on:
  // reset whenever the page or any filter changes the row set. Render-time
  // seeding, same pattern as `use-paged-list` (no setState-in-effect).
  const listKey = `${list.page}:${scope}:${status}:${visibility}:${search}:${author}:${difficulty}:${category}:${ordering}`;
  const [selectionKey, setSelectionKey] = useState(listKey);
  if (selectionKey !== listKey) {
    setSelectionKey(listKey);
    setChecked(new Set());
  }

  const totals = {
    all: useRecipeCount({}),
    published: useRecipeCount({ status: "published" }),
    draft: useRecipeCount({ status: "draft" }),
    unlisted: useRecipeCount({ visibility: "unlisted" }),
    archived: useRecipeCount({ status: "archived" }),
  };

  const detail = useApiQuery(
    (signal) =>
      selected
        ? api.get<RecipeDetail>(`/recipes/${selected}/`, { signal })
        : Promise.resolve(null),
    [selected],
  );

  const hasFilters = Boolean(
    search ||
      author ||
      status ||
      visibility ||
      difficulty ||
      category ||
      scope !== "all",
  );

  function toggleChecked(slug: string) {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function togglePage() {
    setChecked((current) =>
      current.size === list.rows.length
        ? new Set()
        : new Set(list.rows.map((row) => row.slug)),
    );
  }

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

  /** Run one existing endpoint per selected row; report the batch honestly. */
  async function runBulk(
    label: string,
    slugs: string[],
    perRow: (slug: string) => Promise<unknown>,
  ) {
    setBusy(true);
    let done = 0;
    const failures: string[] = [];
    for (const slug of slugs) {
      try {
        await perRow(slug);
        done += 1;
      } catch {
        failures.push(slug);
      }
    }
    setBusy(false);
    setChecked(new Set());
    setSelected(null);
    list.refetch();
    if (failures.length === 0) {
      toast(`${label} ${done} รายการเรียบร้อย`, "success");
    } else {
      toast(
        `${label}สำเร็จ ${done} รายการ, ล้มเหลว ${failures.length} (${failures.join(", ")})`,
        "danger",
      );
    }
  }

  function bulkTransition(label: string, action: Transition, skip: string) {
    // Rows already in the target state are skipped, not errored.
    const rows = list.rows.filter(
      (row) => checked.has(row.slug) && row.status !== skip,
    );
    if (rows.length === 0) {
      toast("รายการที่เลือกอยู่ในสถานะนั้นแล้วทั้งหมด", "neutral");
      return;
    }
    confirm.ask({
      title: `${label} ${rows.length} รายการ?`,
      body: "ระบบจะยิงคำสั่งทีละสูตรตาม API ที่มีจริง และสรุปผลเมื่อครบ",
      confirmLabel: label,
      action: () =>
        runBulk(label, rows.map((row) => row.slug), (slug) =>
          runTransition("/recipes", slug, action),
        ),
    });
  }

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  /** The row's "…" menu: only verbs the backend really has. */
  function rowMenu(row: RecipeListItem) {
    return [
      {
        key: "view",
        label: "ดูสูตรบนเว็บ",
        onSelect: () =>
          window.open(`/recipes/${encodeURIComponent(row.slug)}`, "_blank"),
      },
      {
        key: "detail",
        label: "ดูรายละเอียด",
        onSelect: () => setSelected(row.slug),
      },
      row.status !== "published"
        ? {
            key: "publish",
            label: "เผยแพร่",
            onSelect: () => transition(row.slug, "publish"),
          }
        : {
            key: "unpublish",
            label: "ถอนกลับเป็นฉบับร่าง",
            onSelect: () => transition(row.slug, "unpublish"),
          },
      ...(row.status !== "archived"
        ? [
            {
              key: "archive",
              label: "เก็บเข้าคลัง",
              onSelect: () =>
                confirm.ask({
                  title: "เก็บสูตรเข้าคลัง?",
                  body: `“${row.title}” จะหายจากหน้าเว็บสาธารณะ แต่ข้อมูลยังอยู่ครบและย้อนกลับได้`,
                  confirmLabel: "เก็บเข้าคลัง",
                  action: () => transition(row.slug, "archive"),
                }),
            },
          ]
        : []),
      {
        key: "delete",
        separator: true,
        label: <span className="text-danger">ลบถาวร</span>,
        onSelect: () =>
          confirm.ask({
            title: "ลบสูตรนี้ถาวร?",
            body: `“${row.title}” จะถูกลบออกจากฐานข้อมูลอย่างถาวร กู้คืนไม่ได้  ถ้าต้องการแค่ซ่อน ให้ใช้ “เก็บเข้าคลัง” แทน`,
            confirmLabel: "ลบถาวร",
            danger: true,
            action: () => destroy(row.slug, row.title),
          }),
      },
    ];
  }

  const emptyState = hasFilters ? (
    <AdminEmpty
      title="ไม่พบสูตรอาหาร"
      description="ลองเปลี่ยนคำค้นหาหรือตัวกรองของคุณ"
    />
  ) : (
    <div>
      <AdminEmpty
        title="ยังไม่มีสูตรอาหาร"
        description="เริ่มสร้างสูตรแรกของ KawaiiBake ได้เลย"
      />
      <div className="flex justify-center pb-6">
        <Link href="/admin/recipes/new">
          <Button size="sm">+ เพิ่มสูตรใหม่</Button>
        </Link>
      </div>
    </div>
  );

  return (
    <>
      <AdminPageHeader
        title="สูตรอาหาร"
        description="จัดการสูตรอาหารทั้งหมดของ KawaiiBake — ทุกสถานะ ทุกผู้เขียน"
        actions={
          <Link href="/admin/recipes/new">
            <Button size="sm">+ เพิ่มสูตรใหม่</Button>
          </Link>
        }
      />

      {/* Summary strip — each card is a live count and a one-click filter. */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <MiniStat
          label="สูตรทั้งหมด"
          count={totals.all.data?.count}
          loading={totals.all.loading}
          active={!status && !visibility}
          onClick={() => {
            setStatus("");
            setVisibility("");
          }}
        />
        <MiniStat
          label="เผยแพร่"
          count={totals.published.data?.count}
          loading={totals.published.loading}
          active={status === "published"}
          onClick={() => {
            setStatus("published");
            setVisibility("");
          }}
        />
        <MiniStat
          label="ฉบับร่าง"
          count={totals.draft.data?.count}
          loading={totals.draft.loading}
          active={status === "draft"}
          onClick={() => {
            setStatus("draft");
            setVisibility("");
          }}
        />
        <MiniStat
          label="ไม่แสดงในรายการ"
          count={totals.unlisted.data?.count}
          loading={totals.unlisted.loading}
          active={visibility === "unlisted"}
          onClick={() => {
            setStatus("");
            setVisibility("unlisted");
          }}
        />
        <MiniStat
          label="เก็บเข้าคลัง"
          count={totals.archived.data?.count}
          loading={totals.archived.loading}
          active={status === "archived"}
          onClick={() => {
            setStatus("archived");
            setVisibility("");
          }}
        />
      </div>

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center whitespace-nowrap text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> รายการ
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาชื่อสูตรหรือคำโปรย…"
            label="ค้นหาสูตร"
          />
          <SearchInput
            value={authorInput}
            onChange={setAuthorInput}
            placeholder="กรองตามผู้เขียน…"
            label="กรองตามผู้เขียน"
          />
          <Button
            size="sm"
            variant="secondary"
            className="lg:hidden"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((value) => !value)}
          >
            <Icon name="ui/filter" className="size-4" tint /> ตัวกรอง
          </Button>
          {/* Below lg the filter row folds behind the button above. */}
          <div className={cn("w-full", filtersOpen ? "block" : "hidden lg:block")}>
            <FilterBar>
              <FilterSelect
                label="ขอบเขต"
                value={scope}
                options={SCOPES}
                onChange={setScope}
              />
              <FilterSelect
                label="สถานะ"
                value={status}
                options={STATUSES}
                onChange={setStatus}
              />
              <FilterSelect
                label="การมองเห็น"
                value={visibility}
                options={VISIBILITIES}
                onChange={setVisibility}
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
          </div>
        </DataTableToolbar>

        {/* Contextual bulk bar — appears only with a selection. */}
        {checked.size > 0 ? (
          <div
            role="toolbar"
            aria-label="จัดการรายการที่เลือก"
            className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-accent/40 bg-accent-subtle px-3 py-2"
          >
            <span className="text-sm font-medium text-fg">
              เลือกแล้ว {checked.size} รายการ
            </span>
            <span className="mx-1 hidden h-4 w-px bg-edge-strong sm:block" />
            <Button
              size="sm"
              variant="secondary"
              loading={busy}
              onClick={() => bulkTransition("เผยแพร่", "publish", "published")}
            >
              เผยแพร่
            </Button>
            <Button
              size="sm"
              variant="secondary"
              loading={busy}
              onClick={() =>
                bulkTransition("เก็บเข้าคลัง", "archive", "archived")
              }
            >
              เก็บเข้าคลัง
            </Button>
            <Button
              size="sm"
              variant="danger"
              loading={busy}
              onClick={() =>
                confirm.ask({
                  title: `ลบ ${checked.size} สูตรถาวร?`,
                  body: "ทุกสูตรที่เลือกจะถูกลบออกจากฐานข้อมูลอย่างถาวร กู้คืนไม่ได้",
                  confirmLabel: "ลบถาวร",
                  danger: true,
                  action: () =>
                    runBulk("ลบ", [...checked], (slug) =>
                      api.delete(`/recipes/${slug}/`),
                    ),
                })
              }
            >
              ลบถาวร
            </Button>
            <button
              type="button"
              onClick={() => setChecked(new Set())}
              className="ml-auto text-xs text-fg-muted underline-offset-2 hover:text-fg hover:underline"
            >
              ล้างการเลือก
            </button>
          </div>
        ) : null}

        {/* Desktop: the dense table. */}
        <div className="hidden md:block">
          <DataTable
            caption="รายการสูตรอาหารทั้งหมดในระบบ"
            loading={list.loading}
            rows={list.rows}
            rowKey={(row) => row.slug}
            onRowClick={(row) => setSelected(row.slug)}
            empty={emptyState}
            columns={[
              {
                key: "select",
                className: "w-8",
                header: (
                  <input
                    type="checkbox"
                    aria-label="เลือกทุกสูตรในหน้านี้"
                    checked={
                      list.rows.length > 0 && checked.size === list.rows.length
                    }
                    onChange={togglePage}
                    className="size-3.5 accent-(--color-accent)"
                  />
                ),
                render: (row) => (
                  <input
                    type="checkbox"
                    aria-label={`เลือก ${row.title}`}
                    checked={checked.has(row.slug)}
                    onChange={() => toggleChecked(row.slug)}
                    onClick={(event) => event.stopPropagation()}
                    className="size-3.5 accent-(--color-accent)"
                  />
                ),
              },
              {
                key: "cover",
                header: "ภาพ",
                className: "w-14",
                render: (row) => (
                  <CoverThumb url={row.cover_image_url} className="h-10 w-14" />
                ),
              },
              {
                key: "title",
                header: "สูตรอาหาร",
                render: (row) => (
                  <div className="min-w-0">
                    <p className="line-clamp-1 font-medium">{row.title}</p>
                    <p className="font-mono text-xs text-fg-subtle">
                      {row.slug}
                    </p>
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
                  <span className="line-clamp-1 text-xs text-fg-muted">
                    {row.categories.map((item) => item.name).join(", ") || "-"}
                  </span>
                ),
              },
              {
                key: "difficulty",
                header: "ระดับ",
                render: (row) => (
                  <span className="text-xs text-fg-muted">
                    {DIFFICULTY_LABELS[row.difficulty] ?? row.difficulty}
                  </span>
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
                key: "updated",
                header: "อัปเดตล่าสุด",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {relativeThai(row.updated_at)}
                  </span>
                ),
              },
              {
                key: "actions",
                header: "การจัดการ",
                className: "w-px",
                render: (row) => (
                  <span
                    className="flex items-center gap-1"
                    // The row itself opens the detail drawer; actions must not.
                    onClick={(event) => event.stopPropagation()}
                  >
                    <Link
                      href={`/admin/recipes/${encodeURIComponent(row.slug)}/edit`}
                      className="rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                    >
                      แก้ไข
                    </Link>
                    <Dropdown
                      trigger={
                        <span
                          aria-label={`ตัวเลือกเพิ่มเติมของ ${row.title}`}
                          className="block rounded px-1.5 py-1 text-fg-muted hover:bg-surface-sunken hover:text-fg"
                        >
                          …
                        </span>
                      }
                      items={rowMenu(row)}
                    />
                  </span>
                ),
              },
            ]}
          />
        </div>

        {/* Mobile: each row folds into a compact management card. */}
        <div className="md:hidden">
          {list.loading ? (
            <div className="space-y-2" aria-busy="true">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton key={index} className="h-20 w-full rounded-lg" />
              ))}
            </div>
          ) : list.rows.length === 0 ? (
            emptyState
          ) : (
            <ul className="space-y-2">
              {list.rows.map((row) => (
                <li
                  key={row.slug}
                  className="flex gap-3 rounded-lg border border-edge bg-surface p-3"
                >
                  <CoverThumb
                    url={row.cover_image_url}
                    className="h-14 w-16 shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-1 text-sm font-medium">
                      {row.title}
                    </p>
                    <p className="text-xs text-fg-subtle">
                      @{row.author.username} · {relativeThai(row.updated_at)}
                    </p>
                    <p className="mt-1.5 flex flex-wrap gap-1">
                      <StatusBadge status={row.status} />
                      <StatusBadge status={row.visibility} />
                    </p>
                  </div>
                  <span className="flex shrink-0 flex-col items-end justify-between">
                    <Dropdown
                      trigger={
                        <span
                          aria-label={`ตัวเลือกเพิ่มเติมของ ${row.title}`}
                          className="block rounded px-1.5 py-0.5 text-fg-muted hover:bg-surface-sunken hover:text-fg"
                        >
                          …
                        </span>
                      }
                      items={rowMenu(row)}
                    />
                    <Link
                      href={`/admin/recipes/${encodeURIComponent(row.slug)}/edit`}
                      className="rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                    >
                      แก้ไข
                    </Link>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

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
                  <Icon name="ui/edit" className="size-4" /> แก้ไขสูตร
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
                    body: `“${detail.data!.title}” จะถูกลบออกจากฐานข้อมูลอย่างถาวร กู้คืนไม่ได้  ถ้าต้องการแค่ซ่อน ให้ใช้ “เก็บเข้าคลัง” แทน`,
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
            <DetailRow label="ระดับ">
              {DIFFICULTY_LABELS[detail.data.difficulty] ??
                detail.data.difficulty}
            </DetailRow>
            <DetailRow label="เวลารวม">
              {detail.data.total_minutes} นาที
            </DetailRow>
            <DetailRow label="หมวดหมู่">
              {detail.data.categories.map((item) => item.name).join(", ") || ""}
            </DetailRow>
            <DetailRow label="วัตถุดิบ">
              {detail.data.ingredients.length} รายการ
            </DetailRow>
            <DetailRow label="ขั้นตอน">{detail.data.steps.length} ขั้น</DetailRow>
            <DetailRow label="สร้างเมื่อ">
              {relativeThai(detail.data.created_at)}
            </DetailRow>
            <DetailRow label="อัปเดตล่าสุด">
              {relativeThai(detail.data.updated_at)}
            </DetailRow>
            <DetailRow label="สรุป">
              <span className="text-fg-muted">{detail.data.summary || ""}</span>
            </DetailRow>
          </dl>
        ) : null}
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}
