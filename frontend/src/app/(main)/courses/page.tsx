"use client";

/**
 * Course discovery: a baking school, not a video marketplace.
 *
 * Search and every facet the API supports run **server-side**
 * (`?search=` + category/difficulty/instructor, ADR 0021) with the URL
 * as the single source of truth. Cards read the stored aggregates the
 * list payload now carries  total duration and rating  so nothing
 * here fans out per-course requests. The learning-status facet filters
 * the current page client-side over the real `is_enrolled` /
 * `is_completed` flags.
 */

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Category,
  CourseListItem,
  LessonSyllabusItem,
  MyCourseProgress,
  RecommendedCourse,
} from "@/lib/api/models";
import { REASON_LABELS } from "@/lib/recommendations";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { Avatar } from "@/components/ui/avatar";
import { Badge, DifficultyBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageBar } from "@/components/ui/page-bar";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Rating } from "@/components/ui/rating";
import { Skeleton } from "@/components/ui/skeleton";
import { Icon } from "@/components/ui/icon";
import { CategoryThumb } from "@/components/content/category-tile";
import { MediaFrame } from "@/components/content/media-frame";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 12;

/* Fluid card grid (same rule as the home page): rows stay straight with
   any item count instead of demanding "just enough" content. */
const FLUID_GRID =
  "grid gap-5 sm:grid-cols-[repeat(auto-fill,minmax(17.5rem,1fr))]";

const LEVELS = [
  {
    value: "beginner",
    icon: "sprout" as const,
    name: "เริ่มต้นได้เลย",
    detail: "ไม่ต้องมีพื้นฐาน  อุปกรณ์ การตวง และโดแรกของคุณ",
  },
  {
    value: "intermediate",
    icon: "croissant" as const,
    name: "ระดับกลาง",
    detail: "ต่อยอดจากพื้นฐาน  กลูเตน ครีม และการขึ้นรูป",
  },
  {
    value: "advanced",
    icon: "chef-hat" as const,
    name: "ขั้นสูง",
    detail: "งานละเอียดระดับร้าน  ลามิเนตและการตกแต่งขั้นสูง",
  },
] as const;

const STATUS_FILTERS = [
  { value: "not_started", label: "ยังไม่เริ่ม" },
  { value: "in_progress", label: "กำลังเรียน" },
  { value: "completed", label: "เรียนจบแล้ว" },
];

// Server-side orderings that actually exist on the API.
const SORTS = [
  { value: "newest", label: "มาใหม่" },
  { value: "title", label: "ตามชื่อ" },
  { value: "oldest", label: "เก่าสุด" },
];

/** "45 นาที" · "1 ชม. 20 นาที"  hidden entirely when the sum is 0. */
function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} นาที`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} ชม. ${rest} นาที` : `${hours} ชม.`;
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition-colors",
        "focus-visible:outline-2 focus-visible:outline-focus",
        // Selected = dark ink (see the recipes page): pink stays with
        // the primary CTAs so "on" and "do it" never look alike.
        active
          ? "bg-fg font-medium text-fg-inverted shadow-raised"
          : "border border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Course card built around learning value                             */
/* ------------------------------------------------------------------ */

function CourseLearningCard({
  course,
  progress,
  reasons,
  orientation = "vertical",
}: {
  course: CourseListItem;
  progress?: MyCourseProgress;
  /** Recommendation reasons - rendered inside the card so recommended
   *  and catalogue cards keep identical geometry. */
  reasons?: string[];
  /** `horizontal` (image left, content right) for a one-card shelf,
   *  where a lone grid cell would float in 70% empty space. */
  orientation?: "vertical" | "horizontal";
}) {
  const [curriculumOpen, setCurriculumOpen] = useState(false);
  const [lessons, setLessons] = useState<LessonSyllabusItem[] | null>(null);

  async function toggleCurriculum() {
    const next = !curriculumOpen;
    setCurriculumOpen(next);
    if (next && lessons === null) {
      try {
        setLessons(
          await api.get<LessonSyllabusItem[]>(`/courses/${course.slug}/lessons/`),
        );
      } catch {
        setLessons([]);
      }
    }
  }

  const cta = course.is_completed
    ? "ทบทวนคอร์ส"
    : course.is_enrolled
      ? "เรียนต่อ"
      : "เริ่มเรียนเลย";

  const horizontal = orientation === "horizontal";
  return (
    <Card
      className={cn(
        "flex h-full flex-col overflow-hidden transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-overlay",
        horizontal && "md:flex-row",
      )}
    >
      <Link
        href={`/courses/${course.slug}`}
        className={cn(
          "relative block aspect-video w-full overflow-hidden focus-visible:outline-2 focus-visible:outline-focus",
          horizontal && "md:w-2/5 md:self-stretch",
        )}
      >
        <div className={cn("size-full", horizontal && "md:absolute md:inset-0")}>
          <MediaFrame src={course.thumbnail_url} seed={course.slug} />
        </div>
        {course.is_completed ? (
          <span className="absolute right-3 top-3 rounded-full bg-success px-3 py-1 text-xs font-medium text-fg-inverted shadow-raised">
            <Icon tint name="ui/check" className="size-3.5" /> เรียนจบแล้ว
          </span>
        ) : null}
      </Link>
      <div
        className={cn(
          "flex flex-1 flex-col gap-2.5 p-4",
          horizontal && "md:justify-center",
        )}
      >
        {/* Two badges, one line, every card the same height - the rest
            of the facts live in the meta line under the title. */}
        <div className="flex flex-wrap items-center gap-1.5">
          <DifficultyBadge level={course.difficulty} />
          <Badge tone="mint">ฟรี</Badge>
        </div>
        <Link
          href={`/courses/${course.slug}`}
          className="focus-visible:outline-2 focus-visible:outline-focus"
        >
          <h3 className="font-display line-clamp-2 font-medium text-fg hover:text-accent-hover">
            {course.title}
          </h3>
        </Link>
        <p className="text-xs text-fg-subtle">
          {course.lesson_count} บทเรียน
          {course.total_duration_minutes > 0 ? (
            <> · {formatDuration(course.total_duration_minutes)}</>
          ) : null}
          {course.categories[0] ? <> · {course.categories[0].name}</> : null}
        </p>
        <p className="line-clamp-2 text-sm text-fg-muted">{course.summary}</p>
        {reasons?.length ? (
          <p className="flex flex-wrap gap-1.5">
            {reasons.slice(0, 2).map((reason) => (
              <Badge key={reason} tone="lavender">
                <Icon name="ui/sparkle" className="size-3.5" />{" "}
                {REASON_LABELS[reason] ?? reason}
              </Badge>
            ))}
          </p>
        ) : null}
        <p className="flex items-center gap-2 text-xs text-fg-subtle">
          <Avatar
            src={course.instructor.avatar_url}
            name={course.instructor.display_name || course.instructor.username}
            size="sm"
          />
          สอนโดย {course.instructor.display_name || course.instructor.username}
          {course.rating_average !== null && course.rating_count > 0 ? (
            <Rating
              average={course.rating_average}
              count={course.rating_count}
              className="ml-auto"
            />
          ) : null}
        </p>

        {progress && course.is_enrolled && !course.is_completed ? (
          <div>
            <p className="mb-1 text-xs text-fg-muted">
              เรียนแล้ว {progress.completed_lessons} จาก {progress.total_lessons}{" "}
              บทเรียน · {progress.percentage}%
            </p>
            <ProgressBar
              percent={progress.percentage}
              label={`ความคืบหน้า ${course.title}`}
            />
          </div>
        ) : null}

        <div className="mt-auto space-y-2 pt-1">
          {/* Always filled - the outline variant next to filled cards
              read as disabled; the completed state already shows on the
              cover badge. */}
          <Link href={`/courses/${course.slug}`} className="block">
            <Button size="sm" className="w-full">
              {cta}
            </Button>
          </Link>
          {/* The curriculum drawer belongs to the card: a hairline rule
              out to both edges ties it in instead of leaving it afloat
              under the button. */}
          <div className="-mx-4 space-y-2 border-t border-edge px-4 pt-1.5">
          <button
            type="button"
            aria-expanded={curriculumOpen}
            onClick={() => void toggleCurriculum()}
            className="flex w-full items-center justify-center gap-1 rounded-full py-1 text-xs text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            ดูบทเรียนในคอร์ส <span aria-hidden>{curriculumOpen ? "▲" : "▼"}</span>
          </button>
          {curriculumOpen ? (
            lessons === null ? (
              <Skeleton className="h-16 w-full" />
            ) : lessons.length === 0 ? (
              <p className="text-center text-xs text-fg-subtle">
                ยังไม่มีบทเรียนเผยแพร่
              </p>
            ) : (
              <ol className="space-y-1 rounded-control bg-surface-sunken/70 p-3 text-xs text-fg-muted">
                {lessons.slice(0, 4).map((lesson, index) => (
                  <li key={lesson.id} className="flex items-baseline gap-2">
                    <span className="shrink-0 font-medium text-fg-subtle">
                      {index + 1}.
                    </span>
                    <span className="min-w-0 flex-1 truncate text-fg">
                      {lesson.title}
                    </span>
                    {lesson.is_preview ? <Icon name="ui/eye" label="ดูตัวอย่างได้" className="size-3.5" /> : null}
                    {lesson.duration_minutes ? (
                      <span className="shrink-0">{lesson.duration_minutes} นาที</span>
                    ) : null}
                  </li>
                ))}
                {lessons.length > 4 ? (
                  <li className="pt-1 text-center">
                    <Link
                      href={`/courses/${course.slug}`}
                      className="text-accent underline"
                    >
                      ดูทั้งหมด {lessons.length} บทเรียน
                    </Link>
                  </li>
                ) : null}
              </ol>
            )
          ) : null}
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Featured course  richer metadata, still zero extra rating calls    */
/* ------------------------------------------------------------------ */

function FeaturedCourse({
  course,
  progress,
}: {
  course: CourseListItem;
  progress?: MyCourseProgress;
}) {
  const syllabus = useApiQuery(
    (signal) =>
      api.get<LessonSyllabusItem[]>(`/courses/${course.slug}/lessons/`, {
        signal,
      }),
    [course.slug],
  );
  const lessons = syllabus.data ?? [];
  const previewCount = lessons.filter((lesson) => lesson.is_preview).length;
  const cta = course.is_completed
    ? "ทบทวนคอร์ส"
    : course.is_enrolled
      ? "เรียนต่อจากที่ค้างไว้"
      : "เริ่มเรียนเลย";

  return (
    <Card className="overflow-hidden md:flex">
      {/* The cover is a locked 16:9 box at every breakpoint - the same
          ratio as every other course card (and the home featured card),
          so a huge upload can never inflate it and all covers line up.
          The absolute fill keeps it cover-cropped if the text column
          ever runs taller. */}
      <Link
        href={`/courses/${course.slug}`}
        className="relative block aspect-video w-full overflow-hidden focus-visible:outline-2 focus-visible:outline-focus md:w-1/2 md:self-stretch"
      >
        <div className="size-full md:absolute md:inset-0">
          <MediaFrame src={course.thumbnail_url} seed={course.slug} />
        </div>
      </Link>
      <div className="flex flex-col justify-center gap-1.5 px-6 py-5 md:w-1/2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="butter"><Icon name="ui/star" className="size-3.5" /> คอร์สแนะนำ</Badge>
          <DifficultyBadge level={course.difficulty} />
          <Badge tone="mint">ฟรี</Badge>
        </div>
        <h2 className="font-display text-xl font-medium text-fg sm:text-2xl">
          {course.title}
        </h2>
        <p className="line-clamp-2 text-sm text-fg-muted">{course.summary}</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-fg-muted">
          <span className="flex items-center gap-2">
            <Avatar
              src={course.instructor.avatar_url}
              name={course.instructor.display_name || course.instructor.username}
              size="sm"
            />
            {course.instructor.display_name || course.instructor.username}
          </span>
          {course.rating_average !== null && course.rating_count > 0 ? (
            <Rating average={course.rating_average} count={course.rating_count} />
          ) : null}
        </div>
        <p className="text-xs text-fg-subtle">
          <Icon name="ui/book" className="size-3.5" /> {course.lesson_count} บทเรียน
          {course.total_duration_minutes > 0 ? (
            <> · รวม {formatDuration(course.total_duration_minutes)}</>
          ) : null}
          {previewCount > 0 ? <> · ดูตัวอย่างได้ {previewCount} บท</> : null}
        </p>
        {/* Either the syllabus teaser (prospects) or the progress bar
            (enrolled) - never both, so the text column's height stays
            inside the cover's locked 16:9 box in both variants. */}
        {lessons.length > 0 &&
        !(progress && course.is_enrolled && !course.is_completed) ? (
          <ol className="space-y-1 rounded-control bg-surface-sunken/70 p-3 text-xs">
            {lessons.slice(0, 2).map((lesson, index) => (
              <li key={lesson.id} className="flex items-baseline gap-2 text-fg-muted">
                <span className="font-medium text-fg-subtle">{index + 1}.</span>
                <span className="min-w-0 flex-1 truncate text-fg">
                  {lesson.title}
                </span>
                {lesson.is_preview ? <Icon name="ui/eye" label="ดูตัวอย่างได้" className="size-3.5" /> : null}
              </li>
            ))}
            {lessons.length > 2 ? (
              <li className="text-center text-fg-subtle">
                …และอีก {lessons.length - 2} บทเรียน
              </li>
            ) : null}
          </ol>
        ) : null}
        {progress && course.is_enrolled && !course.is_completed ? (
          <div>
            <p className="mb-1 text-xs text-fg-muted">
              เรียนแล้ว {progress.completed_lessons}/{progress.total_lessons} ·{" "}
              {progress.percentage}%
            </p>
            <ProgressBar
              percent={progress.percentage}
              label={`ความคืบหน้า ${course.title}`}
            />
          </div>
        ) : null}
        <Link href={`/courses/${course.slug}`} className="mt-1 w-fit">
          <Button>{cta}</Button>
        </Link>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function CoursesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status } = useAuth();

  const search = searchParams.get("search") ?? "";
  const categoryParam = searchParams.get("category") ?? "";
  const difficultyParam = searchParams.get("difficulty") ?? "";
  const instructor = searchParams.get("instructor") ?? "";
  const statusFilter = searchParams.get("status") ?? "";
  const ordering = searchParams.get("ordering") ?? "";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const selectedCategories = categoryParam ? categoryParam.split(",") : [];
  const selectedDifficulties = difficultyParam ? difficultyParam.split(",") : [];
  const [sheetOpen, setSheetOpen] = useState(false);
  // Level tiles double as the level filter; activating one scrolls the
  // results into view so the click visibly does something.
  const catalogRef = useRef<HTMLHeadingElement>(null);
  const [searchInput, setSearchInput] = useState(search);
  const [seenSearch, setSeenSearch] = useState(search);
  if (seenSearch !== search) {
    setSeenSearch(search);
    setSearchInput(search);
  }

  // `router.replace` does not update `searchParams` until the next
  // render, so two quick filter clicks would both merge into the same
  // pre-click URL and the first selection would vanish. The pending copy
  // bridges that gap; the effect clears it once the URL catches up.
  const pendingQuery = useRef<string | null>(null);
  useEffect(() => {
    pendingQuery.current = null;
  }, [searchParams]);

  function setParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams(
      pendingQuery.current ?? searchParams.toString(),
    );
    for (const [key, value] of Object.entries(updates)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    if (!("page" in updates)) params.delete("page");
    const qs = params.toString();
    pendingQuery.current = qs;
    router.replace((qs ? `/courses?${qs}` : "/courses") as Route, {
      scroll: false,
    });
  }

  function toggleInList(_current: string[], value: string, key: string, max = 5) {
    // Membership from the freshest query (pending write included), never
    // the render snapshot - see setParams.
    const params = new URLSearchParams(
      pendingQuery.current ?? searchParams.toString(),
    );
    const live = params.get(key)?.split(",").filter(Boolean) ?? [];
    const next = live.includes(value)
      ? live.filter((item) => item !== value)
      : live.length < max
        ? [...live, value]
        : live;
    setParams({ [key]: next.join(",") || null });
  }

  // Debounced live search  the URL updates after the user pauses.
  useEffect(() => {
    const term = searchInput.trim();
    if (term === search) return;
    const handle = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      if (term) params.set("search", term);
      else params.delete("search");
      params.delete("page");
      const qs = params.toString();
      router.replace((qs ? `/courses?${qs}` : "/courses") as Route, {
        scroll: false,
      });
    }, 400);
    return () => clearTimeout(handle);
  }, [searchInput, search, router]);

  /* ---------------- Data ---------------- */

  const catalog = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: {
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          category: categoryParam || undefined,
          difficulty: difficultyParam || undefined,
          instructor: instructor || undefined,
          ordering: ordering || undefined,
        },
        signal,
      }),
    [page, search, categoryParam, difficultyParam, instructor, ordering, status],
  );
  // Small unfiltered peek: featured card, level counts, empty-state fallback.
  const overview = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: { page_size: 12 },
        signal,
      }),
    [status],
  );
  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );
  const progress = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<{ courses: MyCourseProgress[] }>("/me/progress/", { signal })
        : Promise.resolve({ courses: [] as MyCourseProgress[] }),
    [status],
  );
  const recommended = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<Paginated<RecommendedCourse>>("/recommendations/courses/", {
            query: { page_size: 3 },
            signal,
          })
        : Promise.resolve(null),
    [status],
  );

  const overviewRows = overview.data?.results ?? [];
  const progressBySlug = new Map(
    (progress.data?.courses ?? []).map((course) => [course.slug, course]),
  );
  const inProgress = (progress.data?.courses ?? [])
    .filter((course) => course.percentage < 100)
    .sort((a, b) => b.percentage - a.percentage);

  const levelCounts = new Map<string, number>();
  for (const course of overviewRows) {
    levelCounts.set(course.difficulty, (levelCounts.get(course.difficulty) ?? 0) + 1);
  }
  const courseCategorySlugs = new Set(
    overviewRows.flatMap((course) =>
      course.categories.map((category) => category.slug),
    ),
  );
  const courseCategories = (categories.data ?? []).filter((category) =>
    courseCategorySlugs.has(category.slug),
  );
  const instructors = [
    ...new Map(
      overviewRows.map((course) => [course.instructor.username, course.instructor]),
    ).values(),
  ];

  // Learning-status facet: client-side over the current page's real flags.
  const rows = (catalog.data?.results ?? []).filter((course) => {
    if (statusFilter === "not_started") return !course.is_enrolled;
    if (statusFilter === "in_progress") {
      return course.is_enrolled && !course.is_completed;
    }
    if (statusFilter === "completed") return course.is_completed;
    return true;
  });

  const activeFilterCount =
    selectedCategories.length +
    selectedDifficulties.length +
    (instructor ? 1 : 0) +
    (statusFilter ? 1 : 0);
  const filtered = Boolean(search || activeFilterCount);
  // A featured hero and a recommendation shelf only earn their place
  // over a catalogue big enough to scroll: below six courses everything
  // is already on screen, and the sections would just repeat the same
  // few cards two or three times down one page.
  const showcase = !filtered && (overview.data?.count ?? 0) >= 6;
  const featured = showcase && overviewRows.length > 0 ? overviewRows[0] : null;
  const recommendedItems = (recommended.data?.results ?? [])
    .filter((item) => item.course)
    .map((item) => ({ ...item, course: item.course as unknown as CourseListItem }))
    .filter((item) => !item.course.is_enrolled)
    // The hero already occupies the top of the page - never repeat it.
    .filter((item) => item.course.slug !== featured?.slug)
    .slice(0, 3);
  const totalPages = catalog.data
    ? Math.max(1, Math.ceil(catalog.data.count / PAGE_SIZE))
    : 1;

  const clearAll = () =>
    setParams({
      search: null,
      category: null,
      difficulty: null,
      instructor: null,
      status: null,
      ordering: null,
    });

  // ระดับ lives ONLY on the level tiles up top - repeating it here as
  // chips made the same filter exist twice on one page.
  const hasExtraFilters = status === "authenticated" || instructors.length > 1;
  const filterControls = (
    <>
      {status === "authenticated" ? (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="กรองตามสถานะการเรียน">
          <span className="text-xs font-medium text-fg-subtle">สถานะ:</span>
          {STATUS_FILTERS.map((item) => (
            <FilterChip
              key={item.value}
              active={statusFilter === item.value}
              onClick={() =>
                setParams({
                  status: statusFilter === item.value ? null : item.value,
                })
              }
            >
              {item.label}
            </FilterChip>
          ))}
        </div>
      ) : null}
      {instructors.length > 1 ? (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="กรองตามผู้สอน">
          <span className="text-xs font-medium text-fg-subtle">ผู้สอน:</span>
          {instructors.map((person) => (
            <FilterChip
              key={person.username}
              active={instructor === person.username}
              onClick={() =>
                setParams({
                  instructor:
                    instructor === person.username ? null : person.username,
                })
              }
            >
              {person.display_name || person.username}
            </FilterChip>
          ))}
        </div>
      ) : null}
    </>
  );

  return (
    <PageContainer>
      <PageHeader
        title="คอร์สเรียน"
        description={`เรียนเบเกอรี่เป็นลำดับขั้นจากครูตัวจริง ทั้งหมด ${overview.data?.count ?? "…"} คอร์ส พร้อมแบบทดสอบและใบประกาศนียบัตร`}
      />

      {/* Search: one field, icon inside, already live (debounced) - a
          separate submit button suggested typing alone does nothing. */}
      <form
        role="search"
        className="relative max-w-md"
        onSubmit={(event) => {
          event.preventDefault();
          setParams({ search: searchInput.trim() || null });
        }}
      >
        <Icon
          name="ui/search"
          className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
        />
        <Input
          type="search"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="ค้นหาคอร์ส เทคนิค หรือคำในบทเรียน…"
          aria-label="ค้นหาคอร์สเรียน"
          className="rounded-full pl-10 pr-10"
        />
        {searchInput ? (
          <button
            type="button"
            aria-label="ล้างคำค้น"
            onClick={() => {
              setSearchInput("");
              setParams({ search: null });
            }}
            className="absolute right-3 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded-full text-fg-subtle hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            <Icon name="ui/close" className="size-4" />
          </button>
        ) : null}
      </form>

      {/* Learning path */}
      <section className="mt-6" aria-label="เลือกระดับเริ่มต้น">
        <div className="grid gap-3 sm:grid-cols-3">
          {LEVELS.map((level) => {
            const active = selectedDifficulties.includes(level.value);
            const count = levelCounts.get(level.value) ?? 0;
            const empty = count === 0;
            return (
              <button
                key={level.value}
                type="button"
                aria-pressed={active}
                // An empty level is a dead end - the tile stays visible
                // as information but stops pretending to be a filter.
                disabled={empty}
                onClick={() => {
                  toggleInList(selectedDifficulties, level.value, "difficulty");
                  if (!active) {
                    catalogRef.current?.scrollIntoView({
                      behavior: "smooth",
                      block: "start",
                    });
                  }
                }}
                className={cn(
                  "rounded-surface p-4 text-left shadow-raised transition-[transform,box-shadow] duration-150",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                  level.value === "beginner" && "bg-mint-soft text-mint-ink",
                  level.value === "intermediate" && "bg-butter-soft text-butter-ink",
                  level.value === "advanced" && "bg-peach-soft text-peach-ink",
                  empty
                    ? "cursor-not-allowed opacity-45 shadow-none"
                    : "hover:-translate-y-0.5 hover:shadow-overlay",
                  active && "outline-2 outline-offset-2 outline-focus",
                )}
              >
                <p className="font-display font-medium">
                  <Icon name={`ui/${level.icon}`} className="size-3.5" /> {level.name}
                  <span className="ml-2 text-xs font-normal opacity-80">
                    {empty ? "เร็ว ๆ นี้" : `${count} คอร์ส`}
                  </span>
                </p>
                <p className="mt-1 text-xs opacity-90">{level.detail}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Featured course  hidden while filtering so results stay primary */}
      {featured ? (
        <section className="mt-8" aria-label="คอร์สแนะนำ">
          <FeaturedCourse
            course={featured}
            progress={progressBySlug.get(featured.slug)}
          />
        </section>
      ) : null}

      {/* Continue learning */}
      {!filtered && inProgress.length > 0 ? (
        <section className="mt-10" aria-label="เรียนต่อ">
          <h2 className="font-display mb-4 text-xl font-medium text-fg">
            เรียนต่อจากที่ค้างไว้
          </h2>
          <div className="flex snap-x gap-4 overflow-x-auto pb-2">
            {inProgress.map((course) => (
              <div
                key={course.slug}
                className="w-75 shrink-0 snap-start rounded-surface border border-lavender-ink/15 bg-lavender-soft/50 p-5 sm:w-85"
              >
                <h3 className="font-display line-clamp-1 font-medium text-fg">
                  {course.title}
                </h3>
                <p className="mt-1 text-sm text-fg-muted">
                  เรียนแล้ว {course.completed_lessons} จาก {course.total_lessons}{" "}
                  บทเรียน
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <ProgressBar
                    percent={course.percentage}
                    label={`ความคืบหน้า ${course.title}`}
                  />
                  <span className="shrink-0 text-sm font-medium text-lavender-ink">
                    {course.percentage}%
                  </span>
                </div>
                <Link href={`/courses/${course.slug}`} className="mt-4 block">
                  <Button size="sm" className="w-full">
                    เรียนต่อ
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {/* Recommended for your skill - only over a big catalogue (see
          `showcase`), never repeating the hero course. */}
      {showcase && recommendedItems.length > 0 ? (
        <section
          aria-label="คอร์สแนะนำสำหรับคุณ"
          className="mt-10 rounded-surface border border-berry-ink/10 bg-berry-soft/35 p-5 sm:p-6"
        >
          <h2 className="font-display mb-1 flex items-center gap-2 text-xl font-medium text-fg">
            <Icon name="ui/sparkle" className="size-5 text-berry-ink" />
            แนะนำตามระดับของคุณ
          </h2>
          <p className="mb-4 text-sm text-fg-muted">
            คัดจากระดับ หมวดที่ชอบ และคอร์สที่คุณเรียน
          </p>
          {recommendedItems.length === 1 ? (
            // A lone grid cell floats in empty space - one card lies
            // down instead (image left, content right).
            <CourseLearningCard
              orientation="horizontal"
              course={recommendedItems[0].course}
              progress={progressBySlug.get(recommendedItems[0].course.slug)}
              reasons={recommendedItems[0].reasons}
            />
          ) : (
            <div className={FLUID_GRID}>
              {recommendedItems.map((item) => (
                <CourseLearningCard
                  key={item.course.slug}
                  course={item.course}
                  progress={progressBySlug.get(item.course.slug)}
                  reasons={item.reasons}
                />
              ))}
            </div>
          )}
        </section>
      ) : null}

      {/* The catalog region starts here - a rule and its own heading keep
          the filters from visually belonging to the recommendation box. */}
      <hr aria-hidden className="mt-10 border-edge" />
      <h2
        ref={catalogRef}
        className="font-display mt-8 scroll-mt-24 text-xl font-medium text-fg"
      >
        คอร์สทั้งหมด
      </h2>

      {/* Categories relevant to courses */}
      {courseCategories.length > 0 ? (
        <div
          className="mt-4 flex snap-x gap-2.5 overflow-x-auto pb-2"
          role="group"
          aria-label="หมวดคอร์ส"
        >
          {courseCategories.map((category) => {
            const active = selectedCategories.includes(category.slug);
            return (
              <button
                key={category.slug}
                type="button"
                aria-pressed={active}
                onClick={() =>
                  toggleInList(selectedCategories, category.slug, "category")
                }
                className={cn(
                  "flex shrink-0 snap-start items-center gap-1.5 rounded-full px-4 py-2 text-sm transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-focus",
                  active
                    ? "bg-fg font-medium text-fg-inverted shadow-raised"
                    : "border border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
                )}
              >
                <CategoryThumb slug={category.slug} />
                {category.name}
              </button>
            );
          })}
        </div>
      ) : null}

      {/* Filters: inline (desktop) / bottom sheet (mobile). With ระดับ
          living on the tiles, anonymous visitors of a one-teacher school
          have no extra facets - so no empty filter UI either. */}
      {hasExtraFilters ? (
        <>
          <div className="mt-3 hidden space-y-2.5 lg:block">{filterControls}</div>
          <div className="mt-3 lg:hidden">
            <Button
              variant="secondary"
              size="sm"
              aria-expanded={sheetOpen}
              onClick={() => setSheetOpen(true)}
            >
              <Icon name="ui/sliders" className="size-4" /> ตัวกรอง{activeFilterCount ? ` (${activeFilterCount})` : ""}
            </Button>
          </div>
        </>
      ) : null}

      {/* Active filter summary */}
      {filtered ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-control bg-surface-sunken/70 px-3 py-2 text-sm">
          <span className="text-xs font-medium text-fg-subtle">กำลังกรอง:</span>
          {search ? (
            <FilterChip active onClick={() => setParams({ search: null })}>
              <>“{search}” <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ) : null}
          {selectedDifficulties.map((value) => (
            <FilterChip
              key={value}
              active
              onClick={() => toggleInList(selectedDifficulties, value, "difficulty")}
            >
              <>{LEVELS.find((level) => level.value === value)?.name ?? value} <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ))}
          {selectedCategories.map((slug) => (
            <FilterChip
              key={slug}
              active
              onClick={() => toggleInList(selectedCategories, slug, "category")}
            >
              {categories.data?.find((category) => category.slug === slug)?.name ??
                slug}
              <Icon name="ui/close" className="size-3" />
            </FilterChip>
          ))}
          {statusFilter ? (
            <FilterChip active onClick={() => setParams({ status: null })}>
              <>{STATUS_FILTERS.find((item) => item.value === statusFilter)?.label} <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ) : null}
          {instructor ? (
            <FilterChip active onClick={() => setParams({ instructor: null })}>
              <>ครู {instructor} <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ) : null}
          <button
            type="button"
            onClick={clearAll}
            className="ml-auto text-xs text-fg-subtle underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            ล้างทั้งหมด
          </button>
        </div>
      ) : null}

      {/* Results header - count and sort share one quiet bar instead of
          floating at opposite edges. */}
      <div className="mb-5 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-control bg-surface-sunken/60 px-4 py-2">
        <p className="text-sm text-fg-muted" aria-live="polite">
          {catalog.loading ? (
            "กำลังค้นหา…"
          ) : (
            <>
              พบ{" "}
              <strong className="text-fg">
                {statusFilter ? rows.length : (catalog.data?.count ?? 0)}
              </strong>{" "}
              คอร์ส
            </>
          )}
        </p>
        <label className="flex items-center gap-2 text-sm text-fg-muted">
          เรียงตาม
          <select
            value={ordering || "newest"}
            onChange={(event) =>
              setParams({
                ordering:
                  event.target.value === "newest" ? null : event.target.value,
              })
            }
            className="rounded-full border border-edge-strong/50 bg-surface px-3 py-1.5 text-sm text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            {SORTS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {catalog.loading ? (
        <div aria-busy="true" className={FLUID_GRID}>
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-96 w-full rounded-surface" />
          ))}
        </div>
      ) : catalog.error ? (
        <ErrorState error={catalog.error} onRetry={catalog.refetch} />
      ) : rows.length === 0 ? (
        <div className="space-y-8">
          <EmptyState
            icon={<Icon name="ui/graduation" className="size-8 text-fg-subtle" />}
            title={
              search
                ? `ไม่พบคอร์สที่ตรงกับ “${search}”`
                : "ไม่พบคอร์สตามเงื่อนไขที่เลือก"
            }
            description="ลองลดตัวกรอง หรือเริ่มจากระดับที่แนะนำ"
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="secondary" size="sm" onClick={clearAll}>
                  ล้างตัวกรองทั้งหมด
                </Button>
                {LEVELS.map((level) => (
                  <Button
                    key={level.value}
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setParams({ search: null, difficulty: level.value })
                    }
                  >
                    <Icon name={`ui/${level.icon}`} className="size-3.5" /> {level.name}
                  </Button>
                ))}
              </div>
            }
          />
          {overviewRows.length > 0 ? (
            <section>
              <h2 className="font-display mb-4 text-lg font-medium text-fg">
                คอร์สทั้งหมดที่เปิดสอนตอนนี้
              </h2>
              <div className={FLUID_GRID}>
                {overviewRows.slice(0, 3).map((course) => (
                  <CourseLearningCard
                    key={course.slug}
                    course={course}
                    progress={progressBySlug.get(course.slug)}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <>
          <div className={FLUID_GRID}>
            {rows.map((course) => (
              <CourseLearningCard
                key={course.slug}
                course={course}
                progress={progressBySlug.get(course.slug)}
              />
            ))}
          </div>
          <PageBar
            page={page}
            totalPages={totalPages}
            onPage={(next) => setParams({ page: next === 1 ? null : String(next) })}
            className="mt-8"
          />
        </>
      )}

      {/* Mobile filter sheet */}
      {sheetOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="ปิดตัวกรอง"
            onClick={() => setSheetOpen(false)}
            className="absolute inset-0 bg-fg/30"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="ตัวกรองคอร์ส"
            className="absolute inset-x-0 bottom-0 max-h-[80dvh] overflow-y-auto rounded-t-surface bg-surface p-5 shadow-overlay"
          >
            <div className="mb-4 flex items-center justify-between">
              <p className="font-display font-medium text-fg">
                ตัวกรอง{activeFilterCount ? ` (${activeFilterCount})` : ""}
              </p>
              <button
                type="button"
                onClick={clearAll}
                className="text-sm text-fg-subtle underline hover:text-fg"
              >
                ล้างทั้งหมด
              </button>
            </div>
            <div className="space-y-4">{filterControls}</div>
            <Button className="mt-5 w-full" size="lg" onClick={() => setSheetOpen(false)}>
              ดูผลลัพธ์ ({rows.length} คอร์ส)
            </Button>
          </div>
        </div>
      ) : null}
    </PageContainer>
  );
}

export default function CoursesPage() {
  return (
    <Suspense>
      <CoursesContent />
    </Suspense>
  );
}
