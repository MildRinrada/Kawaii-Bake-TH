"use client";

/**
 * Favorites  the staff view (ADR 0027).
 *
 * Two reads, zero writes:
 *
 * - `GET /admin/favorites/top/`  the most-favorited recipes and courses,
 *   for a quick popularity pulse.
 * - `GET /admin/favorites/`  the cross-user rows, filterable by target
 *   type and searchable by owner username or target title.
 *
 * Deliberately read-only: a favorite is a user's private signal, so the
 * backend offers staff no way to add or remove one on their behalf.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { AdminFavorite, FavoriteTop } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  FilterSelect,
  Pagination,
  SearchInput,
} from "@/components/admin/primitives";

const TYPE_OPTIONS = [
  { value: "", label: "ทั้งหมด" },
  { value: "recipe", label: "สูตร" },
  { value: "course", label: "คอร์ส" },
];

/* ------------------------------------------------------------------ */
/* Top-favorited rankings                                              */
/* ------------------------------------------------------------------ */

function TopList({
  entries,
  hrefBase,
  emptyLabel,
}: {
  entries: FavoriteTop["recipes"];
  /** `/recipes` or `/courses`  the public detail route for a row. */
  hrefBase: string;
  emptyLabel: string;
}) {
  if (entries.length === 0) {
    return <p className="px-4 py-6 text-sm text-fg-muted">{emptyLabel}</p>;
  }
  return (
    <ol className="divide-y divide-edge/60">
      {entries.map((entry, index) => (
        <li key={entry.id} className="flex items-center gap-3 px-4 py-2.5">
          <span className="w-6 shrink-0 text-right font-mono text-sm tabular-nums text-fg-subtle">
            {index + 1}
          </span>
          {/* Public detail page in a new tab  the admin stays here. */}
          <a
            href={`${hrefBase}/${encodeURIComponent(entry.slug)}`}
            target="_blank"
            rel="noreferrer"
            className="min-w-0 flex-1 truncate text-sm font-medium text-fg hover:text-accent hover:underline"
          >
            {entry.title}
          </a>
          <span className="flex shrink-0 items-center gap-1 text-xs text-fg-muted">
            <Icon name="ui/heart" className="size-3.5" />
            <span className="font-mono tabular-nums">{entry.count}</span> ครั้ง
          </span>
        </li>
      ))}
    </ol>
  );
}

function TopPanels() {
  const top = useApiQuery(
    (signal) => api.get<FavoriteTop>("/admin/favorites/top/", { signal }),
    [],
  );

  const body = (entries: FavoriteTop["recipes"], hrefBase: string, emptyLabel: string) =>
    top.loading ? (
      <div aria-busy="true" className="space-y-2 p-3">
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton key={index} className="h-8 w-full rounded" />
        ))}
      </div>
    ) : top.error ? (
      <div className="p-4">
        <ErrorState error={top.error} onRetry={top.refetch} />
      </div>
    ) : (
      <TopList entries={entries} hrefBase={hrefBase} emptyLabel={emptyLabel} />
    );

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <AdminPanel
        title="สูตรยอดนิยม"
        description="สูตรที่ถูกบันทึกเป็นรายการโปรดมากที่สุด"
      >
        {body(top.data?.recipes ?? [], "/recipes", "ยังไม่มีสูตรที่ถูกบันทึก")}
      </AdminPanel>
      <AdminPanel
        title="คอร์สยอดนิยม"
        description="คอร์สที่ถูกบันทึกเป็นรายการโปรดมากที่สุด"
      >
        {body(top.data?.courses ?? [], "/courses", "ยังไม่มีคอร์สที่ถูกบันทึก")}
      </AdminPanel>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Cross-user favorites table                                          */
/* ------------------------------------------------------------------ */

function FavoritesTable() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [type, setType] = useState("");

  // Empty filters are omitted: the endpoint 400s on unknown/blank keys.
  const list = usePagedList<AdminFavorite>("/admin/favorites/", {
    type: type || undefined,
    search: search || undefined,
  });

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
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
          placeholder="ค้นหา username หรือชื่อรายการ…"
          label="ค้นหารายการโปรด"
        />
        <FilterSelect
          label="ชนิด"
          value={type}
          options={TYPE_OPTIONS}
          onChange={setType}
        />
      </DataTableToolbar>

      {/* Read-only by design: no admin write endpoints exist for
          favorites, because a save is the user's private signal. */}
      <p className="border-b border-edge bg-surface-sunken/60 px-3 py-2 text-xs text-fg-muted">
        รายการโปรดเป็นสัญญาณส่วนตัวของผู้ใช้  หน้านี้อ่านได้อย่างเดียว
        ไม่มีการเพิ่มหรือลบแทนผู้ใช้
      </p>

      <DataTable
        caption="รายการโปรดของผู้ใช้ทุกคน"
        loading={list.loading}
        rows={list.rows}
        rowKey={(row) => row.id}
        empty={
          <AdminEmpty
            title="ไม่พบรายการโปรดที่ตรงกับเงื่อนไข"
            description="ลองล้างคำค้นหรือเปลี่ยนตัวกรองชนิด"
          />
        }
        columns={[
          {
            key: "user",
            header: "ผู้ใช้",
            render: (row) => (
              <div className="min-w-0">
                <p className="line-clamp-1 font-medium">{row.display_name}</p>
                <p className="font-mono text-xs text-fg-subtle">
                  @{row.username}
                </p>
              </div>
            ),
          },
          {
            key: "type",
            header: "ชนิด",
            render: (row) => (
              <Badge tone={row.type === "recipe" ? "berry" : "lavender"}>
                {row.type === "recipe" ? "สูตร" : "คอร์ส"}
              </Badge>
            ),
          },
          {
            key: "target",
            header: "รายการ",
            render: (row) => (
              <div className="min-w-0">
                <p className="line-clamp-1 font-medium">
                  {row.target_title || ""}
                </p>
                <p className="font-mono text-xs text-fg-subtle">
                  {row.target_slug || ""}
                </p>
              </div>
            ),
          },
          {
            key: "saved",
            header: "บันทึกเมื่อ",
            render: (row) => (
              <span className="whitespace-nowrap text-xs text-fg-muted">
                {relativeThai(row.favorited_at)}
              </span>
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
  );
}

/* ------------------------------------------------------------------ */

export default function AdminFavoritesPage() {
  return (
    <>
      <AdminPageHeader
        title="รายการโปรด"
        description="ความนิยมของเนื้อหาจากการบันทึกเป็นรายการโปรด และรายการทั้งหมดข้ามผู้ใช้"
      />
      <div className="space-y-4">
        <TopPanels />
        <FavoritesTable />
      </div>
    </>
  );
}
