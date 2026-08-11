import Link from "next/link";

import type { CourseListItem } from "@/lib/api/models";
import { Badge, DifficultyBadge, flavorFor } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { MediaFrame } from "@/components/content/media-frame";

/** Course discovery card  sibling of RecipeCard, lavender-leaning. */
export function CourseCard({ course }: { course: CourseListItem }) {
  return (
    <Link
      href={`/courses/${course.slug}`}
      className="group block rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Card className="overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay">
        <div className="aspect-[4/3] w-full overflow-hidden">
          <MediaFrame src={course.thumbnail_url} seed={course.slug} />
        </div>
        <div className="space-y-2 p-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <DifficultyBadge level={course.difficulty} />
            <Badge tone="lavender">{course.lesson_count} บทเรียน</Badge>
            {course.is_completed ? (
              <Badge tone="mint">เรียนจบแล้ว ✓</Badge>
            ) : course.is_enrolled ? (
              <Badge tone="butter">กำลังเรียน</Badge>
            ) : null}
          </div>
          <h3 className="font-display line-clamp-2 font-medium text-fg group-hover:text-accent-hover">
            {course.title}
          </h3>
          <p className="line-clamp-2 text-sm text-fg-muted">{course.summary}</p>
          <p className="flex flex-wrap items-center gap-1.5 text-xs text-fg-subtle">
            <span>
              สอนโดย {course.instructor.display_name || course.instructor.username}
            </span>
            {course.categories.slice(0, 1).map((category) => (
              <Badge key={category.slug} tone={flavorFor(category.slug)}>
                {category.name}
              </Badge>
            ))}
          </p>
        </div>
      </Card>
    </Link>
  );
}
