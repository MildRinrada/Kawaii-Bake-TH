"use client";

/**
 * The per-recipient delivery log - every notification snapshot the
 * platform has created, across campaigns and machine events alike.
 *
 * Moved here from `/admin/notifications` when that page became the
 * campaign hub (ADR 0030). Rows are read-only by design: there is no
 * delete endpoint, so no row actions are offered.
 */

import Link from "next/link";
import { useState } from "react";

import type { AdminNotification } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { Badge, type Tone } from "@/components/ui/badge";
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
  Pagination,
  SearchInput,
} from "@/components/admin/primitives";

/** Every event type the backend emits, with its admin-facing label. */
const EVENT_TYPES: { value: string; label: string; tone: Tone }[] = [
  { value: "announcement", label: "ประกาศ", tone: "berry" },
  { value: "review_received", label: "ได้รับรีวิว", tone: "peach" },
  { value: "course_enrollment", label: "มีผู้ลงเรียน", tone: "mint" },
  { value: "achievement_earned", label: "ได้รับเหรียญ", tone: "butter" },
  { value: "qa_answer_received", label: "มีคำตอบ", tone: "lavender" },
  { value: "qa_answer_accepted", label: "คำตอบถูกเลือก", tone: "success" },
];

const EVENT_BY_VALUE = new Map(EVENT_TYPES.map((item) => [item.value, item]));

const READ_STATES = [
  { value: "", label: "ทั้งหมด" },
  { value: "true", label: "ยังไม่อ่าน" },
  { value: "false", label: "อ่านแล้ว" },
];

function EventTypeBadge({ eventType }: { eventType: string }) {
  const meta = EVENT_BY_VALUE.get(eventType);
  return (
    <Badge tone={meta?.tone ?? "neutral"} className="whitespace-nowrap">
      {meta?.label ?? eventType}
    </Badge>
  );
}

export default function AdminNotificationLogPage() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [eventType, setEventType] = useState("");
  const [readState, setReadState] = useState("");

  const list = usePagedList<AdminNotification>("/admin/notifications/", {
    // Unknown or empty query keys are a 400 on this endpoint - omit them.
    search: search || undefined,
    event_type: eventType || undefined,
    unread: readState === "" ? undefined : readState === "true",
  });

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="บันทึกรายผู้รับ"
        description="ทุกการแจ้งเตือนที่ระบบสร้างถึงผู้ใช้แต่ละคน ทั้งจากแคมเปญและเหตุการณ์อัตโนมัติ"
        actions={
          <Link href="/admin/notifications">
            <Button size="sm" variant="secondary">
              ← กลับไปหน้าจัดการแจ้งเตือน
            </Button>
          </Link>
        }
      />

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
            placeholder="ค้นหาหัวข้อ ข้อความ หรือผู้รับ…"
            label="ค้นหาการแจ้งเตือน"
          />
          <FilterBar>
            <FilterSelect
              label="ประเภท"
              value={eventType}
              options={[
                { value: "", label: "ทุกประเภท" },
                ...EVENT_TYPES.map(({ value, label }) => ({ value, label })),
              ]}
              onChange={setEventType}
            />
            <FilterSelect
              label="สถานะการอ่าน"
              value={readState}
              options={READ_STATES}
              onChange={setReadState}
            />
          </FilterBar>
        </DataTableToolbar>

        <DataTable
          caption="บันทึกการแจ้งเตือนทั้งแพลตฟอร์ม"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          empty={
            <AdminEmpty
              title="ไม่พบการแจ้งเตือนที่ตรงกับเงื่อนไข"
              description="ลองล้างคำค้นหรือเปลี่ยนตัวกรอง"
            />
          }
          columns={[
            {
              key: "recipient",
              header: "ผู้รับ",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">
                    {row.recipient_display_name}
                  </p>
                  <p className="font-mono text-xs text-fg-subtle">
                    @{row.recipient}
                  </p>
                </div>
              ),
            },
            {
              key: "type",
              header: "ประเภท",
              render: (row) => <EventTypeBadge eventType={row.event_type} />,
            },
            {
              key: "message",
              header: "ข้อความ",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1">{row.title}</p>
                  {row.body ? (
                    <p className="line-clamp-1 text-xs text-fg-muted">
                      {row.body}
                    </p>
                  ) : null}
                </div>
              ),
            },
            {
              key: "read",
              header: "อ่านแล้ว",
              render: (row) =>
                row.read_at ? (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {relativeThai(row.read_at)}
                  </span>
                ) : (
                  <Badge tone="warning" className="whitespace-nowrap">
                    ยังไม่อ่าน
                  </Badge>
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

        <Pagination
          page={list.page}
          pageSize={list.pageSize}
          count={list.count}
          onPage={list.setPage}
        />
      </AdminPanel>

      {/* The one honest gap: in-app only, so read receipts are the whole
          delivery story - no email pipeline exists to report on. */}
      <p className="mt-3 text-xs text-fg-muted">
        ระบบแจ้งเตือนเป็น in-app เท่านั้น - ไม่มีการส่งอีเมล จึงไม่มีสถานะ
        delivered/bounced ให้ติดตาม “อ่านแล้ว”
        คือใบเสร็จเดียวที่ระบบยืนยันได้จริง
      </p>
    </>
  );
}
