"use client";

/**
 * Favorites — `me`-scoped, and deliberately so: what a learner saves is
 * private behavioural data the backend never discloses to anyone else,
 * staff included. This page shows the caller's own saves and says what
 * an aggregate view would require.
 */

import type { CourseListItem, FavoriteItem, RecipeListItem } from "@/lib/api/models";
import { usePagedList } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  Pagination,
  UnavailablePanel,
} from "@/components/admin/primitives";

export default function AdminFavoritesPage() {
  const list = usePagedList<FavoriteItem>("/users/me/favorites/", {});

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
    <>
      <AdminPageHeader
        title="รายการโปรด"
        description="ข้อมูลการบันทึกของผู้เรียนเป็นข้อมูลส่วนตัว — API เปิดให้อ่านเฉพาะของเจ้าของบัญชีเท่านั้น"
      />

      <AdminPanel
        title="รายการโปรดของบัญชีที่กำลังใช้งาน"
        description="GET /users/me/favorites/"
      >
        <DataTable
          caption="รายการโปรดของบัญชีนี้"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => `${row.type}-${row.favorited_at}`}
          empty={<AdminEmpty title="บัญชีนี้ยังไม่มีรายการโปรด" />}
          columns={[
            {
              key: "type",
              header: "ชนิด",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.type === "recipe" ? "สูตร" : "คอร์ส"}
                </span>
              ),
            },
            {
              key: "title",
              header: "รายการ",
              render: (row) => {
                const recipe = row.recipe as unknown as RecipeListItem | null;
                const course = row.course as unknown as CourseListItem | null;
                return (
                  <span className="line-clamp-1 font-medium">
                    {recipe?.title ?? course?.title ?? "—"}
                  </span>
                );
              },
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

      <div className="mt-4">
        <UnavailablePanel
          title="สถิติการบันทึกทั้งแพลตฟอร์ม"
          what="ไม่มี endpoint บอกว่าสูตรหรือคอร์สใดถูกบันทึกกี่ครั้ง หรือใครบันทึกอะไร — และการเปิดข้อมูลรายบุคคลก็ขัดกับหลักความเป็นส่วนตัวที่แอปนี้วางไว้ตั้งแต่ต้น"
          missing={[
            "GET /api/v1/admin/favorites/stats/ (จำนวนการบันทึกต่อเนื้อหา — สรุปรวม ไม่ระบุตัวบุคคล)",
            "ฟิลด์ favorite_count ในรายการสูตร/คอร์ส",
          ]}
          workaround="ถ้าจะเพิ่มในอนาคต ควรเป็นตัวเลขสรุปต่อเนื้อหา ไม่ใช่รายชื่อผู้บันทึก"
        />
      </div>
    </>
  );
}
