"use client";

/**
 * Recommendations — read-only inspection of the live engine.
 *
 * `/recommendations/recipes/` and `/recommendations/courses/` are
 * personalised to the caller, so what this page shows is what the engine
 * would serve *this admin account*. That is still genuinely useful: the
 * `reasons` array is the engine's own explanation, so an operator can
 * see which rules are firing.
 *
 * No score, rank, weight or per-user behavioural signal is displayed —
 * the API exposes none of them, and the behavioural inputs are private
 * by design.
 */

import { api, type Paginated } from "@/lib/api/client";
import type {
  CourseListItem,
  RecipeListItem,
  RecommendedCourse,
  RecommendedRecipe,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  UnavailablePanel,
} from "@/components/admin/primitives";

/** The engine embeds the content app's own card, typed loosely by the
 *  schema generator because it is a method field. */
const asRecipe = (item: RecommendedRecipe) =>
  item.recipe as unknown as RecipeListItem;
const asCourse = (item: RecommendedCourse) =>
  item.course as unknown as CourseListItem;

const REASON_LABELS: Record<string, string> = {
  matches_your_favorite_categories: "ตรงหมวดที่ผู้ใช้ชอบ",
  similar_to_your_favorites: "คล้ายรายการที่บันทึกไว้",
  from_a_creator_you_like: "จากผู้สร้างที่ผู้ใช้ติดตาม",
  similar_to_content_you_reviewed: "คล้ายเนื้อหาที่เคยรีวิว",
  matches_your_skill_level: "ตรงระดับฝีมือ",
  popular_right_now: "กำลังได้รับความนิยม",
  new_on_kawaiibake: "มาใหม่",
};

export default function AdminRecommendationsPage() {
  const recipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecommendedRecipe>>("/recommendations/recipes/", {
        query: { page_size: 15 },
        signal,
      }),
    [],
  );
  const courses = useApiQuery(
    (signal) =>
      api.get<Paginated<RecommendedCourse>>("/recommendations/courses/", {
        query: { page_size: 15 },
        signal,
      }),
    [],
  );

  return (
    <>
      <AdminPageHeader
        title="การแนะนำ"
        description="ตรวจสอบว่าเครื่องมือแนะนำกำลังเลือกอะไรและด้วยเหตุผลใด — ผลลัพธ์เป็นของบัญชีที่กำลังใช้งาน"
      />

      <div className="space-y-4">
        <AdminPanel
          title="สูตรที่ระบบแนะนำ"
          description="GET /recommendations/recipes/ — คอลัมน์ “เหตุผล” คือค่าที่ engine ส่งมาเอง"
        >
          {recipes.error ? (
            <div className="p-4">
              <ErrorState error={recipes.error} onRetry={recipes.refetch} />
            </div>
          ) : (
            <DataTable
              caption="สูตรที่ระบบแนะนำให้บัญชีนี้"
              loading={recipes.loading}
              rows={recipes.data?.results ?? []}
              rowKey={(row) => asRecipe(row).slug}
              empty={
                <AdminEmpty
                  title="ยังไม่มีผลการแนะนำ"
                  description="บัญชีนี้อาจยังไม่มีข้อมูลความชอบมากพอให้ engine ทำงาน"
                />
              }
              columns={[
                {
                  key: "title",
                  header: "สูตร",
                  render: (row) => (
                    <span className="line-clamp-1 font-medium">
                      {asRecipe(row).title}
                    </span>
                  ),
                },
                {
                  key: "author",
                  header: "ผู้เขียน",
                  render: (row) => (
                    <span className="text-fg-muted">
                      {asRecipe(row).author.username}
                    </span>
                  ),
                },
                {
                  key: "reasons",
                  header: "เหตุผลที่ถูกแนะนำ",
                  render: (row) => (
                    <span className="flex flex-wrap gap-1">
                      {row.reasons.map((reason) => (
                        <span
                          key={reason}
                          className="rounded bg-surface-sunken px-1.5 py-0.5 text-xs text-fg-muted"
                        >
                          {REASON_LABELS[reason] ?? reason}
                        </span>
                      ))}
                    </span>
                  ),
                },
              ]}
            />
          )}
        </AdminPanel>

        <AdminPanel
          title="คอร์สที่ระบบแนะนำ"
          description="GET /recommendations/courses/"
        >
          {courses.error ? (
            <div className="p-4">
              <ErrorState error={courses.error} onRetry={courses.refetch} />
            </div>
          ) : (
            <DataTable
              caption="คอร์สที่ระบบแนะนำให้บัญชีนี้"
              loading={courses.loading}
              rows={courses.data?.results ?? []}
              rowKey={(row) => asCourse(row).slug}
              empty={<AdminEmpty title="ยังไม่มีผลการแนะนำคอร์ส" />}
              columns={[
                {
                  key: "title",
                  header: "คอร์ส",
                  render: (row) => (
                    <span className="line-clamp-1 font-medium">
                      {asCourse(row).title}
                    </span>
                  ),
                },
                {
                  key: "instructor",
                  header: "ผู้สอน",
                  render: (row) => (
                    <span className="text-fg-muted">
                      {asCourse(row).instructor.username}
                    </span>
                  ),
                },
                {
                  key: "reasons",
                  header: "เหตุผลที่ถูกแนะนำ",
                  render: (row) => (
                    <span className="flex flex-wrap gap-1">
                      {row.reasons.map((reason) => (
                        <span
                          key={reason}
                          className="rounded bg-surface-sunken px-1.5 py-0.5 text-xs text-fg-muted"
                        >
                          {REASON_LABELS[reason] ?? reason}
                        </span>
                      ))}
                    </span>
                  ),
                },
              ]}
            />
          )}
        </AdminPanel>
      </div>

      <div className="mt-4">
        <UnavailablePanel
          title="ข้อมูลเชิงลึกของเครื่องมือแนะนำ"
          what="API ส่งมาเฉพาะรายการที่แนะนำกับ “เหตุผล” เท่านั้น ไม่มีคะแนน น้ำหนัก หรืออันดับดิบ และไม่มีมุมมองรวมทั้งแพลตฟอร์ม — ตัวเลขคะแนนที่ดูน่าเชื่อจึงไม่ถูกสร้างขึ้นเองในหน้านี้"
          missing={[
            "ค่า score / rank / weight ในผลลัพธ์",
            "GET /api/v1/admin/recommendations/stats/ (อัตราการคลิก, เนื้อหาที่ถูกแนะนำบ่อย)",
            "การทดสอบ engine ในนามผู้ใช้คนอื่น",
          ]}
          workaround="สัญญาณพฤติกรรมรายบุคคลที่ engine ใช้เป็นข้อมูลส่วนตัวที่ระบบตั้งใจไม่เปิดเผย — หน้านี้จึงแสดงเฉพาะเหตุผลที่ API ประกาศออกมาเอง"
        />
      </div>
    </>
  );
}
