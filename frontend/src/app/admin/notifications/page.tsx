"use client";

/**
 * Notifications hub - the staff campaign manager (ADR 0030).
 *
 * Campaigns are staff-authored sends with a lifecycle (draft →
 * scheduled → sent / canceled); templates are reusable composer
 * starting points. Composition lives at `/admin/notifications/compose`,
 * the per-recipient delivery log at `/admin/notifications/log`. This is
 * NOT the user's notification-preferences page - that stays in
 * `/settings`.
 *
 * Every number here is a real count from the API. Sent campaigns can be
 * amended (content only - the delivered copies update too) or deleted,
 * which **retracts** them: in-app rows make un-sending real (ADR 0030
 * amendment). Audience and schedule stay history once sent.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type {
  AdminNotificationStats,
  AudienceEstimate,
  BroadcastResult,
  CampaignAnalytics,
  NotificationCampaign,
  NotificationTemplateItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  DetailPanel,
  DetailRow,
  Pagination,
  SearchInput,
  StatCard,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";
import { cn } from "@/lib/cn";

import { Icon } from "@/components/ui/icon";
import { announcementStyle } from "@/lib/notifications";

import { CAMPAIGN_STATUS, audienceLabel, kindLabel } from "./kinds";
import { NotificationPreviewCard } from "./preview-card";
import { TemplateForm } from "./template-form";

/**
 * The announcement's kind, drawn the way its recipients will see it.
 *
 * Staff used to pick an emoji here and readers never saw it; now the
 * kind picks one glyph and one colour for both sides, so a row in this
 * table looks like the row that landed in the inbox.
 */
function KindGlyph({ kind }: { kind: string }) {
  const style = announcementStyle(kind);
  return (
    <span
      aria-hidden
      title={style.label}
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-full",
        style.tone,
      )}
    >
      <Icon tint name={`ui/${style.icon}`} className="size-4.5" />
    </span>
  );
}

const TABS = [
  { key: "all", label: "ทั้งหมด" },
  { key: "draft", label: "ฉบับร่าง" },
  { key: "scheduled", label: "ตั้งเวลา" },
  { key: "sent", label: "ส่งแล้ว" },
  { key: "templates", label: "เทมเพลต" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function StatusBadgeFor({ campaign }: { campaign: NotificationCampaign }) {
  const meta = CAMPAIGN_STATUS[campaign.status] ?? {
    label: campaign.status,
    tone: "neutral" as const,
  };
  const overdue =
    campaign.status === "scheduled" &&
    campaign.scheduled_at !== null &&
    new Date(campaign.scheduled_at) <= new Date();
  return (
    <div className="space-y-0.5">
      <Badge tone={meta.tone} className="whitespace-nowrap">
        {meta.label}
      </Badge>
      {campaign.status === "scheduled" && campaign.scheduled_at ? (
        <p className="whitespace-nowrap text-xs text-fg-muted">
          {new Date(campaign.scheduled_at).toLocaleString("th-TH", {
            dateStyle: "short",
            timeStyle: "short",
          })}
          {overdue ? (
            <span className="text-warning"> · ถึงกำหนดแล้ว</span>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

/** One labelled rate, drawn as a bar. */
function RateBar({
  label,
  percent,
  tone = "bg-accent",
}: {
  label: string;
  percent: number;
  tone?: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-fg-muted">{label}</span>
        <span className="font-mono font-semibold tabular-nums">{percent}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-2 overflow-hidden rounded-full bg-surface-sunken"
      >
        <div
          className={cn("h-full rounded-full", tone)}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

/** Analytics slide-over for one (usually sent) campaign. */
function CampaignAnalyticsPanel({
  campaign,
  onClose,
}: {
  campaign: NotificationCampaign;
  onClose: () => void;
}) {
  const { data, loading, error, refetch } = useApiQuery(
    (signal) =>
      api.get<CampaignAnalytics>(
        `/admin/notifications/campaigns/${campaign.id}/analytics/`,
        { signal },
      ),
    [campaign.id],
  );
  const percent = data ? Math.round(data.read_rate * 100) : 0;
  const clickPercent = data ? Math.round(data.click_rate * 100) : 0;

  return (
    <DetailPanel open title={`สถิติ: ${campaign.title}`} onClose={onClose}>
      <div className="space-y-4">
        <NotificationPreviewCard
          title={campaign.title}
          body={campaign.body}
          ctaText={campaign.cta_text}
          link={campaign.link}
          kind={campaign.kind}
        />

        {loading ? (
          <Skeleton className="h-32 w-full rounded-md" />
        ) : error ? (
          <ErrorState error={error} onRetry={refetch} />
        ) : data ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              <StatCard label="ผู้รับ" value={data.recipients} />
              <StatCard label="ส่งถึงแล้ว" value={data.delivered} />
              <StatCard label="อ่านแล้ว" value={data.read} />
              <StatCard label="ยังไม่อ่าน" value={data.unread} />
              <StatCard label="กดลิงก์" value={data.clicked} />
              <StatCard
                label="อ่านแต่ไม่กด"
                value={Math.max(0, data.read - data.clicked)}
              />
            </div>
            <RateBar label="อัตราการอ่าน" percent={percent} />
            {campaign.link ? (
              <RateBar
                label="อัตราการกดลิงก์"
                percent={clickPercent}
                tone="bg-lavender-ink"
              />
            ) : null}
            {/* The click count comes from the reader's browser as it
                navigates, so a middle-click or a blocked script is a
                real click nobody counted. Saying so is the difference
                between a number and a number people trust. */}
            <p className="text-xs leading-relaxed text-fg-muted">
              ยอดกดลิงก์นับจากการกดในแอปเท่านั้น
              การเปิดลิงก์ในแท็บใหม่หรือคัดลอกลิงก์ไปเปิดเองจะไม่ถูกนับ
              ตัวเลขนี้จึงเป็นค่าต่ำสุดที่เกิดขึ้นจริง
            </p>
            <div className="rounded-md border border-edge">
              <DetailRow label="กลุ่มเป้าหมาย">
                {audienceLabel(campaign.audience)}
              </DetailRow>
              <DetailRow label="ส่งเมื่อ">
                {data.sent_at
                  ? new Date(data.sent_at).toLocaleString("th-TH")
                  : "-"}
              </DetailRow>
              <DetailRow label="สร้างโดย">
                {campaign.created_by ? `@${campaign.created_by}` : "-"}
              </DetailRow>
            </div>
            <p className="text-xs leading-relaxed text-fg-muted">
              ระบบแจ้งเตือนเป็น in-app เท่านั้น “อ่านแล้ว”
              คือใบเสร็จที่ยืนยันได้จริง ไม่มีอีเมลหรือ push ให้ติดตามสถานะ
            </p>
          </>
        ) : null}
      </div>
    </DetailPanel>
  );
}

export default function AdminNotificationsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const confirm = useConfirm();

  const [tab, setTab] = useState<TabKey>("all");
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [analyticsFor, setAnalyticsFor] =
    useState<NotificationCampaign | null>(null);
  const [templatePanel, setTemplatePanel] = useState<{
    open: boolean;
    item: NotificationTemplateItem | null;
  }>({ open: false, item: null });

  const stats = useApiQuery(
    (signal) =>
      api.get<AdminNotificationStats>("/admin/notifications/stats/", {
        signal,
      }),
    [],
  );
  const campaigns = usePagedList<NotificationCampaign>(
    "/admin/notifications/campaigns/",
    {
      status: tab === "all" || tab === "templates" ? undefined : tab,
      search: search || undefined,
    },
  );
  const templates = useApiQuery(
    (signal) =>
      api.get<NotificationTemplateItem[]>("/admin/notifications/templates/", {
        signal,
      }),
    [],
  );

  function refresh() {
    campaigns.refetch();
    stats.refetch();
  }

  async function sendNow(campaign: NotificationCampaign) {
    // Estimate first, so the confirmation states the real blast radius.
    let estimated: number | null = null;
    try {
      const estimate = await api.post<AudienceEstimate>(
        "/admin/notifications/audience/estimate/",
        { body: { audience: campaign.audience } },
      );
      estimated = estimate.count;
    } catch {
      // The send itself re-validates; the dialog just says "unknown".
    }
    confirm.ask({
      title: `ส่ง “${campaign.title}” ตอนนี้?`,
      body:
        estimated === null
          ? "ไม่สามารถประเมินจำนวนผู้รับได้ - ระบบจะตรวจสอบกลุ่มเป้าหมายอีกครั้งตอนส่ง"
          : `การแจ้งเตือนจะเข้ากล่องของประมาณ ${estimated.toLocaleString("th-TH")} บัญชีทันที (เรียกคืนภายหลังได้ด้วย “ลบและเรียกคืน”)`,
      confirmLabel: "ส่งตอนนี้",
      action: async () => {
        try {
          const result = await api.post<BroadcastResult>(
            `/admin/notifications/campaigns/${campaign.id}/send/`,
          );
          toast(`ส่งถึง ${result.recipients} บัญชีแล้ว`, "success");
          refresh();
        } catch (error) {
          toast(describeAdminError(error), "danger");
        }
      },
    });
  }

  function cancelScheduled(campaign: NotificationCampaign) {
    confirm.ask({
      title: `ยกเลิกการตั้งเวลา “${campaign.title}”?`,
      body: "แคมเปญจะไม่ถูกส่งตามเวลาเดิม และจะย้ายไปสถานะยกเลิก",
      confirmLabel: "ยกเลิกการตั้งเวลา",
      action: async () => {
        try {
          await api.post(
            `/admin/notifications/campaigns/${campaign.id}/cancel/`,
          );
          toast("ยกเลิกการตั้งเวลาแล้ว", "success");
          refresh();
        } catch (error) {
          toast(describeAdminError(error), "danger");
        }
      },
    });
  }

  function deleteCampaign(campaign: NotificationCampaign) {
    const retracting = campaign.status === "sent";
    confirm.ask({
      title: retracting
        ? `ลบและเรียกคืน “${campaign.title}”?`
        : `ลบ “${campaign.title}”?`,
      body: retracting
        ? `การแจ้งเตือนนี้จะถูกลบออกจากกล่องแจ้งเตือนของผู้รับทั้ง ${(campaign.recipients_count ?? 0).toLocaleString("th-TH")} บัญชีทันที - เรียกคืนแล้วกู้กลับไม่ได้`
        : "ลบแล้วกู้คืนไม่ได้",
      confirmLabel: retracting ? "ลบและเรียกคืน" : "ลบแคมเปญ",
      danger: true,
      action: async () => {
        try {
          await api.delete(`/admin/notifications/campaigns/${campaign.id}/`);
          toast(
            retracting ? "เรียกคืนการแจ้งเตือนแล้ว" : "ลบแคมเปญแล้ว",
            "success",
          );
          refresh();
        } catch (error) {
          toast(describeAdminError(error), "danger");
        }
      },
    });
  }

  async function duplicateTemplate(item: NotificationTemplateItem) {
    try {
      await api.post("/admin/notifications/templates/", {
        body: {
          name: `${item.name} (สำเนา)`,
          kind: item.kind,
          title: item.title,
          body: item.body,
          cta_text: item.cta_text,
          link: item.link,
        },
      });
      toast("ทำสำเนาเทมเพลตแล้ว", "success");
      templates.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  async function toggleTemplateArchive(item: NotificationTemplateItem) {
    try {
      await api.patch(`/admin/notifications/templates/${item.id}/`, {
        body: { is_archived: !item.is_archived },
      });
      toast(
        item.is_archived ? "นำเทมเพลตกลับมาใช้แล้ว" : "เก็บเทมเพลตแล้ว",
        "success",
      );
      templates.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  function deleteTemplate(item: NotificationTemplateItem) {
    confirm.ask({
      title: `ลบเทมเพลต “${item.name}”?`,
      body: "แคมเปญที่เคยสร้างจากเทมเพลตนี้ไม่ได้รับผลกระทบ",
      confirmLabel: "ลบเทมเพลต",
      danger: true,
      action: async () => {
        try {
          await api.delete(`/admin/notifications/templates/${item.id}/`);
          toast("ลบเทมเพลตแล้ว", "success");
          templates.refetch();
        } catch (error) {
          toast(describeAdminError(error), "danger");
        }
      },
    });
  }

  function campaignMenu(row: NotificationCampaign) {
    const editable = row.status === "draft" || row.status === "scheduled";
    const items = [];
    if (editable) {
      items.push({
        key: "edit",
        label: "แก้ไข",
        onSelect: () =>
          router.push(`/admin/notifications/compose?edit=${row.id}`),
      });
      items.push({
        key: "send",
        label: "ส่งตอนนี้",
        onSelect: () => void sendNow(row),
      });
    }
    items.push({
      key: "duplicate",
      label: "ทำสำเนา",
      onSelect: () =>
        router.push(`/admin/notifications/compose?from=${row.id}`),
    });
    if (row.status === "sent") {
      items.push({
        key: "analytics",
        label: "ดูสถิติ",
        onSelect: () => setAnalyticsFor(row),
      });
      items.push({
        key: "amend",
        label: "แก้ไขเนื้อหา (อัปเดตถึงผู้รับ)",
        onSelect: () =>
          router.push(`/admin/notifications/compose?edit=${row.id}`),
      });
      items.push({
        key: "retract",
        label: <span className="text-danger">ลบและเรียกคืนจากผู้รับ</span>,
        onSelect: () => deleteCampaign(row),
        separator: true,
      });
    }
    if (row.status === "scheduled") {
      items.push({
        key: "cancel",
        label: "ยกเลิกการตั้งเวลา",
        onSelect: () => cancelScheduled(row),
        separator: true,
      });
    }
    if (row.status === "draft" || row.status === "canceled") {
      items.push({
        key: "delete",
        label: <span className="text-danger">ลบแคมเปญ</span>,
        onSelect: () => deleteCampaign(row),
        separator: true,
      });
    }
    return items;
  }

  const readRate =
    stats.data && stats.data.delivered_total > 0
      ? `${Math.round((stats.data.read_total / stats.data.delivered_total) * 100)}%`
      : null;
  const clickRate =
    stats.data && stats.data.delivered_total > 0
      ? `${Math.round((stats.data.clicked_total / stats.data.delivered_total) * 100)}%`
      : null;

  if (campaigns.error) {
    return <ErrorState error={campaigns.error} onRetry={campaigns.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="การแจ้งเตือน"
        description="สร้าง ปรับแต่ง และจัดการการแจ้งเตือนที่ส่งถึงผู้ใช้ KawaiiBake"
        actions={
          <div className="flex gap-2">
            <Link href="/admin/notifications/log">
              <Button size="sm" variant="secondary">
                บันทึกรายผู้รับ
              </Button>
            </Link>
            <Link href="/admin/notifications/compose?kind=announcement">
              <Button size="sm" variant="secondary">
                ส่งประกาศ
              </Button>
            </Link>
            <Link href="/admin/notifications/compose">
              <Button size="sm">+ สร้างการแจ้งเตือน</Button>
            </Link>
          </div>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-6">
        <StatCard
          label="แคมเปญที่ส่งแล้ว"
          value={stats.data?.campaigns_sent}
          loading={stats.loading}
        />
        <StatCard
          label="ส่งวันนี้"
          value={stats.data?.sent_today}
          hint="รวมการแจ้งเตือนอัตโนมัติ"
          loading={stats.loading}
        />
        <StatCard
          label="ตั้งเวลาไว้"
          value={stats.data?.scheduled}
          loading={stats.loading}
        />
        <StatCard
          label="ฉบับร่าง"
          value={stats.data?.drafts}
          loading={stats.loading}
        />
        <StatCard
          label="อัตราการอ่าน"
          value={readRate}
          hint={
            stats.data
              ? `อ่าน ${stats.data.read_total.toLocaleString("th-TH")} จาก ${stats.data.delivered_total.toLocaleString("th-TH")}`
              : undefined
          }
          loading={stats.loading}
          unavailable={
            stats.data && stats.data.delivered_total === 0
              ? "ยังไม่มีการส่ง"
              : undefined
          }
        />
        <StatCard
          label="อัตราการกดลิงก์"
          value={clickRate}
          hint="นับเฉพาะการกดในแอป จึงเป็นค่าต่ำสุด"
          loading={stats.loading}
          unavailable={
            stats.data && stats.data.delivered_total === 0
              ? "ยังไม่มีการส่ง"
              : undefined
          }
        />
      </div>

      <div
        role="tablist"
        aria-label="มุมมองการแจ้งเตือน"
        className="mb-3 flex flex-wrap gap-1 border-b border-edge"
      >
        {TABS.map((item) => {
          const count =
            item.key === "draft"
              ? stats.data?.drafts
              : item.key === "scheduled"
                ? stats.data?.scheduled
                : item.key === "sent"
                  ? stats.data?.campaigns_sent
                  : item.key === "templates"
                    ? templates.data?.length
                    : undefined;
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={tab === item.key}
              onClick={() => setTab(item.key)}
              className={cn(
                "-mb-px rounded-t-md border-b-2 px-3 py-2 text-sm",
                tab === item.key
                  ? "border-accent font-medium text-fg"
                  : "border-transparent text-fg-muted hover:text-fg",
              )}
            >
              {item.label}
              {count !== undefined ? (
                <span className="ml-1.5 rounded-full bg-surface-sunken px-1.5 py-0.5 font-mono text-xs tabular-nums">
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {tab === "templates" ? (
        <AdminPanel>
          <DataTableToolbar
            actions={
              <Button
                size="sm"
                onClick={() => setTemplatePanel({ open: true, item: null })}
              >
                + สร้างเทมเพลต
              </Button>
            }
          >
            <span className="self-center text-xs text-fg-muted">
              เทมเพลตคือจุดเริ่มต้นสำเร็จรูปของผู้ดูแล -
              ไม่เกี่ยวกับการตั้งค่าการแจ้งเตือนของผู้ใช้
            </span>
          </DataTableToolbar>
          <DataTable
            caption="เทมเพลตการแจ้งเตือน"
            loading={templates.loading}
            rows={templates.data ?? []}
            rowKey={(row) => row.id}
            empty={
              <AdminEmpty
                title="ยังไม่มีเทมเพลต"
                description="สร้างเทมเพลตเพื่อเริ่มแคมเปญซ้ำ ๆ ได้เร็วขึ้น"
              />
            }
            columns={[
              {
                key: "name",
                header: "เทมเพลต",
                render: (row) => (
                  <div className="flex min-w-0 items-center gap-2.5">
                    <KindGlyph kind={row.kind} />
                    <div className="min-w-0">
                      <p className="line-clamp-1 font-medium">{row.name}</p>
                      <p className="line-clamp-1 text-xs text-fg-muted">
                        {row.title}
                      </p>
                    </div>
                  </div>
                ),
              },
              {
                key: "kind",
                header: "ประเภท",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {kindLabel(row.kind)}
                  </span>
                ),
              },
              {
                key: "state",
                header: "สถานะ",
                render: (row) =>
                  row.is_archived ? (
                    <Badge tone="neutral">เก็บแล้ว</Badge>
                  ) : (
                    <Badge tone="success">ใช้งาน</Badge>
                  ),
              },
              {
                key: "updated",
                header: "แก้ไขล่าสุด",
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
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() =>
                        router.push(
                          `/admin/notifications/compose?template=${row.id}`,
                        )
                      }
                      className="whitespace-nowrap rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                    >
                      ใช้เทมเพลต
                    </button>
                    <Dropdown
                      trigger={
                        <span className="px-2 py-1 text-fg-muted">…</span>
                      }
                      items={[
                        {
                          key: "edit",
                          label: "แก้ไข",
                          onSelect: () =>
                            setTemplatePanel({ open: true, item: row }),
                        },
                        {
                          key: "duplicate",
                          label: "ทำสำเนา",
                          onSelect: () => void duplicateTemplate(row),
                        },
                        {
                          key: "archive",
                          label: row.is_archived
                            ? "นำกลับมาใช้"
                            : "เก็บเทมเพลต",
                          onSelect: () => void toggleTemplateArchive(row),
                        },
                        {
                          key: "delete",
                          label: (
                            <span className="text-danger">ลบเทมเพลต</span>
                          ),
                          onSelect: () => deleteTemplate(row),
                          separator: true,
                        },
                      ]}
                    />
                  </div>
                ),
              },
            ]}
          />
        </AdminPanel>
      ) : (
        <AdminPanel>
          <DataTableToolbar
            actions={
              <span className="self-center text-xs text-fg-muted">
                ทั้งหมด{" "}
                <span className="font-mono tabular-nums">
                  {campaigns.count}
                </span>{" "}
                แคมเปญ
              </span>
            }
          >
            <SearchInput
              value={searchInput}
              onChange={setSearchInput}
              placeholder="ค้นหาหัวข้อหรือข้อความ…"
              label="ค้นหาแคมเปญ"
            />
          </DataTableToolbar>

          <DataTable
            caption="แคมเปญการแจ้งเตือน"
            loading={campaigns.loading}
            rows={campaigns.rows}
            rowKey={(row) => row.id}
            empty={
              <AdminEmpty
                title={
                  tab === "all" && !search
                    ? "ยังไม่มีแคมเปญ"
                    : "ไม่พบแคมเปญที่ตรงกับเงื่อนไข"
                }
                description={
                  tab === "all" && !search
                    ? "กด “+ สร้างการแจ้งเตือน” เพื่อเริ่มแคมเปญแรก"
                    : "ลองเปลี่ยนแท็บหรือล้างคำค้น"
                }
              />
            }
            columns={[
              {
                key: "title",
                header: "การแจ้งเตือน",
                render: (row) => (
                  <div className="flex min-w-0 items-center gap-2.5">
                    <KindGlyph kind={row.kind} />
                    <div className="min-w-0">
                      <p className="line-clamp-1 font-medium">{row.title}</p>
                      {row.body ? (
                        <p className="line-clamp-1 text-xs text-fg-muted">
                          {row.body}
                        </p>
                      ) : null}
                    </div>
                  </div>
                ),
              },
              {
                key: "kind",
                header: "ประเภท",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {kindLabel(row.kind)}
                  </span>
                ),
              },
              {
                key: "audience",
                header: "กลุ่มเป้าหมาย",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {audienceLabel(row.audience)}
                  </span>
                ),
              },
              {
                key: "status",
                header: "สถานะ",
                render: (row) => <StatusBadgeFor campaign={row} />,
              },
              {
                key: "reach",
                header: "ผู้รับ / อ่าน",
                render: (row) =>
                  row.status === "sent" ? (
                    <span className="whitespace-nowrap font-mono text-xs tabular-nums">
                      {(row.recipients_count ?? 0).toLocaleString("th-TH")} ·
                      อ่าน {row.read_count.toLocaleString("th-TH")}
                    </span>
                  ) : (
                    <span className="text-xs text-fg-subtle">-</span>
                  ),
              },
              {
                key: "created",
                header: "สร้างโดย",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {row.created_by ? `@${row.created_by}` : "-"}
                    <span className="text-fg-subtle">
                      {" "}
                      · {relativeThai(row.created_at)}
                    </span>
                  </span>
                ),
              },
              {
                key: "actions",
                header: "การจัดการ",
                className: "w-px",
                render: (row) => (
                  <div className="flex items-center gap-1.5">
                    {row.status === "sent" ? (
                      <button
                        type="button"
                        onClick={() => setAnalyticsFor(row)}
                        className="whitespace-nowrap rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                      >
                        ดูสถิติ
                      </button>
                    ) : row.status === "draft" ||
                      row.status === "scheduled" ? (
                      <Link
                        href={`/admin/notifications/compose?edit=${row.id}`}
                        className="whitespace-nowrap rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                      >
                        แก้ไข
                      </Link>
                    ) : null}
                    <Dropdown
                      trigger={
                        <span className="px-2 py-1 text-fg-muted">…</span>
                      }
                      items={campaignMenu(row)}
                    />
                  </div>
                ),
              },
            ]}
          />

          <Pagination
            page={campaigns.page}
            pageSize={campaigns.pageSize}
            count={campaigns.count}
            onPage={campaigns.setPage}
          />
        </AdminPanel>
      )}

      {analyticsFor ? (
        <CampaignAnalyticsPanel
          campaign={analyticsFor}
          onClose={() => setAnalyticsFor(null)}
        />
      ) : null}

      {templatePanel.open ? (
        <TemplateForm
          key={templatePanel.item?.id ?? "new"}
          open
          initial={templatePanel.item}
          onClose={() => setTemplatePanel({ open: false, item: null })}
          onSaved={() => templates.refetch()}
        />
      ) : null}

      {confirm.dialog}
    </>
  );
}
