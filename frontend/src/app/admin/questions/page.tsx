"use client";

/**
 * Quiz question bank.
 *
 * `GET /questions/?scope=all` is the staff-wide slice (a non-staff
 * caller only ever sees their own). `PATCH` and `DELETE /questions/{id}/`
 * are the writes staff may perform on anyone's question.
 *
 * Editing question text and choices is intentionally out of scope here:
 * the write payload is a nested choice structure, and a half-built
 * editor that can only save some of it would be worse than sending the
 * author back to the authoring UI.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { OwnerQuestion } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
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
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

export default function AdminQuestionsPage() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [selected, setSelected] = useState<OwnerQuestion | null>(null);

  const list = usePagedList<OwnerQuestion>("/questions/", {
    scope: "all",
    search: search || undefined,
  });

  async function remove(question: OwnerQuestion) {
    try {
      await api.delete(`/questions/${question.id}/`);
      toast("ลบคำถามแล้ว", "success");
      setSelected(null);
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
    <>
      <AdminPageHeader
        title="คลังคำถาม"
        description="คำถามทั้งหมดที่ใช้ประกอบแบบทดสอบ  ดูได้ทุกเจ้าของด้วยสิทธิ์ staff"
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> ข้อ
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาคำถาม…"
            label="ค้นหาคำถาม"
          />
        </DataTableToolbar>

        <DataTable
          caption="คลังคำถามทั้งหมด"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          onRowClick={setSelected}
          empty={<AdminEmpty title="ไม่พบคำถาม" />}
          columns={[
            {
              key: "text",
              header: "คำถาม",
              render: (row) => (
                <span className="line-clamp-2">{row.text}</span>
              ),
            },
            {
              key: "type",
              header: "ชนิด",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.question_type}
                </span>
              ),
            },
            {
              key: "choices",
              header: "ตัวเลือก",
              numeric: true,
              render: (row) => row.choices.length,
            },
            {
              key: "difficulty",
              header: "ระดับ",
              render: (row) => (
                <span className="text-xs text-fg-muted">{row.difficulty}</span>
              ),
            },
            {
              key: "frozen",
              header: "ล็อกแล้ว",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.is_frozen ? `v${row.version} · ล็อก` : `v${row.version}`}
                </span>
              ),
            },
            {
              key: "tags",
              header: "แท็ก",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.tags.map((tag) => tag.name).join(", ") || ""}
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

      <DetailPanel
        open={selected !== null}
        title="รายละเอียดคำถาม"
        onClose={() => setSelected(null)}
        footer={
          selected ? (
            <Button
              size="sm"
              variant="danger"
              onClick={() =>
                confirm.ask({
                  title: "ลบคำถามนี้?",
                  body: "คำถามจะถูกลบออกจากคลัง แบบทดสอบที่อ้างถึงจะไม่มีข้อนี้อีก",
                  confirmLabel: "ลบคำถาม",
                  danger: true,
                  action: () => remove(selected),
                })
              }
            >
              ลบคำถาม
            </Button>
          ) : null
        }
      >
        {selected ? (
          <>
            <dl>
              <DetailRow label="คำถาม">{selected.text}</DetailRow>
              <DetailRow label="ชนิด">{selected.question_type}</DetailRow>
              <DetailRow label="ระดับ">{selected.difficulty}</DetailRow>
              <DetailRow label="เวอร์ชัน">
                v{selected.version}
                {selected.is_frozen ? " · ล็อกแล้ว (แก้ไขไม่ได้)" : ""}
              </DetailRow>
              <DetailRow label="แท็ก">
                {selected.tags.map((tag) => tag.name).join(", ") || ""}
              </DetailRow>
              <DetailRow label="คำอธิบายเฉลย">
                {selected.explanation || ""}
              </DetailRow>
            </dl>
            <p className="mt-4 text-xs font-medium uppercase tracking-wide text-fg-subtle">
              ตัวเลือก
            </p>
            <ul className="mt-1.5 space-y-1">
              {selected.choices.map((choice) => (
                <li
                  key={choice.id}
                  className="flex items-start gap-2 rounded border border-edge px-2 py-1.5"
                >
                  <span
                    aria-label={choice.is_correct ? "ตัวเลือกที่ถูก" : "ตัวเลือกที่ผิด"}
                    className={
                      choice.is_correct
                        ? "text-success"
                        : "text-fg-subtle"
                    }
                  >
                    {choice.is_correct ? "✓" : "○"}
                  </span>
                  <span className="min-w-0 wrap-break-word">{choice.text}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}
