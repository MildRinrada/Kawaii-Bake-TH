"use client";

/**
 * Notifications - the cross-user delivery log plus broadcast.
 *
 * Reads `GET /admin/notifications/` (staff-only): every delivered row
 * with its recipient, filterable by event type and read state. The one
 * write is `POST /admin/notifications/broadcast/`, which fans an
 * announcement out to every active account that has not opted out of
 * the "announcement" event type.
 *
 * Rows are read-only by design: there is no delete endpoint, so no row
 * actions are offered here.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { AdminNotification, BroadcastResult } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

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

export default function AdminNotificationsPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  // Log filters
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [eventType, setEventType] = useState("");
  const [readState, setReadState] = useState("");

  // Broadcast composer
  const [composing, setComposing] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [link, setLink] = useState("");
  const [titleError, setTitleError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const list = usePagedList<AdminNotification>("/admin/notifications/", {
    // Unknown or empty query keys are a 400 on this endpoint - omit them.
    search: search || undefined,
    event_type: eventType || undefined,
    unread: readState === "" ? undefined : readState === "true",
  });

  async function sendBroadcast() {
    setSending(true);
    try {
      const result = await api.post<BroadcastResult>(
        "/admin/notifications/broadcast/",
        {
          body: {
            title: title.trim(),
            ...(body.trim() ? { body: body.trim() } : {}),
            ...(link.trim() ? { link: link.trim() } : {}),
          },
        },
      );
      toast(`ส่งประกาศถึง ${result.recipients} บัญชีแล้ว`, "success");
      setComposing(false);
      setTitle("");
      setBody("");
      setLink("");
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setSending(false);
    }
  }

  function submitBroadcast(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError("กรุณากรอกหัวข้อก่อนส่งประกาศ");
      return;
    }
    setTitleError(null);
    confirm.ask({
      title: "ส่งประกาศถึงทุกคน?",
      body: "ประกาศนี้จะถูกส่งเข้ากล่องแจ้งเตือนของทุกบัญชีที่ยังใช้งานอยู่และไม่ได้ปิดรับ “ประกาศ” - ส่งแล้วเรียกคืนไม่ได้",
      confirmLabel: "ส่งประกาศ",
      action: sendBroadcast,
    });
  }

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="การแจ้งเตือน"
        description="บันทึกการแจ้งเตือนที่ระบบส่งถึงผู้ใช้ทุกคน พร้อมช่องทางประกาศถึงทั้งแพลตฟอร์ม"
        actions={
          <Button size="sm" onClick={() => setComposing((open) => !open)}>
            {composing ? "ปิดฟอร์มประกาศ" : "ประกาศถึงทุกคน"}
          </Button>
        }
      />

      {composing ? (
        <AdminPanel
          title="ประกาศถึงทุกคน"
          description="ส่งเข้ากล่องแจ้งเตือน in-app ของทุกบัญชีที่ใช้งานอยู่และเปิดรับ “ประกาศ”"
          className="mb-4"
        >
          <form onSubmit={submitBroadcast} noValidate className="space-y-3 px-4 py-4">
            <Field
              label="หัวข้อ"
              required
              errors={titleError ? [titleError] : undefined}
            >
              {(control) => (
                <Input
                  {...control}
                  value={title}
                  maxLength={200}
                  placeholder="เช่น ปิดปรับปรุงระบบคืนวันเสาร์"
                  onChange={(event) => {
                    setTitle(event.target.value);
                    if (titleError) setTitleError(null);
                  }}
                />
              )}
            </Field>
            <Field label="ข้อความ" hint="ไม่บังคับ ยาวได้ไม่เกิน 500 ตัวอักษร">
              {(control) => (
                <Textarea
                  {...control}
                  value={body}
                  maxLength={500}
                  rows={3}
                  onChange={(event) => setBody(event.target.value)}
                />
              )}
            </Field>
            <Field label="ลิงก์" hint="ไม่บังคับ - เส้นทางในเว็บ เช่น /courses">
              {(control) => (
                <Input
                  {...control}
                  value={link}
                  maxLength={300}
                  placeholder="/courses"
                  onChange={(event) => setLink(event.target.value)}
                />
              )}
            </Field>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setComposing(false)}
              >
                ยกเลิก
              </Button>
              <Button type="submit" size="sm" loading={sending}>
                ส่งประกาศ
              </Button>
            </div>
          </form>
        </AdminPanel>
      ) : null}

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

      {confirm.dialog}
    </>
  );
}
