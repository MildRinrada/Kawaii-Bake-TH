"use client";

/**
 * Course management.
 *
 * `GET /courses/?scope=all` is the staff slice; publish / unpublish /
 * archive and DELETE are the writes the backend already exposes.
 *
 * Enrolment figures are deliberately absent: no endpoint reports how
 * many learners are enrolled in a course. `is_enrolled` on the list item
 * describes *the caller*, not the course, and would be a lie in an admin
 * table — see the note under the table.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { Category, CourseDetail, CourseListItem } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
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
  FilterBar,
  FilterSelect,
  Pagination,
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import {
  describeAdminError,
  runTransition,
  type Transition,
} from "@/components/admin/lifecycle";

const DIFFICULTIES = [
  { value: "", label: "ทุกระดับ" },
  { value: "beginner", label: "เริ่มต้น" },
  { value: "intermediate", label: "ปานกลาง" },
  { value: "advanced", label: "ขั้นสูง" },
];

const SCOPES = [
  { value: "all", label: "ทั้งหมด (staff)" },
  { value: "public", label: "เฉพาะที่เผยแพร่" },
];

const ORDERINGS = [
  { value: "newest", label: "ใหม่ล่าสุด" },
  { value: "oldest", label: "เก่าสุด" },
  { value: "title", label: "ชื่อ ก–ฮ" },
];

export default function AdminCoursesPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [difficulty, setDifficulty] = useState("");
  const [category, setCategory] = useState("");
  const [scope, setScope] = useState("all");
  const [ordering, setOrdering] = useState("newest");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const list = usePagedList<CourseListItem>("/courses/", {
    scope,
    ordering,
    search: search || undefined,
    difficulty: difficulty || undefined,
    category: category || undefined,
  });

  const detail = useApiQuery(
    (signal) =>
      selected
        ? api.get<CourseDetail>(`/courses/${selected}/`, { signal })
        : Promise.resolve(null),
    [selected],
  );

  async function transition(slug: string, action: Transition) {
    setBusy(true);
    try {
      await runTransition("/courses", slug, action);
      toast("อัปเดตสถานะคอร์สเรียบร้อย", "success");
      list.refetch();
      if (selected === slug) detail.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  async function destroy(slug: string, title: string) {
    try {
      await api.delete(`/courses/${slug}/`);
      toast(`ลบคอร์ส “${title}” แล้ว`, "success");
      setSelected(null);
      list.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="คอร์สเรียน"
        description="จัดการคอร์สทุกสถานะ พร้อมจำนวนบทเรียนและคะแนนรีวิวที่ระบบคำนวณไว้จริง"
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> คอร์ส
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาชื่อคอร์ส…"
            label="ค้นหาคอร์ส"
          />
          <FilterBar>
            <FilterSelect
              label="ขอบเขต"
              value={scope}
              options={SCOPES}
              onChange={setScope}
            />
            <FilterSelect
              label="ระดับ"
              value={difficulty}
              options={DIFFICULTIES}
              onChange={setDifficulty}
            />
            <FilterSelect
              label="หมวด"
              value={category}
              options={[
                { value: "", label: "ทุกหมวด" },
                ...(categories.data ?? []).map((item) => ({
                  value: item.slug,
                  label: item.name,
                })),
              ]}
              onChange={setCategory}
            />
            <FilterSelect
              label="เรียงตาม"
              value={ordering}
              options={ORDERINGS}
              onChange={setOrdering}
            />
          </FilterBar>
        </DataTableToolbar>

        <DataTable
          caption="รายการคอร์สทั้งหมด"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.slug}
          onRowClick={(row) => setSelected(row.slug)}
          empty={<AdminEmpty title="ไม่พบคอร์สที่ตรงกับเงื่อนไข" />}
          columns={[
            {
              key: "title",
              header: "ชื่อคอร์ส",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title}</p>
                  <p className="font-mono text-xs text-fg-subtle">{row.slug}</p>
                </div>
              ),
            },
            {
              key: "instructor",
              header: "ผู้สอน",
              render: (row) => (
                <span className="text-fg-muted">{row.instructor.username}</span>
              ),
            },
            {
              key: "lessons",
              header: "บทเรียน",
              numeric: true,
              render: (row) => row.lesson_count,
            },
            {
              key: "duration",
              header: "นาที",
              numeric: true,
              render: (row) => row.total_duration_minutes,
            },
            {
              key: "rating",
              header: "คะแนน",
              numeric: true,
              render: (row) =>
                row.rating_average !== null && row.rating_count > 0
                  ? `${row.rating_average.toFixed(1)} (${row.rating_count})`
                  : "—",
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => <StatusBadge status={row.status} />,
            },
            {
              key: "visibility",
              header: "การมองเห็น",
              render: (row) => <StatusBadge status={row.visibility} />,
            },
            {
              key: "created",
              header: "สร้างเมื่อ",
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

      <p className="mt-2 text-xs text-fg-muted">
        ไม่มีคอลัมน์ “จำนวนผู้เรียน” เพราะระบบหลังบ้านยังไม่มี endpoint
        นับผู้ลงทะเบียนต่อคอร์ส — ฟิลด์ <code className="font-mono">is_enrolled</code>{" "}
        ที่ API ส่งมาเป็นสถานะของ<em>ผู้เรียกเอง</em> ไม่ใช่ของคอร์ส
      </p>

      <DetailPanel
        open={selected !== null}
        title={detail.data?.title ?? "รายละเอียดคอร์ส"}
        onClose={() => setSelected(null)}
        footer={
          detail.data ? (
            <>
              {detail.data.status !== "published" ? (
                <Button
                  size="sm"
                  loading={busy}
                  onClick={() => transition(detail.data!.slug, "publish")}
                >
                  เผยแพร่
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy}
                  onClick={() => transition(detail.data!.slug, "unpublish")}
                >
                  ถอนกลับเป็นฉบับร่าง
                </Button>
              )}
              {detail.data.status !== "archived" ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    confirm.ask({
                      title: "เก็บคอร์สเข้าคลัง?",
                      body: `“${detail.data!.title}” จะหายจากหน้าเว็บสาธารณะ แต่ผู้ที่ลงทะเบียนไว้แล้วยังเข้าเรียนได้ และย้อนกลับได้`,
                      confirmLabel: "เก็บเข้าคลัง",
                      action: () => transition(detail.data!.slug, "archive"),
                    })
                  }
                >
                  เก็บเข้าคลัง
                </Button>
              ) : null}
              <Button
                size="sm"
                variant="danger"
                onClick={() =>
                  confirm.ask({
                    title: "ลบคอร์สนี้ถาวร?",
                    body: `“${detail.data!.title}” และบทเรียนทั้งหมดจะถูกลบถาวร กู้คืนไม่ได้ — ถ้าต้องการแค่ซ่อน ให้ใช้ “เก็บเข้าคลัง”`,
                    confirmLabel: "ลบถาวร",
                    danger: true,
                    action: () => destroy(detail.data!.slug, detail.data!.title),
                  })
                }
              >
                ลบถาวร
              </Button>
            </>
          ) : null
        }
      >
        {detail.loading ? (
          <p className="text-fg-muted">กำลังโหลด…</p>
        ) : detail.error ? (
          <ErrorState error={detail.error} onRetry={detail.refetch} />
        ) : detail.data ? (
          <dl>
            <DetailRow label="slug">
              <span className="font-mono text-xs">{detail.data.slug}</span>
            </DetailRow>
            <DetailRow label="ผู้สอน">
              {detail.data.instructor.display_name ||
                detail.data.instructor.username}
            </DetailRow>
            <DetailRow label="สถานะ">
              <StatusBadge status={detail.data.status} />
            </DetailRow>
            <DetailRow label="การมองเห็น">
              <StatusBadge status={detail.data.visibility} />
            </DetailRow>
            <DetailRow label="ระดับ">{detail.data.difficulty}</DetailRow>
            <DetailRow label="บทเรียนที่เผยแพร่">
              {detail.data.lesson_count}
            </DetailRow>
            <DetailRow label="หมวดหมู่">
              {detail.data.categories.map((item) => item.name).join(", ") || "—"}
            </DetailRow>
            <DetailRow label="สร้างเมื่อ">
              {relativeThai(detail.data.created_at)}
            </DetailRow>
            <DetailRow label="สรุป">
              <span className="text-fg-muted">{detail.data.summary || "—"}</span>
            </DetailRow>
          </dl>
        ) : null}
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}
