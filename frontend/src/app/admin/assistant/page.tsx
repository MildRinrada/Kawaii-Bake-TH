"use client";

/**
 * AI assistant monitoring.
 *
 * The assistant API lists conversations strictly by owner
 * (`conversation_selector.list_for_user(user_id=request.user.id)`), so
 * there is no cross-user monitoring to render  the spec's "conversations
 * / user / failure state" table would need a new endpoint.
 *
 * What the payloads do carry is real and shown: language, context
 * anchor and prompt version on the conversation, and provider, model
 * name and token counts on each message. Those last three only exist
 * per message, so the list has no provider column  they appear in the
 * transcript, where they are actually recorded. API keys live
 * server-side and appear nowhere in any response.
 *
 * Transcripts stay read-only: the API exposes no moderation operation on
 * messages.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { Conversation, ConversationDetail, Message } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DetailPanel,
  DetailRow,
  Pagination,
  UnavailablePanel,
} from "@/components/admin/primitives";

export default function AdminAssistantPage() {
  const [selected, setSelected] = useState<Conversation | null>(null);

  const list = usePagedList<Conversation>("/me/assistant/conversations/", {});

  const detail = useApiQuery(
    (signal) =>
      selected
        ? api.get<ConversationDetail>(
            `/assistant/conversations/${selected.id}/`,
            { signal },
          )
        : Promise.resolve(null),
    [selected?.id],
  );

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  // `messages` is a paginated envelope, so these totals describe the
  // loaded page only  labelled as such below rather than passed off as
  // the conversation's lifetime cost.
  const messages: Message[] = detail.data?.messages.results ?? [];
  const tokensIn = messages.reduce((sum, item) => sum + (item.token_input ?? 0), 0);
  const tokensOut = messages.reduce(
    (sum, item) => sum + (item.token_output ?? 0),
    0,
  );
  const models = [
    ...new Set(messages.map((item) => item.model_name).filter(Boolean)),
  ];

  return (
    <>
      <AdminPageHeader
        title="ผู้ช่วย AI"
        description="ดูบทสนทนาของบัญชีที่ใช้งานอยู่ พร้อมภาษา บริบท และเวอร์ชันพรอมป์ตที่ใช้จริง"
      />

      <AdminPanel
        title="บทสนทนาของบัญชีนี้"
        description="GET /me/assistant/conversations/  API ไม่มีมุมมองข้ามผู้ใช้"
      >
        <DataTable
          caption="บทสนทนากับผู้ช่วย AI"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          onRowClick={setSelected}
          empty={<AdminEmpty title="บัญชีนี้ยังไม่มีบทสนทนา" />}
          columns={[
            {
              key: "title",
              header: "หัวข้อ",
              render: (row) => (
                <span className="line-clamp-1 font-medium">
                  {row.title || "(ไม่มีหัวข้อ)"}
                </span>
              ),
            },
            {
              key: "language",
              header: "ภาษา",
              render: (row) => (
                <span className="font-mono text-xs text-fg-muted">
                  {row.language}
                </span>
              ),
            },
            {
              key: "context",
              header: "บริบท",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.context_type}
                  {row.recipe_id ? ` · recipe #${row.recipe_id}` : ""}
                  {row.course_id ? ` · course #${row.course_id}` : ""}
                  {row.lesson_id ? ` · lesson #${row.lesson_id}` : ""}
                </span>
              ),
            },
            {
              key: "prompt",
              header: "เวอร์ชันพรอมป์ต",
              render: (row) => (
                <span className="font-mono text-xs text-fg-subtle">
                  {row.prompt_version}
                </span>
              ),
            },
            {
              key: "updated",
              header: "อัปเดตล่าสุด",
              render: (row) => (
                <span className="whitespace-nowrap text-xs text-fg-muted">
                  {relativeThai(row.updated_at)}
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
          title="การเฝ้าระวังผู้ช่วย AI ทั้งระบบ"
          what="ไม่มี endpoint สำหรับดูบทสนทนาของผู้ใช้คนอื่น ส่วนผู้ให้บริการ/โมเดล/โทเคน มีจริงแต่บันทึกไว้ราย “ข้อความ” จึงดูได้ในบทสนทนาที่เปิดเท่านั้น ไม่มีในตารางรายการ และไม่มีฟิลด์บอกสถานะความล้มเหลว"
          missing={[
            "GET /api/v1/admin/assistant/conversations/ (ข้ามผู้ใช้ พร้อมชื่อผู้ใช้)",
            "ฟิลด์สถานะความล้มเหลว / error state ในผลลัพธ์",
            "จำนวนข้อความและยอดโทเคนรวมในหน้ารายการ (ต้องเปิดดูรายตัว)",
            "operation สำหรับกลั่นกรองข้อความ (ตอนนี้บทสนทนาอ่านอย่างเดียว)",
          ]}
          workaround="กุญแจ API ของผู้ให้บริการอยู่ฝั่งเซิร์ฟเวอร์เท่านั้นและต้องอยู่อย่างนั้น  ไม่ควรถูกส่งมาที่หน้าเว็บไม่ว่ากรณีใด"
        />
      </div>

      <DetailPanel
        open={selected !== null}
        title={selected?.title || "บทสนทนา"}
        onClose={() => setSelected(null)}
      >
        {detail.loading ? (
          <p className="text-fg-muted">กำลังโหลด…</p>
        ) : detail.error ? (
          <ErrorState error={detail.error} onRetry={detail.refetch} />
        ) : selected ? (
          <>
            <dl>
              <DetailRow label="ภาษา">{selected.language}</DetailRow>
              <DetailRow label="บริบท">{selected.context_type}</DetailRow>
              <DetailRow label="เวอร์ชันพรอมป์ต">
                <span className="font-mono text-xs">
                  {selected.prompt_version}
                </span>
              </DetailRow>
              <DetailRow label="สร้างเมื่อ">
                {relativeThai(selected.created_at)}
              </DetailRow>
              <DetailRow label="ข้อความ (หน้านี้)">
                {messages.length} จากทั้งหมด {detail.data?.messages.count ?? 0}
              </DetailRow>
              <DetailRow label="โมเดลที่ใช้">
                {models.length ? models.join(", ") : ""}
              </DetailRow>
              <DetailRow label="โทเคน (เฉพาะหน้านี้)">
                <span className="font-mono text-xs">
                  เข้า {tokensIn} · ออก {tokensOut}
                </span>
              </DetailRow>
            </dl>
            <p className="mt-4 text-xs font-medium uppercase tracking-wide text-fg-subtle">
              บทสนทนา (อ่านอย่างเดียว)
            </p>
            <ol className="mt-1.5 space-y-2">
              {messages.map((message) => (
                <li
                  key={message.id}
                  className="rounded border border-edge px-2.5 py-2"
                >
                  <p className="flex flex-wrap gap-2 font-mono text-[11px] uppercase text-fg-subtle">
                    <span>{message.role}</span>
                    {message.provider ? <span>· {message.provider}</span> : null}
                    {message.model_name ? (
                      <span>· {message.model_name}</span>
                    ) : null}
                    {message.token_output !== null ? (
                      <span>· {message.token_output} tok</span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 whitespace-pre-wrap wrap-break-word">
                    {message.content}
                  </p>
                </li>
              ))}
            </ol>
          </>
        ) : null}
      </DetailPanel>
    </>
  );
}
