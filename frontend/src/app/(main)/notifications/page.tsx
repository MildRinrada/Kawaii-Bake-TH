"use client";

/** Notification center: unread emphasis, read stamps, read-all. */

import { api } from "@/lib/api/client";
import type { NotificationList } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { useToast } from "@/components/ui/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

const EVENT_ICONS: Record<string, string> = {
  review_received: "⭐",
  course_enrollment: "🎓",
  achievement_earned: "🏅",
  qa_answer_received: "💬",
  qa_answer_accepted: "✅",
};

function NotificationsContent() {
  const { toast } = useToast();
  const { data, loading, error, refetch } = useApiQuery(
    (signal) => api.get<NotificationList>("/me/notifications/", { signal }),
    [],
  );

  async function markRead(id: number) {
    try {
      await api.post(`/me/notifications/${id}/read/`);
      refetch();
    } catch {
      toast("ทำรายการไม่สำเร็จ", "danger");
    }
  }

  async function markAll() {
    try {
      await api.post("/me/notifications/read-all/");
      refetch();
      toast("อ่านทั้งหมดแล้ว", "success");
    } catch {
      toast("ทำรายการไม่สำเร็จ", "danger");
    }
  }

  return (
    <>
      <PageHeader
        title="การแจ้งเตือน"
        description={
          data && data.unread_count > 0
            ? `มี ${data.unread_count} รายการที่ยังไม่ได้อ่าน`
            : "ติดตามความเคลื่อนไหวเกี่ยวกับคุณ"
        }
        actions={
          data && data.unread_count > 0 ? (
            <Button variant="secondary" size="sm" onClick={() => void markAll()}>
              อ่านทั้งหมด
            </Button>
          ) : undefined
        }
      />
      {loading ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-20 w-full rounded-surface" />
          <Skeleton className="h-20 w-full rounded-surface" />
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          icon="🔔"
          title="ยังไม่มีการแจ้งเตือน"
          description="เมื่อมีคนรีวิวผลงานหรือมีความเคลื่อนไหว จะแจ้งไว้ที่นี่"
        />
      ) : (
        <ul className="space-y-2.5">
          {data.results.map((item) => {
            const unread = item.read_at === null;
            return (
              <li
                key={item.id}
                className={cn(
                  "flex items-start gap-3.5 rounded-surface border px-4 py-3.5",
                  unread
                    ? "border-accent/30 bg-berry-soft/40"
                    : "border-edge bg-surface",
                )}
              >
                <span
                  aria-hidden
                  className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-lg"
                >
                  {EVENT_ICONS[item.event_type] ?? "🔔"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn("text-sm text-fg", unread && "font-medium")}>
                    {item.title}
                  </p>
                  {item.body ? (
                    <p className="mt-0.5 text-sm text-fg-muted">{item.body}</p>
                  ) : null}
                  <p className="mt-1 text-xs text-fg-subtle">
                    {new Date(item.created_at).toLocaleString("th-TH")}
                  </p>
                </div>
                {unread ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void markRead(item.id)}
                  >
                    อ่านแล้ว
                  </Button>
                ) : (
                  <Badge tone="neutral">อ่านแล้ว</Badge>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

export default function NotificationsPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <NotificationsContent />
      </RequireAuth>
    </PageContainer>
  );
}
