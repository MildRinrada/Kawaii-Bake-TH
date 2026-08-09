"use client";

/**
 * Progress.
 *
 * Every progress read in this API is `me`-scoped by design — the
 * learning apps deliberately never expose one learner's progress to
 * another caller, staff included. So this page shows the signed-in
 * admin's own enrolments (real data, honestly labelled) and names the
 * endpoints a platform-wide view would need.
 */

import { api } from "@/lib/api/client";
import type { MyCourseProgress } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { relativeThai } from "@/lib/datetime";
import { ErrorState } from "@/components/ui/error-state";
import { ProgressBar } from "@/components/ui/progress-bar";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  StatusBadge,
  UnavailablePanel,
} from "@/components/admin/primitives";

export default function AdminProgressPage() {
  const progress = useApiQuery(
    (signal) =>
      api.get<{ courses: MyCourseProgress[] }>("/me/progress/", { signal }),
    [],
  );

  if (progress.error) {
    return <ErrorState error={progress.error} onRetry={progress.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="ความคืบหน้า"
        description="ข้อมูลความคืบหน้าอ่านได้เฉพาะของบัญชีผู้เรียกเองเท่านั้น (ทั้งระบบ ไม่ใช่แค่หน้านี้)"
      />

      <AdminPanel
        title="ความคืบหน้าของบัญชีที่กำลังใช้งาน"
        description="GET /me/progress/ — นี่คือข้อมูลของคุณเอง ไม่ใช่ของทั้งแพลตฟอร์ม"
      >
        <DataTable
          caption="คอร์สที่บัญชีนี้ลงทะเบียน"
          loading={progress.loading}
          rows={progress.data?.courses ?? []}
          rowKey={(row) => row.slug}
          empty={<AdminEmpty title="บัญชีนี้ยังไม่ได้ลงทะเบียนคอร์สใด" />}
          columns={[
            {
              key: "title",
              header: "คอร์ส",
              render: (row) => (
                <span className="line-clamp-1 font-medium">{row.title}</span>
              ),
            },
            {
              key: "lessons",
              header: "บทที่จบ",
              numeric: true,
              render: (row) => `${row.completed_lessons}/${row.total_lessons}`,
            },
            {
              key: "percent",
              header: "ความคืบหน้า",
              render: (row) => (
                <div className="flex items-center gap-2">
                  <ProgressBar
                    percent={row.percentage}
                    label={`ความคืบหน้า ${row.title}`}
                    className="h-2 w-24"
                  />
                  <span className="font-mono text-xs tabular-nums text-fg-muted">
                    {row.percentage}%
                  </span>
                </div>
              ),
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => (
                <StatusBadge status={row.completed_at ? "completed" : "active"} />
              ),
            },
            {
              key: "completed",
              header: "จบเมื่อ",
              render: (row) => (
                <span className="whitespace-nowrap text-xs text-fg-muted">
                  {row.completed_at ? relativeThai(row.completed_at) : "—"}
                </span>
              ),
            },
          ]}
        />
      </AdminPanel>

      <div className="mt-4">
        <UnavailablePanel
          title="ความคืบหน้าทั้งแพลตฟอร์ม"
          what="ไม่มีมุมมองความคืบหน้าข้ามผู้ใช้ — ทั้ง /me/progress/ และ /courses/{slug}/progress/ ตอบเฉพาะข้อมูลของผู้เรียก ดังนั้นตารางผู้เรียนรายคอร์ส อัตราการเรียนจบ หรือคอร์สที่คนเลิกเรียนกลางทาง ยังทำไม่ได้จนกว่าจะมี endpoint ใหม่"
          missing={[
            "GET /api/v1/courses/{slug}/enrollments/ (รายชื่อผู้เรียนพร้อมความคืบหน้า)",
            "GET /api/v1/admin/progress/ (สรุปรวมทั้งแพลตฟอร์ม)",
            "อัตราการเรียนจบ / จุดที่ผู้เรียนหลุดกลางคัน",
          ]}
        />
      </div>
    </>
  );
}
