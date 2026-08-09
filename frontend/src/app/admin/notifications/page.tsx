"use client";

/**
 * Notifications.
 *
 * The notifications API is entirely recipient-scoped: read your own
 * inbox, mark items read. There is no template registry, no send
 * endpoint, no delivery log — so this page manages the caller's own
 * inbox and documents the rest.
 *
 * Per-user notification *preferences* are not duplicated here: they
 * belong to the user and are edited in `/settings`.
 */

import { api } from "@/lib/api/client";
import type { NotificationList } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  StatusBadge,
  UnavailablePanel,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

export default function AdminNotificationsPage() {
  const { toast } = useToast();
  const inbox = useApiQuery(
    (signal) =>
      api.get<NotificationList>("/me/notifications/", {
        query: { page_size: 25 },
        signal,
      }),
    [],
  );

  async function markAllRead() {
    try {
      await api.post("/me/notifications/read-all/");
      toast("ทำเครื่องหมายว่าอ่านแล้วทั้งหมด", "success");
      inbox.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  if (inbox.error) return <ErrorState error={inbox.error} onRetry={inbox.refetch} />;

  return (
    <>
      <AdminPageHeader
        title="การแจ้งเตือน"
        description="API การแจ้งเตือนผูกกับผู้รับเสมอ — หน้านี้จึงจัดการกล่องข้อความของบัญชีที่ใช้งานอยู่"
      />

      <AdminPanel
        title="กล่องแจ้งเตือนของบัญชีนี้"
        description={`ยังไม่อ่าน ${inbox.data?.unread_count ?? 0} รายการ`}
        actions={
          <Button
            size="sm"
            variant="secondary"
            disabled={(inbox.data?.unread_count ?? 0) === 0}
            onClick={markAllRead}
          >
            อ่านทั้งหมดแล้ว
          </Button>
        }
      >
        <DataTable
          caption="การแจ้งเตือนของบัญชีนี้"
          loading={inbox.loading}
          rows={inbox.data?.results ?? []}
          rowKey={(row) => row.id}
          empty={<AdminEmpty title="ไม่มีการแจ้งเตือน" />}
          columns={[
            {
              key: "event",
              header: "ชนิดเหตุการณ์",
              render: (row) => (
                <span className="font-mono text-xs text-fg-subtle">
                  {row.event_type}
                </span>
              ),
            },
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
              key: "actor",
              header: "ผู้ก่อเหตุการณ์",
              render: (row) => (
                <span className="text-fg-muted">{row.actor_handle || "—"}</span>
              ),
            },
            {
              key: "read",
              header: "สถานะ",
              render: (row) => (
                <StatusBadge status={row.read_at ? "active" : "pending"} />
              ),
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
          ]}
        />
      </AdminPanel>

      <div className="mt-4">
        <UnavailablePanel
          title="การส่งและติดตามการแจ้งเตือน"
          what="ไม่มีระบบเทมเพลต การส่งจากฝั่งผู้ดูแล หรือบันทึกผลการส่ง (delivery log) ใน API ปัจจุบัน การแจ้งเตือนถูกสร้างจากเหตุการณ์ในโดเมนเท่านั้น"
          missing={[
            "GET /api/v1/admin/notifications/ (ข้ามผู้ใช้ พร้อมผู้รับและสถานะการส่ง)",
            "GET/POST /api/v1/admin/notification-templates/",
            "POST /api/v1/admin/notifications/broadcast/",
            "สถานะการส่งอีเมล (delivered / bounced)",
          ]}
          workaround="การตั้งค่าการรับแจ้งเตือนเป็นของผู้ใช้แต่ละคน แก้ที่หน้า /settings ของเจ้าของบัญชีเอง — หน้านี้จะไม่ทำซ้ำ"
        />
      </div>
    </>
  );
}
