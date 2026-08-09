"use client";

/**
 * Categories — read-only by necessity.
 *
 * `GET /recipe-categories/` is the taxonomy's entire API surface: it is
 * an unpaginated read with a real `recipe_count` per row. There is no
 * create, update, reorder or delete endpoint, so this page shows the
 * data and names the gap instead of rendering an edit form that could
 * only fail.
 */

import { api } from "@/lib/api/client";
import type { Category } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useState } from "react";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  SearchInput,
  UnavailablePanel,
} from "@/components/admin/primitives";

export default function AdminCategoriesPage() {
  const [search, setSearch] = useState("");
  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const term = search.trim().toLowerCase();
  const rows = (categories.data ?? []).filter(
    (item) =>
      !term ||
      item.name.toLowerCase().includes(term) ||
      item.slug.toLowerCase().includes(term),
  );
  const totalRecipes = (categories.data ?? []).reduce(
    (sum, item) => sum + item.recipe_count,
    0,
  );

  if (categories.error) {
    return <ErrorState error={categories.error} onRetry={categories.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="หมวดหมู่"
        description="อนุกรมวิธานของสูตรและคอร์ส พร้อมจำนวนสูตรจริงในแต่ละหมวด"
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
              single unpaginated read — there is no server-side search. */}
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="ค้นหาหมวด…"
            label="ค้นหาหมวดหมู่"
          />
        </DataTableToolbar>

        <DataTable
          caption="หมวดหมู่ทั้งหมด"
          loading={categories.loading}
          rows={rows}
          rowKey={(row) => row.id}
          empty={<AdminEmpty title="ไม่พบหมวดที่ตรงกับคำค้น" />}
          columns={[
            {
              key: "order",
              header: "ลำดับ",
              numeric: true,
              render: (row) => row.display_order,
            },
            {
              key: "icon",
              header: "",
              className: "w-px",
              render: (row) => <span aria-hidden>{row.icon}</span>,
            },
            {
              key: "name",
              header: "ชื่อหมวด",
              render: (row) => <span className="font-medium">{row.name}</span>,
            },
            {
              key: "slug",
              header: "slug",
              render: (row) => (
                <span className="font-mono text-xs text-fg-subtle">
                  {row.slug}
                </span>
              ),
            },
            {
              key: "description",
              header: "คำอธิบาย",
              render: (row) => (
                <span className="line-clamp-1 text-xs text-fg-muted">
                  {row.description || "—"}
                </span>
              ),
            },
            {
              key: "recipes",
              header: "จำนวนสูตร",
              numeric: true,
              render: (row) => row.recipe_count,
            },
          ]}
        />
      </AdminPanel>

      <div className="mt-4">
        <UnavailablePanel
          title="การแก้ไขหมวดหมู่"
          what="หมวดหมู่แก้ไขได้ผ่าน Django Admin เท่านั้น — REST API มีแค่การอ่านรายการ จึงยังไม่มีฟอร์มสร้าง/แก้ไข/ลบในหน้านี้"
          missing={[
            "POST /api/v1/recipe-categories/",
            "PATCH /api/v1/recipe-categories/{slug}/",
            "DELETE /api/v1/recipe-categories/{slug}/",
          ]}
          workaround="ระหว่างนี้ใช้ Django Admin ที่ /admin/ ของฝั่งเซิร์ฟเวอร์ (คนละระบบกับหน้านี้) ในการเพิ่มหรือแก้ไขหมวดหมู่"
        />
      </div>
    </>
  );
}
