import Link from "next/link";

import type { CourseListItem } from "@/lib/api/models";
import { Badge, DifficultyBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { MediaFrame } from "@/components/content/media-frame";

/**
 * Course discovery card - sibling of RecipeCard, and deliberately the
 * same skeleton: two badges on one line, title, a one-line meta strip
 * (lessons · category), a two-line summary that holds its height when
 * the field is blank, and the instructor pinned to the bottom with
 * `mt-auto` so every card in a row ends flush.
 */
export function CourseCard({ course }: { course: CourseListItem }) {
  const summary = course.summary?.trim();
  return (
    <Link
      href={`/courses/${course.slug}`}
      className="group block h-full rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Card className="flex h-full flex-col overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay">
        <div className="aspect-video w-full overflow-hidden">
          <MediaFrame src={course.thumbnail_url} seed={course.slug} />
        </div>
        <div className="flex flex-1 flex-col gap-2 p-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <DifficultyBadge level={course.difficulty} />
            {course.is_completed ? (
              <Badge tone="mint">เรียนจบแล้ว ✓</Badge>
            ) : course.is_enrolled ? (
              <Badge tone="butter">กำลังเรียน</Badge>
            ) : (
              <Badge tone="mint">ฟรี</Badge>
            )}
          </div>
          <h3 className="font-display line-clamp-2 font-medium text-fg group-hover:underline">
            {course.title}
          </h3>
          <p className="text-xs text-fg-subtle">
            {course.lesson_count} บทเรียน
            {course.categories[0] ? <> · {course.categories[0].name}</> : null}
          </p>
          {/* Blank summaries hold their two lines and say nothing: a
              missing field is the author's problem, not a message. */}
          <p className="line-clamp-2 min-h-10 text-sm text-fg-muted">
            {summary}
          </p>
          <p className="mt-auto truncate pt-1 text-xs text-fg-subtle">
            สอนโดย{" "}
            {course.instructor.display_name ||
              course.instructor.username ||
              "ไม่ระบุผู้สอน"}
          </p>
        </div>
      </Card>
    </Link>
  );
}
