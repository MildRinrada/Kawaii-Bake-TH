"use client";

/**
 * Category management.
 *
 * Reads `GET /admin/recipe-categories/`  the staff list that includes
 * inactive rows and returns a plain array, not a paginated envelope: the
 * taxonomy is a small curated set the page loads once. Search and the
 * status filter therefore run in the client; there is no server-side
 * search to defer to.
 *
 * Writes go through the slide-over in `category-form.tsx`: create, edit
 * (changed fields only), photo removal, and delete. Every mutation
 * refetches this list, which is the single source the table renders.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { AdminCategory } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { categoryArt, categoryIcon } from "@/lib/assets";
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
  SearchInput,
} from "@/components/admin/primitives";
import { CategoryForm, isKnownIconKey } from "./category-form";

const STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "active", label: "ใช้งาน" },
  { value: "hidden", label: "ซ่อนอยู่" },
];

/** The active/hidden chip  `StatusBadge`'s "hidden" reads as moderation
    red, which is wrong for a category an admin parked on purpose. */
function ActiveChip({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ${
        active
          ? "bg-success-subtle text-success"
          : "bg-surface-sunken text-fg-muted"
      }`}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {active ? "ใช้งาน" : "ซ่อนอยู่"}
    </span>
  );
}

export default function AdminCategoriesPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState<AdminCategory | null>(null);
  const [creating, setCreating] = useState(false);

  const categories = useApiQuery(
    (signal) =>
      api.get<AdminCategory[]>("/admin/recipe-categories/", { signal }),
    [],
  );

  const term = search.trim().toLowerCase();
  const rows = (categories.data ?? []).filter(
    (item) =>
      (!term ||
        item.name.toLowerCase().includes(term) ||
        item.slug.toLowerCase().includes(term)) &&
      (!status || (status === "active") === item.is_active),
  );
  const totalRecipes = (categories.data ?? []).reduce(
    (sum, item) => sum + item.recipe_count,
    0,
  );

  const formOpen = creating || editing !== null;
  function closeForm() {
    setCreating(false);
    setEditing(null);
  }

  if (categories.error) {
    return <ErrorState error={categories.error} onRetry={categories.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="หมวดหมู่"
        description="อนุกรมวิธานของสูตรและคอร์ส  สร้าง แก้ไข จัดลำดับ และซ่อนหมวดได้จากหน้านี้"
        actions={
          <Button size="sm" onClick={() => setCreating(true)}>
            + เพิ่มหมวดหมู่
          </Button>
        }
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              {rows.length} หมวด · รวม{" "}
              <span className="font-mono tabular-nums">{totalRecipes}</span> สูตร
            </span>
          }
        >
          {/* Filtering happens in the client because the endpoint is a
              single unpaginated read  there is no server-side search. */}
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="ค้นหาหมวด…"
            label="ค้นหาหมวดหมู่"
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
          caption="หมวดหมู่ทั้งหมด รวมหมวดที่ซ่อนอยู่"
          loading={categories.loading}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={(row) => setEditing(row)}
          empty={
            <AdminEmpty
              title="ไม่พบหมวดที่ตรงกับเงื่อนไข"
              description="ลองล้างคำค้นหรือเปลี่ยนตัวกรอง"
            />
          }
          columns={[
            {
              key: "photo",
              header: "ภาพ",
              className: "w-14",
              render: (row) =>
                row.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
                  <img
                    src={row.image_url}
                    alt=""
                    className="h-10 w-14 rounded-md object-cover"
                  />
                ) : (
                  // No uploaded photo: show the built-in art the public
                  // site falls back to, dimmed so the gap stays visible.
                  // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
                  <img
                    src={categoryArt(row.slug)}
                    alt=""
                    title="ใช้ภาพมาตรฐาน"
                    className="h-10 w-14 rounded-md object-cover opacity-50"
                  />
                ),
            },
            {
              key: "icon",
              header: "ไอคอน",
              className: "w-px",
              render: (row) =>
                isKnownIconKey(row.icon) ? (
                  // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
                  <img
                    src={categoryIcon(row.icon)}
                    alt=""
                    title={row.icon}
                    className="size-6"
                  />
                ) : (
                  // Most rows hold an emoji; unknown keys show as-is.
                  <span aria-hidden className="text-lg">
                    {row.icon}
                  </span>
                ),
            },
            {
              key: "order",
              header: "ลำดับ",
              numeric: true,
              render: (row) => row.display_order,
            },
            {
              key: "name",
              header: "ชื่อหมวด",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.name}</p>
                  <p className="font-mono text-xs text-fg-subtle">{row.slug}</p>
                </div>
              ),
            },
            {
              key: "description",
              header: "คำอธิบาย",
              render: (row) => (
                <span className="line-clamp-1 text-xs text-fg-muted">
                  {row.description || ""}
                </span>
              ),
            },
            {
              key: "recipes",
              header: "จำนวนสูตร",
              numeric: true,
              render: (row) => row.recipe_count,
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => <ActiveChip active={row.is_active} />,
            },
          ]}
        />
      </AdminPanel>

      {/* Keyed by row so opening another category resets the fields. */}
      <CategoryForm
        key={editing?.id ?? "new"}
        open={formOpen}
        initial={editing}
        onClose={closeForm}
        onSaved={categories.refetch}
      />
    </>
  );
}
