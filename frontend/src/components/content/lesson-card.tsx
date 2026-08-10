import Link from "next/link";

import type { components } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

type SyllabusItem = components["schemas"]["LessonSyllabusItem"] & {
  completed?: boolean | null;
};

/**
 * Syllabus row: position dish, title, duration, preview/completed marks.
 * Rendered as a link when the viewer may open the lesson.
 */
export function LessonCard({
  lesson,
  index,
  completed,
}: {
  lesson: SyllabusItem;
  index: number;
  completed?: boolean;
}) {
  const inner = (
    <div
      className={cn(
        "flex items-center gap-4 rounded-control border border-edge bg-surface px-4 py-3",
        "transition-colors hover:border-accent/40 hover:bg-accent-subtle/40",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "flex size-13 shrink-0 items-center justify-center rounded-full font-display text-sm font-medium",
          completed ? "bg-mint-soft text-mint-ink" : "bg-lavender-soft text-lavender-ink",
        )}
      >
        {completed ? "✓" : index}
      </span>
      <span className="min-w-0 flex-1">
        <span className="font-display block truncate font-medium text-fg">
          {lesson.title}
        </span>
        <span className="mt-0.5 flex items-center gap-2 text-xs text-fg-subtle">
          {lesson.duration_minutes ? <span>⏱ {lesson.duration_minutes} นาที</span> : null}
          {lesson.has_video ? <span>🎬 มีวิดีโอ</span> : null}
        </span>
      </span>
      {lesson.is_preview ? <Badge tone="butter">ดูตัวอย่างได้</Badge> : null}
    </div>
  );

  return (
    <Link
      href={`/learn/${lesson.id}`}
      className="block rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      {inner}
    </Link>
  );
}
