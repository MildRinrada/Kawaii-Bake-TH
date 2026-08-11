"use client";

/**
 * Platform overview.
 *
 * Every figure is a `count` read straight off a real paginated endpoint
 * (`page_size=1`, so the row payload is one item and the total is exact),
 * or the progress-admin summary. The one metric the API still cannot
 * answer  assistant usage  stays an explicit "no endpoint" card rather
 * than a zero.
 */

import Link from "next/link";

import { api, type Paginated } from "@/lib/api/client";
import type {
  AdminCertificate,
  AdminReview,
  AdminUser,
  Category,
  CourseListItem,
  GalleryPost,
  OwnerQuestion,
  ProgressSummary,
  QaThread,
  QuizListItem,
  RecipeListItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { relativeThai } from "@/lib/datetime";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  StatCard,
  StatusBadge,
} from "@/components/admin/primitives";

function useCount<T>(path: string, query: Record<string, string | number> = {}) {
  return useApiQuery<Paginated<T>>(
    (signal) =>
      api.get<Paginated<T>>(path, { query: { ...query, page_size: 1 }, signal }),
    [path, JSON.stringify(query)],
  );
}

export default function AdminDashboardPage() {
  const allRecipes = useCount<RecipeListItem>("/recipes/", { scope: "all" });
  const publicRecipes = useCount<RecipeListItem>("/recipes/");
  const allCourses = useCount<CourseListItem>("/courses/", { scope: "all" });
  const publicCourses = useCount<CourseListItem>("/courses/");
  const allQuizzes = useCount<QuizListItem>("/quizzes/", { scope: "all" });
  const questions = useCount<OwnerQuestion>("/questions/", { scope: "all" });
  const threads = useCount<QaThread>("/qa/threads/");
  const gallery = useCount<GalleryPost>("/gallery/");
  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );
  const users = useCount<AdminUser>("/admin/users/");
  const newUsers = useCount<AdminUser>("/admin/users/", { joined_days: 7 });
  const reviews = useCount<AdminReview>("/admin/reviews/");
  const certificates = useCount<AdminCertificate>("/admin/certificates/");
  const learning = useApiQuery(
    (signal) => api.get<ProgressSummary>("/admin/progress/summary/", { signal }),
    [],
  );

  const recentRecipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { scope: "all", ordering: "newest", page_size: 5 },
        signal,
      }),
    [],
  );
  const recentCourses = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: { scope: "all", ordering: "newest", page_size: 5 },
        signal,
      }),
    [],
  );
  const recentThreads = useApiQuery(
    (signal) =>
      api.get<Paginated<QaThread>>("/qa/threads/", {
        query: { page_size: 5 },
        signal,
      }),
    [],
  );

  const NO_ENDPOINT = "ยังไม่มี API";

  return (
    <>
      <AdminPageHeader
        title="แดชบอร์ด"
        description="ตัวเลขทั้งหมดอ่านจาก API จริง  ช่องที่ระบบหลังบ้านยังไม่มี endpoint จะบอกไว้ตรง ๆ ไม่ใส่เลขปลอม"
        actions={
          // Quick actions - only creations the backend really supports.
          <div className="flex flex-wrap gap-2">
            <Link href="/admin/recipes/new">
              <Button size="sm">+ สร้างสูตร</Button>
            </Link>
            <Link href="/admin/courses/new">
              <Button size="sm" variant="secondary">
                + สร้างคอร์ส
              </Button>
            </Link>
            <Link href="/admin/lessons">
              <Button size="sm" variant="secondary">
                จัดการบทเรียน
              </Button>
            </Link>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="สูตรทั้งหมด"
          value={allRecipes.data?.count}
          hint={`เผยแพร่แล้ว ${publicRecipes.data?.count ?? ""}`}
          loading={allRecipes.loading}
        />
        <StatCard
          label="คอร์สทั้งหมด"
          value={allCourses.data?.count}
          hint={`เผยแพร่แล้ว ${publicCourses.data?.count ?? ""}`}
          loading={allCourses.loading}
        />
        <StatCard
          label="แบบทดสอบ"
          value={allQuizzes.data?.count}
          loading={allQuizzes.loading}
        />
        <StatCard
          label="คลังคำถาม"
          value={questions.data?.count}
          loading={questions.loading}
        />
        <StatCard
          label="กระทู้ถาม-ตอบ"
          value={threads.data?.count}
          loading={threads.loading}
        />
        <StatCard
          label="โพสต์ในแกลเลอรี"
          value={gallery.data?.count}
          loading={gallery.loading}
        />
        <StatCard
          label="หมวดหมู่"
          value={categories.data?.length}
          loading={categories.loading}
        />
        <StatCard
          label="ผู้ใช้ทั้งหมด"
          value={users.data?.count}
          hint={`ใหม่ใน 7 วัน ${newUsers.data?.count ?? ""}`}
          loading={users.loading}
        />
        <StatCard
          label="การลงทะเบียนเรียน"
          value={learning.data?.enrollments_total}
          hint={`เรียนจบ ${learning.data?.enrollments_completed ?? ""}`}
          loading={learning.loading}
        />
        <StatCard
          label="รีวิวทั้งแพลตฟอร์ม"
          value={reviews.data?.count}
          loading={reviews.loading}
        />
        <StatCard
          label="ใบประกาศที่ออกแล้ว"
          value={certificates.data?.count}
          loading={certificates.loading}
        />
        <StatCard label="บทสนทนาผู้ช่วย AI" unavailable={NO_ENDPOINT} />
      </div>

      <p className="mt-2 text-xs text-fg-muted">
        การ์ดที่ระบุ “ยังไม่มี API” ต้องการ endpoint รวมยอดฝั่งเซิร์ฟเวอร์  ดูรายละเอียดในแต่ละหน้า
      </p>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <AdminPanel
          title="สูตรล่าสุด"
          actions={
            <Link
              href="/admin/recipes"
              className="text-xs text-accent hover:text-accent-hover"
            >
              จัดการสูตร →
            </Link>
          }
        >
          <DataTable
            minWidthClass="min-w-0"
            caption="สูตรที่สร้างล่าสุด"
            loading={recentRecipes.loading}
            rows={recentRecipes.data?.results ?? []}
            rowKey={(row) => row.slug}
            empty={<AdminEmpty title="ยังไม่มีสูตรในระบบ" />}
            columns={[
              {
                key: "title",
                header: "ชื่อสูตร",
                render: (row) => (
                  <span className="line-clamp-1">{row.title}</span>
                ),
              },
              {
                key: "author",
                header: "ผู้เขียน",
                render: (row) => (
                  <span className="text-fg-muted">{row.author.username}</span>
                ),
              },
              {
                key: "status",
                header: "สถานะ",
                render: (row) => <StatusBadge status={row.status} />,
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
        </AdminPanel>

        <AdminPanel
          title="คอร์สล่าสุด"
          actions={
            <Link
              href="/admin/courses"
              className="text-xs text-accent hover:text-accent-hover"
            >
              จัดการคอร์ส →
            </Link>
          }
        >
          <DataTable
            minWidthClass="min-w-0"
            caption="คอร์สที่สร้างล่าสุด"
            loading={recentCourses.loading}
            rows={recentCourses.data?.results ?? []}
            rowKey={(row) => row.slug}
            empty={<AdminEmpty title="ยังไม่มีคอร์สในระบบ" />}
            columns={[
              {
                key: "title",
                header: "ชื่อคอร์ส",
                render: (row) => (
                  <span className="line-clamp-1">{row.title}</span>
                ),
              },
              {
                key: "instructor",
                header: "ผู้สอน",
                render: (row) => (
                  <span className="text-fg-muted">
                    {row.instructor.username}
                  </span>
                ),
              },
              {
                key: "lessons",
                header: "บทเรียน",
                numeric: true,
                render: (row) => row.lesson_count,
              },
              {
                key: "status",
                header: "สถานะ",
                render: (row) => <StatusBadge status={row.status} />,
              },
            ]}
          />
        </AdminPanel>

        <AdminPanel
          title="คำถามจากชุมชนล่าสุด"
          actions={
            <Link
              href="/admin/reviews"
              className="text-xs text-accent hover:text-accent-hover"
            >
              ไปหน้ากลั่นกรอง →
            </Link>
          }
          className="xl:col-span-2"
        >
          <DataTable
            minWidthClass="min-w-0"
            caption="กระทู้ถาม-ตอบล่าสุด"
            loading={recentThreads.loading}
            rows={recentThreads.data?.results ?? []}
            rowKey={(row) => row.id}
            empty={<AdminEmpty title="ยังไม่มีกระทู้" />}
            columns={[
              {
                key: "title",
                header: "หัวข้อ",
                render: (row) => (
                  <span className="line-clamp-1">{row.title}</span>
                ),
              },
              {
                key: "author",
                header: "ผู้ถาม",
                render: (row) => (
                  <span className="text-fg-muted">{row.author_handle}</span>
                ),
              },
              {
                key: "status",
                header: "สถานะ",
                render: (row) => <StatusBadge status={row.status} />,
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
        </AdminPanel>
      </div>
    </>
  );
}
