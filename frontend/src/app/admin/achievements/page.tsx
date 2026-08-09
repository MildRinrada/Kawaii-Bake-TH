"use client";

/**
 * Achievements — read-only, `me`-scoped.
 *
 * Awards are granted by the certificates app's own rules (and its
 * `recalculate` path), never by hand through the API, so there is no
 * grant/revoke control to offer. The badge presentation shown here is
 * the backend's own `title_th` / `icon`, not a client-side table.
 */

import { api, type Paginated } from "@/lib/api/client";
import type { Achievement } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { relativeThai } from "@/lib/datetime";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  UnavailablePanel,
} from "@/components/admin/primitives";

export default function AdminAchievementsPage() {
  const list = useApiQuery(
    (signal) => api.get<Paginated<Achievement>>("/me/achievements/", { signal }),
    [],
  );

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
    <>
      <AdminPageHeader
        title="ความสำเร็จ"
        description="เหรียญความสำเร็จออกให้อัตโนมัติตามกติกาฝั่งเซิร์ฟเวอร์ — ไม่มีการมอบหรือถอนด้วยมือผ่าน API"
      />

      <AdminPanel
        title="ความสำเร็จของบัญชีที่กำลังใช้งาน"
        description="GET /me/achievements/"
      >
        <DataTable
          caption="ความสำเร็จของบัญชีนี้"
          loading={list.loading}
          rows={list.data?.results ?? []}
          rowKey={(row) => row.id}
          empty={<AdminEmpty title="บัญชีนี้ยังไม่มีความสำเร็จ" />}
          columns={[
            {
              key: "badge",
              header: "เหรียญ",
              render: (row) => (
                <span className="flex items-center gap-2">
                  <span aria-hidden>{row.badge?.icon || "🏅"}</span>
                  <span className="font-medium">
                    {row.badge?.title_th || row.achievement_type}
                  </span>
                </span>
              ),
            },
            {
              key: "type",
              header: "รหัส",
              render: (row) => (
                <span className="font-mono text-xs text-fg-subtle">
                  {row.achievement_type}
                </span>
              ),
            },
            {
              key: "description",
              header: "คำอธิบาย",
              render: (row) => (
                <span className="line-clamp-1 text-xs text-fg-muted">
                  {row.badge?.description_th || "—"}
                </span>
              ),
            },
            {
              key: "awarded",
              header: "ได้รับเมื่อ",
              render: (row) => (
                <span className="whitespace-nowrap text-xs text-fg-muted">
                  {relativeThai(row.awarded_at)}
                </span>
              ),
            },
          ]}
        />
      </AdminPanel>

      <div className="mt-4">
        <UnavailablePanel
          title="ความสำเร็จทั้งแพลตฟอร์ม"
          what="ไม่มี endpoint ที่อ่านความสำเร็จของผู้ใช้คนอื่น หรือสรุปว่าเหรียญไหนถูกปลดล็อกไปกี่ครั้ง"
          missing={[
            "GET /api/v1/admin/achievements/ (รายการข้ามผู้ใช้)",
            "สรุปจำนวนผู้ได้รับต่อเหรียญ",
            "รายการนิยามเหรียญทั้งหมด (ตอนนี้เห็นเฉพาะเหรียญที่ตัวเองได้รับแล้ว)",
          ]}
        />
      </div>
    </>
  );
}
