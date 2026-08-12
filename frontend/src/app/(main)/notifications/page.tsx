"use client";

/** Notification centre: unread marks, day grouping, and type tabs. */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { NotificationItem, NotificationList } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { dayBucket, notificationGroup } from "@/lib/notifications";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { NotificationRow } from "@/components/notifications/notification-item";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

/** The tabs. `unread` filters on state; the rest filter on kind. */
const TABS = [
  { key: "all", label: "ทั้งหมด" },
  { key: "unread", label: "ยังไม่อ่าน" },
  { key: "engagement", label: "การมีส่วนร่วม" },
  { key: "achievement", label: "ความสำเร็จ" },
  { key: "announcement", label: "ประกาศ" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function matches(item: NotificationItem, tab: TabKey): boolean {
  if (tab === "all") return true;
  if (tab === "unread") return item.read_at === null;
  return notificationGroup(item) === tab;
}

/** Consecutive items under "วันนี้" / "เมื่อวาน" / … in arrival order. */
function groupByDay(items: NotificationItem[]) {
  const groups: Array<{ label: string; items: NotificationItem[] }> = [];
  for (const item of items) {
    const label = dayBucket(item.created_at);
    const last = groups.at(-1);
    if (last && last.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }
  return groups;
}

function NotificationsContent() {
  const { toast } = useToast();
  const [tab, setTab] = useState<TabKey>("all");
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

  const all = data?.results ?? [];
  const shown = all.filter((item) => matches(item, tab));
  const groups = groupByDay(shown);

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

      {all.length > 0 ? (
        <div
          role="group"
          aria-label="กรองการแจ้งเตือน"
          className="mb-4 flex flex-wrap gap-2"
        >
          {TABS.map((item) => {
            const count = all.filter((row) => matches(row, item.key)).length;
            return (
              <button
                key={item.key}
                type="button"
                aria-pressed={tab === item.key}
                onClick={() => setTab(item.key)}
                className={cn(
                  "rounded-full px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus",
                  tab === item.key
                    ? "bg-fg font-medium text-fg-inverted shadow-raised"
                    : "border border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
                )}
              >
                {item.label}
                <span className="ml-1.5 text-xs opacity-70">{count}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      {loading ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-16 w-full rounded-surface" />
          <Skeleton className="h-16 w-full rounded-surface" />
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : all.length === 0 ? (
        <EmptyState
          icon={<Icon name="ui/bell" className="size-8 text-fg-subtle" />}
          title="ยังไม่มีการแจ้งเตือน"
          description="เมื่อมีคนรีวิวผลงานหรือมีความเคลื่อนไหว จะแจ้งไว้ที่นี่"
        />
      ) : shown.length === 0 ? (
        <EmptyState
          icon={<Icon name="ui/bell" className="size-8 text-fg-subtle" />}
          title="ไม่มีรายการในหมวดนี้"
          description="ลองดูหมวดอื่น หรือกลับไปที่ทั้งหมด"
        />
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <section key={`${group.label}-${group.items[0].id}`}>
              <h2 className="mb-2 text-sm font-medium text-fg-muted">
                {group.label}
              </h2>
              <ul className="space-y-2.5">
                {group.items.map((item) => (
                  <NotificationRow
                    key={item.id}
                    item={item}
                    onMarkRead={(id) => void markRead(id)}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
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
