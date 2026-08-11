"use client";

/**
 * Lesson management, scoped to one course.
 *
 * Lessons are addressed through their course everywhere in this API 
 * there is no flat `/lessons/` listing  so the course picker is not a
 * convenience, it is the only shape the backend supports.
 *
 * Writes used here all exist: `PATCH /lessons/{id}/` (status, preview
 * flag), `DELETE /lessons/{id}/`, and
 * `POST /courses/{slug}/lessons/reorder/` with the full id array, which
 * is exactly what the backend validates.
 *
 * Per-lesson completion statistics are not shown: `/courses/{slug}/
 * progress/` reports the *caller's* progress, not the cohort's.
 */

import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type { CourseListItem, LessonSyllabusItem } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  FilterSelect,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

export default function AdminLessonsPage() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [slug, setSlug] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const courses = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: { scope: "all", ordering: "title", page_size: 100 },
        signal,
      }),
    [],
  );

  const lessons = useApiQuery(
    (signal) =>
      slug
        ? api.get<LessonSyllabusItem[]>(`/courses/${slug}/lessons/`, { signal })
        : Promise.resolve(null),
    [slug],
  );

  const rows = lessons.data ?? [];
  const course = courses.data?.results.find((item) => item.slug === slug);

  async function patchLesson(id: number, body: Record<string, unknown>) {
    setBusyId(id);
    try {
      await api.patch(`/lessons/${id}/`, { body });
      toast("อัปเดตบทเรียนแล้ว", "success");
      lessons.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(lesson: LessonSyllabusItem) {
    try {
      await api.delete(`/lessons/${lesson.id}/`);
      toast(`ลบบทเรียน “${lesson.title}” แล้ว`, "success");
      lessons.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  /** Move one lesson and send the whole (validated) id array back. */
  async function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= rows.length) return;
    const ids = rows.map((row) => row.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    setBusyId(rows[index].id);
    try {
      await api.post(`/courses/${slug}/lessons/reorder/`, {
        body: { lesson_ids: ids },
      });
      toast("จัดลำดับบทเรียนใหม่แล้ว", "success");
      lessons.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <AdminPageHeader
        title="บทเรียน"
        description="เลือกคอร์สเพื่อดูและจัดการบทเรียนทั้งหมด รวมถึงบทที่ยังเป็นฉบับร่าง"
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            course ? (
              <span className="self-center text-xs text-fg-muted">
                สถานะคอร์ส: <StatusBadge status={course.status} />
              </span>
            ) : null
          }
        >
          <FilterSelect
            label="คอร์ส"
            value={slug}
            onChange={setSlug}
            options={[
              { value: "", label: " เลือกคอร์ส " },
              ...(courses.data?.results ?? []).map((item) => ({
                value: item.slug,
                label: `${item.title} (${item.lesson_count})`,
              })),
            ]}
          />
        </DataTableToolbar>

        {!slug ? (
          <AdminEmpty
            title="ยังไม่ได้เลือกคอร์ส"
            description="บทเรียนอยู่ภายใต้คอร์สเสมอ  เลือกคอร์สด้านบนเพื่อเริ่ม"
          />
        ) : lessons.error ? (
          <div className="p-4">
            <ErrorState error={lessons.error} onRetry={lessons.refetch} />
          </div>
        ) : (
          <DataTable
            caption="บทเรียนของคอร์สที่เลือก"
            loading={lessons.loading}
            rows={rows}
            rowKey={(row) => row.id}
            empty={<AdminEmpty title="คอร์สนี้ยังไม่มีบทเรียน" />}
            columns={[
              {
                key: "position",
                header: "ลำดับ",
                numeric: true,
                render: (row) => row.position + 1,
              },
              {
                key: "title",
                header: "ชื่อบทเรียน",
                render: (row) => (
                  <span className="line-clamp-1 font-medium">{row.title}</span>
                ),
              },
              {
                key: "duration",
                header: "นาที",
                numeric: true,
                render: (row) => row.duration_minutes,
              },
              {
                key: "video",
                header: "วิดีโอ",
                render: (row) => (
                  <span className="text-xs text-fg-muted">
                    {row.has_video ? "มี" : ""}
                  </span>
                ),
              },
              {
                key: "preview",
                header: "ตัวอย่างฟรี",
                render: (row) => (
                  <label className="flex items-center gap-1.5 text-xs text-fg-muted">
                    <input
                      type="checkbox"
                      checked={row.is_preview}
                      disabled={busyId === row.id}
                      onChange={(event) =>
                        patchLesson(row.id, { is_preview: event.target.checked })
                      }
                      className="size-4 accent-[var(--kb-accent)]"
                    />
                    {row.is_preview ? "เปิด" : "ปิด"}
                  </label>
                ),
              },
              {
                key: "status",
                header: "สถานะ",
                render: (row) => <StatusBadge status={row.status} />,
              },
              {
                key: "actions",
                header: "จัดการ",
                className: "w-px",
                render: (row) => {
                  const index = rows.findIndex((item) => item.id === row.id);
                  return (
                    <div className="flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`เลื่อน ${row.title} ขึ้น`}
                        disabled={index === 0 || busyId !== null}
                        onClick={() => move(index, -1)}
                      >
                        ↑
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`เลื่อน ${row.title} ลง`}
                        disabled={index === rows.length - 1 || busyId !== null}
                        onClick={() => move(index, 1)}
                      >
                        ↓
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={busyId === row.id}
                        onClick={() =>
                          patchLesson(row.id, {
                            status:
                              row.status === "published" ? "draft" : "published",
                          })
                        }
                      >
                        {row.status === "published" ? "ถอนออก" : "เผยแพร่"}
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() =>
                          confirm.ask({
                            title: "ลบบทเรียนนี้?",
                            body: `“${row.title}” จะถูกลบถาวร พร้อมกับความคืบหน้าของผู้เรียนในบทนี้`,
                            confirmLabel: "ลบบทเรียน",
                            danger: true,
                            action: () => remove(row),
                          })
                        }
                      >
                        ลบ
                      </Button>
                    </div>
                  );
                },
              },
            ]}
          />
        )}
      </AdminPanel>

      <p className="mt-2 text-xs text-fg-muted">
        ไม่มีคอลัมน์ “ผู้เรียนที่จบบทนี้” เพราะ{" "}
        <code className="font-mono">GET /courses/&#123;slug&#125;/progress/</code>{" "}
        รายงานความคืบหน้าของผู้เรียกเอง ไม่ใช่ของทั้งคอร์ส
      </p>

      {confirm.dialog}
    </>
  );
}
