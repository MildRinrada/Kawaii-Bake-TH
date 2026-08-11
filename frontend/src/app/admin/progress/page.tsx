"use client";

/**
 * Platform-wide learning progress.
 *
 * Reads the staff-only `/admin/progress/` slice (ADR 0027/0028):
 * a platform summary, per-course completion stats, and  once a course
 * is selected  the paginated learner roster for that course. The
 * roster's "last activity" column is the drop-off signal: a learner
 * with no activity at all is the most likely abandonment point.
 */

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type {
  CourseStatRow,
  LearnerRow,
  ProgressSummary,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { cn } from "@/lib/cn";
import { Avatar } from "@/components/ui/avatar";
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
  StatCard,
} from "@/components/admin/primitives";

const ENROLLMENT_STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "active", label: "กำลังเรียน" },
  { value: "completed", label: "เรียนจบ" },
  { value: "dropped", label: "เลิกกลางทาง" },
];

/* ------------------------------------------------------------------ */
/* Local presentation helpers                                          */
/* ------------------------------------------------------------------ */

/** Percentage with a small horizontal bar  no chart library needed. */
function RateBar({ percent, label }: { percent: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-surface-sunken"
      >
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
        />
      </div>
      <span className="font-mono text-xs tabular-nums text-fg-muted">
        {percent}%
      </span>
    </div>
  );
}

/**
 * Enrollment-status chip. StatusBadge's shared vocabulary renders
 * `active` as "ใช้งาน" and gives `completed` the same green as
 * `active`, so the roster keeps its own three labels and tones.
 */
const LEARNER_STATUS: Record<string, { label: string; className: string }> = {
  active: { label: "กำลังเรียน", className: "bg-success-subtle text-success" },
  completed: { label: "เรียนจบ", className: "bg-lavender-soft text-lavender-ink" },
  dropped: { label: "เลิกกลางทาง", className: "bg-surface-sunken text-fg-muted" },
};

function LearnerStatusChip({ status }: { status: string }) {
  const meta = LEARNER_STATUS[status] ?? {
    label: status,
    className: "bg-surface-sunken text-fg-muted",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium",
        meta.className,
      )}
    >
      {/* A dot as well as colour: status must not be conveyed by hue alone. */}
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {meta.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Roster panel (one selected course)                                  */
/* ------------------------------------------------------------------ */

function CourseRosterPanel({
  course,
  onClose,
}: {
  course: CourseStatRow;
  onClose: () => void;
}) {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [status, setStatus] = useState("");
  const anchorRef = useRef<HTMLDivElement>(null);

  const list = usePagedList<LearnerRow>(
    `/admin/progress/courses/${encodeURIComponent(course.slug)}/enrollments/`,
    {
      // Unknown/empty query keys are a 400 on this API  omit them.
      status: status || undefined,
      search: search || undefined,
    },
  );

  // The panel appears below the fold of a long course table; bring it
  // into view on mount (the component is keyed by course slug, so a
  // new selection remounts and scrolls again).
  useEffect(() => {
    anchorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    // scroll-mt clears the sticky h-14 admin top bar.
    <div ref={anchorRef} className="mt-4 scroll-mt-20">
      <AdminPanel
        title={`ผู้เรียนใน ${course.title}`}
        description={`บทเรียนที่เผยแพร่ ${course.published_lesson_count} บท · ลงเรียน ${course.enrolled_count} คน`}
        actions={
          <Button size="sm" variant="secondary" onClick={onClose}>
            ✕ ปิด
          </Button>
        }
      >
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> คน
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาผู้เรียน…"
            label="ค้นหาผู้เรียน"
          />
          <FilterBar>
            <FilterSelect
              label="สถานะ"
              value={status}
              options={ENROLLMENT_STATUSES}
              onChange={setStatus}
            />
          </FilterBar>
        </DataTableToolbar>

        <p className="border-b border-edge px-3 py-2 text-xs text-fg-muted">
          ผู้เรียนที่ขึ้นว่า “ยังไม่เริ่มเรียน” คือจุดที่มีแนวโน้มหลุดกลางคันมากที่สุด
          ลงเรียนแล้วแต่ไม่มีกิจกรรมใดเลย
        </p>

        {list.error ? (
          <div className="p-4">
            <ErrorState error={list.error} onRetry={list.refetch} />
          </div>
        ) : (
          <>
            <DataTable
              caption={`รายชื่อผู้เรียนในคอร์ส ${course.title}`}
              loading={list.loading}
              rows={list.rows}
              rowKey={(row) => row.username}
              empty={
                <AdminEmpty
                  title="ไม่พบผู้เรียนที่ตรงกับเงื่อนไข"
                  description="ลองล้างคำค้นหรือเปลี่ยนตัวกรองสถานะ"
                />
              }
              columns={[
                {
                  key: "learner",
                  header: "ผู้เรียน",
                  render: (row) => (
                    <div className="flex min-w-0 items-center gap-2.5">
                      <Avatar
                        src={row.avatar_url}
                        name={row.display_name || row.username}
                        size="sm"
                      />
                      <div className="min-w-0">
                        <p className="line-clamp-1 font-medium">
                          {row.display_name || row.username}
                        </p>
                        <p className="font-mono text-xs text-fg-subtle">
                          @{row.username}
                        </p>
                      </div>
                    </div>
                  ),
                },
                {
                  key: "status",
                  header: "สถานะ",
                  render: (row) => <LearnerStatusChip status={row.status} />,
                },
                {
                  key: "progress",
                  header: "ความคืบหน้า",
                  render: (row) => (
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs tabular-nums text-fg-muted">
                        {row.completed_lessons}/{row.total_lessons}
                      </span>
                      <RateBar
                        percent={row.percent}
                        label={`ความคืบหน้าของ ${row.display_name || row.username}`}
                      />
                    </div>
                  ),
                },
                {
                  key: "enrolled",
                  header: "ลงเรียนเมื่อ",
                  render: (row) => (
                    <span className="whitespace-nowrap text-xs text-fg-muted">
                      {relativeThai(row.enrolled_at)}
                    </span>
                  ),
                },
                {
                  key: "activity",
                  header: "กิจกรรมล่าสุด",
                  render: (row) =>
                    row.last_activity_at ? (
                      <span className="whitespace-nowrap text-xs text-fg-muted">
                        {relativeThai(row.last_activity_at)}
                      </span>
                    ) : (
                      <span className="whitespace-nowrap text-xs font-medium text-warning">
                        ยังไม่เริ่มเรียน
                      </span>
                    ),
                },
                {
                  key: "completed",
                  header: "จบเมื่อ",
                  render: (row) => (
                    <span className="whitespace-nowrap text-xs text-fg-muted">
                      {row.completed_at ? relativeThai(row.completed_at) : "-"}
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
          </>
        )}
      </AdminPanel>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function AdminProgressPage() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [selected, setSelected] = useState<CourseStatRow | null>(null);

  const summary = useApiQuery(
    (signal) =>
      api.get<ProgressSummary>("/admin/progress/summary/", { signal }),
    [],
  );

  const courses = usePagedList<CourseStatRow>("/admin/progress/courses/", {
    search: search || undefined,
  });

  if (courses.error) {
    return <ErrorState error={courses.error} onRetry={courses.refetch} />;
  }

  const s = summary.data;
  // Overall completion share as a hint  only when there is a denominator.
  const completedShare =
    s && s.enrollments_total > 0
      ? `${Math.round((s.enrollments_completed / s.enrollments_total) * 100)}% ของการลงเรียนทั้งหมด`
      : undefined;

  return (
    <>
      <AdminPageHeader
        title="ความคืบหน้า"
        description="ภาพรวมการเรียนทั้งแพลตฟอร์ม  อัตราการเรียนจบรายคอร์ส และผู้เรียนรายคนพร้อมจุดที่หลุดกลางคัน"
      />

      {summary.error ? (
        <ErrorState error={summary.error} onRetry={summary.refetch} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="การลงเรียนทั้งหมด"
            value={s?.enrollments_total}
            hint="ทุกสถานะรวมกัน"
            loading={summary.loading}
          />
          <StatCard
            label="กำลังเรียน"
            value={s?.enrollments_active}
            loading={summary.loading}
          />
          <StatCard
            label="เรียนจบ"
            value={s?.enrollments_completed}
            hint={completedShare}
            loading={summary.loading}
          />
          <StatCard
            label="เลิกกลางทาง"
            value={s?.enrollments_dropped}
            loading={summary.loading}
          />
          <StatCard
            label="ผู้เรียนทั้งหมด"
            value={s?.learners}
            hint="นับคนไม่ซ้ำ"
            loading={summary.loading}
          />
          <StatCard
            label="บทเรียนที่ถูกทำจบ"
            value={s?.lessons_completed}
            hint="รวมทุกคอร์สทุกคน"
            loading={summary.loading}
          />
          <StatCard
            label="ผู้เรียน active ใน 7 วัน"
            value={s?.active_learners_7d}
            hint="มีกิจกรรมการเรียนใน 7 วันล่าสุด"
            loading={summary.loading}
          />
        </div>
      )}

      <AdminPanel
        className="mt-6"
        title="อัตราการเรียนจบรายคอร์ส"
        description="คลิกแถวเพื่อดูรายชื่อผู้เรียนของคอร์สนั้น"
      >
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{courses.count}</span>{" "}
              คอร์ส
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาชื่อคอร์ส…"
            label="ค้นหาคอร์ส"
          />
        </DataTableToolbar>

        <DataTable
          caption="สถิติการเรียนรายคอร์ส"
          loading={courses.loading}
          rows={courses.rows}
          rowKey={(row) => row.slug}
          onRowClick={(row) => setSelected(row)}
          empty={
            <AdminEmpty
              title="ไม่พบคอร์สที่ตรงกับเงื่อนไข"
              description="ลองล้างคำค้น"
            />
          }
          columns={[
            {
              key: "course",
              header: "คอร์ส",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title}</p>
                  <p className="font-mono text-xs text-fg-subtle">{row.slug}</p>
                </div>
              ),
            },
            {
              key: "lessons",
              header: "บทเรียน",
              numeric: true,
              render: (row) => row.published_lesson_count,
            },
            {
              key: "enrolled",
              header: "ลงเรียน",
              numeric: true,
              render: (row) => row.enrolled_count,
            },
            {
              key: "active",
              header: "กำลังเรียน",
              numeric: true,
              render: (row) => row.active_count,
            },
            {
              key: "completed",
              header: "จบ",
              numeric: true,
              render: (row) => row.completed_count,
            },
            {
              key: "dropped",
              header: "เลิกกลางทาง",
              numeric: true,
              render: (row) => row.dropped_count,
            },
            {
              key: "rate",
              header: "อัตราจบ",
              render: (row) => (
                <RateBar
                  percent={row.completion_rate}
                  label={`อัตราการเรียนจบของ ${row.title}`}
                />
              ),
            },
          ]}
        />

        <Pagination
          page={courses.page}
          pageSize={courses.pageSize}
          count={courses.count}
          onPage={courses.setPage}
        />
      </AdminPanel>

      {selected ? (
        // Keyed by slug: switching course resets the roster's search,
        // status filter and page, and re-triggers the scroll-into-view.
        <CourseRosterPanel
          key={selected.slug}
          course={selected}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </>
  );
}
