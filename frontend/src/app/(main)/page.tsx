"use client";

/**
 * Home: a learning-platform front page, not a recipe blog.
 *
 * Hierarchy (deliberate, not equal-weight): hero with search + start
 * CTA → continue-learning strip for returning students → skill-level
 * discovery → featured course → recommendation feed → recipe grid →
 * category explorer → community preview. Every section renders real
 * API data; secondary sections disappear quietly when they have
 * nothing to show instead of stacking empty states.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Route } from "next";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Category,
  CourseListItem,
  GalleryPost,
  MyCourseProgress,
  QaThread,
  RecipeListItem,
  RecommendedRecipe,
} from "@/lib/api/models";
import { BANNER } from "@/lib/assets";
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
import { PageContainer } from "@/components/ui/page-container";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Skeleton } from "@/components/ui/skeleton";
import { ArtIcon, Icon } from "@/components/ui/icon";
import { CategoryTile } from "@/components/content/category-tile";
import { CourseCard } from "@/components/content/course-card";
import { MediaFrame } from "@/components/content/media-frame";
import { RecipeCard } from "@/components/content/recipe-card";
import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ */
/* Shared section chrome                                              */
/* ------------------------------------------------------------------ */

function Section({
  title,
  description,
  href,
  hrefLabel = "ดูทั้งหมด →",
  action,
  children,
  className,
}: {
  title: string;
  description?: string;
  href?: Route;
  hrefLabel?: string;
  /** A section-owned CTA, on the heading row beside the "see all" link
      rather than stacked in a band of its own above the grid. */
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("mt-14", className)}>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="font-display text-xl font-medium text-fg sm:text-2xl">
            {title}
          </h2>
          {description ? (
            <p className="mt-1 text-sm text-fg-muted">{description}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {action}
          {href ? (
            // Quiet by design: pink is reserved for the page's primary
            // CTAs, so navigation links stay in the neutral ink.
            <Link
              href={href}
              className="rounded-full px-3 py-1 text-sm font-medium text-fg-muted hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
            >
              {hrefLabel}
            </Link>
          ) : null}
        </div>
      </div>
      {children}
    </section>
  );
}

/* Card grids flow with the data instead of demanding an exact count:
   `auto-fill, minmax(17.5rem, 1fr)` keeps rows straight with 2 items or
   12, so no section ever needs "just enough" content to look right. */
const FLUID_GRID = "grid gap-5 sm:grid-cols-[repeat(auto-fill,minmax(17.5rem,1fr))]";

function CardGridSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div aria-busy="true" className={FLUID_GRID}>
      {Array.from({ length: count }, (_, index) => (
        <Skeleton key={index} className="h-72 w-full rounded-surface" />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                               */
/* ------------------------------------------------------------------ */

/* The banner is one wide illustration from `public/banners/`, anchored
   right so it never sits under the headline, and purely decorative  the
   hero's words stay real HTML for search engines and screen readers. */

function Hero() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function onSearch(event: React.FormEvent) {
    event.preventDefault();
    const q = query.trim();
    router.push(
      (q ? `/recipes?search=${encodeURIComponent(q)}` : "/recipes") as Route,
    );
  }

  return (
    <div className="kb-hero relative overflow-hidden border-b border-edge">
      {/* Oversized past the top/bottom so the float bob never exposes a
          gap, and left-masked so the photo fades into the hero gradient
          instead of meeting it at a hard seam. */}
      <ArtIcon
        src={BANNER.home}
        className="kb-float pointer-events-none absolute -top-4 right-0 hidden h-[calc(100%+2rem)] w-[58%] object-cover object-right lg:block mask-[linear-gradient(to_right,transparent,black_28%)]"
      />
      {/* Scrim under the copy: whatever artwork the banner ships, the
          headline keeps its contrast. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 hidden w-3/5 bg-gradient-to-r from-canvas/90 via-canvas/50 to-transparent lg:block"
      />
      <PageContainer className="relative py-14 sm:py-20">
        <div className="max-w-2xl">
          <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-surface/70 px-4 py-1.5 text-sm text-fg-muted shadow-raised">
            แพลตฟอร์มเรียนทำเบเกอรี่ภาษาไทย
          </p>
          <h1 className="font-display text-3xl font-medium leading-snug text-fg sm:text-5xl sm:leading-snug">
            อบขนมให้อร่อย
            <br />
            เรียนรู้ได้ทุกวัน <span className="text-accent">ทีละขั้นตอน</span>
          </h1>
          <p className="mt-4 max-w-lg text-fg-muted">
            เรียนกับผู้สอนตัวจริง พร้อมสูตรและวิธีทำแบบละเอียด แบบทดสอบ
            ใบประกาศนียบัตร และผู้ช่วย AI ที่ช่วยตอบคำถามเรื่องการอบขนมเป็นภาษาไทย
          </p>
          {/* One primary CTA; recipe browsing demotes to a quiet link so
              the two never compete for the same click. */}
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link href="/courses">
              <Button size="lg">
                เริ่มเรียนเลย
              </Button>
            </Link>
            <Link
              href="/recipes"
              className="rounded-full px-3 py-2.5 text-sm font-medium text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
            >
              สำรวจสูตรขนม →
            </Link>
          </div>
          <form
            role="search"
            onSubmit={onSearch}
            className="mt-6 flex w-full max-w-md gap-2"
          >
            <Input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="ค้นหาสูตร เทคนิค หรือวัตถุดิบ เช่น ครัวซองต์…"
              aria-label="ค้นหาสูตรขนมและเทคนิค"
              className="rounded-full bg-surface/90"
            />
            <Button type="submit" variant="secondary" aria-label="ค้นหา">
              <Icon name="ui/search" />
            </Button>
          </form>
        </div>
      </PageContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Continue learning (returning students)                             */
/* ------------------------------------------------------------------ */

function ContinueLearning() {
  const { status } = useAuth();
  const progress = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<{ courses: MyCourseProgress[] }>("/me/progress/", { signal })
        : Promise.resolve({ courses: [] as MyCourseProgress[] }),
    [status],
  );

  const courses = progress.data?.courses ?? [];
  if (status !== "authenticated" || progress.loading || courses.length === 0) {
    return null;
  }

  return (
    <Section
      title="เรียนต่อจากที่ค้างไว้"
      description="กลับเข้าบทเรียนล่าสุดของคุณได้เลย"
    >
      <div className="flex snap-x gap-4 overflow-x-auto pb-2">
        {courses.slice(0, 6).map((course) => (
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
                {course.completed_at ? "ทบทวนคอร์ส" : "เรียนต่อ"}
              </Button>
            </Link>
          </div>
        ))}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ */
/* Skill-level discovery                                              */
/* ------------------------------------------------------------------ */

const SKILL_LEVELS = [
  {
    difficulty: "beginner",
    icon: "sprout" as const,
    name: "เริ่มต้นได้เลย",
    description: "ยังไม่เคยอบก็เริ่มได้  อุปกรณ์ วัตถุดิบ และสูตรแรกที่สำเร็จแน่",
    tone: "mint" as const,
  },
  {
    difficulty: "intermediate",
    icon: "croissant" as const,
    name: "ระดับกลาง",
    description: "อบเป็นแล้ว อยากไปต่อ  เทคนิคแป้ง ครีม และการขึ้นรูป",
    tone: "butter" as const,
  },
  {
    difficulty: "advanced",
    icon: "chef-hat" as const,
    name: "ขั้นสูง",
    description: "เก็บรายละเอียดระดับร้าน  งานตกแต่งและสูตรที่ท้าทาย",
    tone: "peach" as const,
  },
] as const;

function SkillLevels() {
  return (
    <Section
      title="เริ่มจากระดับไหนดี?"
      description="เลือกตามประสบการณ์ แล้วเราจะพาไปคอร์สที่พอดีกับคุณ"
    >
      <div className="grid gap-4 sm:grid-cols-3">
        {SKILL_LEVELS.map((level) => (
          <Link
            key={level.difficulty}
            href={`/courses?difficulty=${level.difficulty}` as Route}
            className={cn(
              "group rounded-surface border border-edge bg-surface p-6 shadow-raised transition-[transform,box-shadow] duration-150",
              "hover:-translate-y-0.5 hover:shadow-overlay",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
            )}
          >
            {/* One surface for all three. Green/amber/red panels read as
                success/warning/error, which is a different meaning
                entirely; the level is what the icon and badge say. */}
            <div className="flex items-center gap-3">
              <Icon name={`ui/${level.icon}`} className="size-8" />
              <DifficultyBadge level={level.difficulty} />
            </div>
            <h3 className="font-display mt-3 text-lg font-medium text-fg">
              {level.name}
            </h3>
            <p className="mt-1 text-sm text-fg-muted">{level.description}</p>
            <p className="mt-4 text-sm font-medium text-fg-muted">
              ดูคอร์สระดับนี้{" "}
              <span
                aria-hidden
                className="inline-block transition-transform group-hover:translate-x-1"
              >
                →
              </span>
            </p>
          </Link>
        ))}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ */
/* Featured courses                                                   */
/* ------------------------------------------------------------------ */

function FeaturedCourses() {
  const courses = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: { page_size: 4 },
        signal,
      }),
    [],
  );

  return (
    <Section
      title="คอร์สเด่นประจำสัปดาห์"
      description="คอร์สล่าสุดจากครูเบเกอรี่ตัวจริง"
      href="/courses"
    >
      {courses.loading ? (
        <Skeleton className="h-72 w-full rounded-surface" />
      ) : courses.error ? (
        <ErrorState error={courses.error} onRetry={courses.refetch} />
      ) : !courses.data || courses.data.results.length === 0 ? (
        <EmptyState icon={<Icon name="ui/graduation" className="size-8 text-fg-subtle" />} title="ยังไม่มีคอร์สเรียน" description="คอร์สแรกกำลังจะเปิดเร็ว ๆ นี้" />
      ) : courses.data.results.length < 4 ? (
        // Too few courses to earn a hero slot - a plain fluid grid
        // never leaves a lonely featured card over an empty row.
        <div className={FLUID_GRID}>
          {courses.data.results.map((course) => (
            <CourseCard key={course.slug} course={course} />
          ))}
        </div>
      ) : (
        <div className="space-y-5">
          <FeaturedCourseCard course={courses.data.results[0]} />
          <div className="flex snap-x gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-[repeat(auto-fill,minmax(17.5rem,1fr))] sm:overflow-visible sm:pb-0">
            {courses.data.results.slice(1).map((course) => (
              <div key={course.slug} className="w-70 shrink-0 snap-start sm:w-auto">
                <CourseCard course={course} />
              </div>
            ))}
          </div>
        </div>
      )}
    </Section>
  );
}

function FeaturedCourseCard({ course }: { course: CourseListItem }) {
  return (
    <Link
      href={`/courses/${course.slug}`}
      className="group block rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Card className="overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay md:flex">
        {/* The cover is a locked 16:9 box at every breakpoint - the same
            ratio as every other course card (and the /courses featured
            card), so a huge upload can never inflate it and all covers
            line up. The absolute fill keeps it cover-cropped if the text
            column ever runs taller. */}
        <div className="relative aspect-video w-full overflow-hidden md:w-1/2 md:self-stretch">
          <div className="size-full md:absolute md:inset-0">
            <MediaFrame src={course.thumbnail_url} seed={course.slug} />
          </div>
        </div>
        <div className="flex flex-col justify-center gap-3 p-6 md:w-1/2 md:p-8">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone="butter"><Icon name="ui/star" className="size-3.5" /> คอร์สแนะนำ</Badge>
            <DifficultyBadge level={course.difficulty} />
            {course.is_enrolled ? <Badge tone="mint">ลงเรียนแล้ว</Badge> : null}
          </div>
          <h3 className="font-display text-xl font-medium text-fg group-hover:text-accent-hover sm:text-2xl">
            {course.title}
          </h3>
          <p className="line-clamp-3 text-sm text-fg-muted">{course.summary}</p>
          <p className="text-xs text-fg-subtle">
            {course.lesson_count} บทเรียน · โดย{" "}
            {course.instructor.display_name || course.instructor.username}
          </p>
          <span className="mt-1 inline-flex w-fit items-center rounded-full bg-accent px-5 py-2 text-sm font-medium text-fg-inverted shadow-raised transition-colors group-hover:bg-accent-hover">
            ดูรายละเอียดคอร์ส
          </span>
        </div>
      </Card>
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/* Recommendation feed (trending for anonymous, personal for members) */
/* ------------------------------------------------------------------ */

function RecommendationFeed({
  onShown,
}: {
  /** The slugs this section rendered, so later sections can skip them. */
  onShown: (slugs: string[]) => void;
}) {
  const { status } = useAuth();
  const feed = useApiQuery(
    (signal) =>
      api.get<Paginated<RecommendedRecipe>>("/recommendations/recipes/", {
        query: { page_size: 3 },
        signal,
      }),
    [status],
  );

  const items = (feed.data?.results ?? []).filter((item) => item.recipe);
  // A string, not the array: the effect should fire on content, not on
  // every new array identity.
  const shown = items.map((item) => item.recipe!.slug).join(",");
  useEffect(() => {
    onShown(shown ? shown.split(",") : []);
  }, [shown, onShown]);

  if (feed.error || (!feed.loading && items.length === 0)) return null;

  const authenticated = status === "authenticated";
  return (
    <Section
      title={authenticated ? "แนะนำสำหรับคุณ" : "กำลังเป็นที่นิยม"}
      description={
        authenticated
          ? "คัดจากหมวดที่คุณชอบ ของที่บันทึก และคอร์สที่เรียน"
          : "จัดอันดับจากคะแนนรีวิวและรายการโปรดจริงของผู้ใช้"
      }
      href="/recommendations"
    >
      {feed.loading ? (
        <CardGridSkeleton />
      ) : (
        <div className={FLUID_GRID}>
          {items.map((item, index) => (
            <div key={index}>
              <RecipeCard recipe={item.recipe as unknown as RecipeListItem} />
              {item.reasons.length ? (
                <p className="mt-2 flex flex-wrap gap-1.5">
                  {item.reasons.slice(0, 2).map((reason) => (
                    <Badge key={reason} tone="lavender">
                      <Icon name="ui/sparkle" className="size-3.5" /> {REASON_LABELS[reason] ?? reason}
                    </Badge>
                  ))}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

/* ------------------------------------------------------------------ */
/* Recipe discovery                                                   */
/* ------------------------------------------------------------------ */

function RecipeDiscovery({ exclude }: { exclude: string[] }) {
  const recipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        // Over-fetch, so dropping what another section already showed
        // still leaves a full row.
        query: { page_size: 9 },
        signal,
      }),
    [],
  );
  const items = (recipes.data?.results ?? [])
    .filter((recipe) => !exclude.includes(recipe.slug))
    .slice(0, 6);

  return (
    <Section
      title="สูตรขนมล่าสุด"
      description="ทำตามได้เลย พร้อมส่วนผสมและวิธีทำครบทุกขั้นตอน"
      href="/recipes"
      action={
        <Link href="/recipes/create">
          <Button variant="secondary" size="sm">
            <Icon name="ui/plus" tint className="size-4" /> เพิ่มสูตร
          </Button>
        </Link>
      }
    >
      {recipes.loading ? (
        <CardGridSkeleton count={6} />
      ) : recipes.error ? (
        <ErrorState error={recipes.error} onRetry={recipes.refetch} />
      ) : items.length === 0 ? (
        <EmptyState title="ยังไม่มีสูตรขนม" description="สูตรแรกกำลังจะมาเร็ว ๆ นี้" />
      ) : (
        <div className={FLUID_GRID}>
          {items.map((recipe) => (
            <RecipeCard key={recipe.slug} recipe={recipe} />
          ))}
        </div>
      )}
    </Section>
  );
}

/* ------------------------------------------------------------------ */
/* Category explorer                                                  */
/* ------------------------------------------------------------------ */

function CategoryExplorer() {
  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  // A tile with "0 สูตร" is a dead end, not an invitation - only
  // categories that actually lead somewhere get shown.
  const items = (categories.data ?? []).filter(
    (category) => category.recipe_count > 0,
  );
  if (categories.error || (!categories.loading && items.length === 0)) {
    return null;
  }

  return (
    <Section
      title="สำรวจตามหมวดขนม"
      description="เลือกสิ่งที่อยากอบ แล้วไปดูสูตรในหมวดนั้นทั้งหมด"
      href="/recipes"
      hrefLabel="ดูทุกหมวด →"
    >
      {categories.loading ? (
        <div aria-busy="true" className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="aspect-4/3 w-full rounded-surface" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {items.slice(0, 8).map((category) => (
            <CategoryTile
              key={category.slug}
              aspect="landscape"
              slug={category.slug}
              name={category.name}
              count={category.recipe_count}
              imageUrl={category.image_url}
              href={`/recipes?category=${category.slug}` as Route}
            />
          ))}
        </div>
      )}
    </Section>
  );
}

/* ------------------------------------------------------------------ */
/* Community preview                                                  */
/* ------------------------------------------------------------------ */

/**
 * The homepage community section.
 *
 * Read-only on purpose: it shows what people made and asked, and sends
 * them to /community to take part. The compose box that used to sit
 * here was a second entry point to the same editor.
 */
function CommunityPreview() {
  const gallery = useApiQuery(
    (signal) =>
      api.get<Paginated<GalleryPost>>("/gallery/", {
        query: { page_size: 6 },
        signal,
      }),
    [],
  );
  const threads = useApiQuery(
    (signal) =>
      api.get<Paginated<QaThread>>("/qa/threads/", {
        query: { page_size: 3 },
        signal,
      }),
    [],
  );

  const posts = (gallery.data?.results ?? []).filter(
    (post) => post.images.length > 0,
  );
  const questions = threads.data?.results ?? [];

  // Unlike the other sections, this one renders even when empty: the
  // homepage has to say "you can post your own baking here", and an
  // empty community is exactly when that matters most.
  return (
    <Section
      title="จากครัวของชุมชน"
      description="ผลงานจริงและคำถามล่าสุดจากเพื่อนนักอบ"
      href="/community"
      hrefLabel="ไปที่ชุมชน →"
    >
      {/* No composer here: posting belongs to /community, and a compose
          box on the home page duplicated the one that lives there. */}
      {/* Stacked, not two columns: squeezing the work into a third of
          the row made cards a third the size of every other card on the
          page. Same grid as the recipes above. */}
      <div className="space-y-8">
        {posts.length > 0 ? (
          <div>
            <h3 className="mb-3 text-sm font-medium text-fg-muted">
              ผลงานล่าสุด
            </h3>
            <ul className={FLUID_GRID}>
              {posts.slice(0, 3).map((post) => (
                <li key={post.id}>
                  <Link
                    href={`/community/posts/${post.id}` as Route}
                    className="group block h-full rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  >
                    <Card className="flex h-full flex-col overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay">
                      <div className="aspect-4/3 w-full overflow-hidden">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={post.images[0].url}
                          alt={post.caption || `ผลงานของ ${post.author_display_name}`}
                          loading="lazy"
                          className="size-full object-cover"
                        />
                      </div>
                      <div className="flex flex-1 flex-col gap-2 p-4">
                        <p className="line-clamp-2 min-h-10 text-sm text-fg">
                          {post.caption ||
                            (post.recipe ? `ทำจากสูตร ${post.recipe.title}` : "")}
                        </p>
                        <p className="mt-auto flex items-center gap-2 pt-1 text-xs text-fg-subtle">
                          <Avatar
                            src={post.author_avatar_url}
                            name={post.author_display_name}
                            size="sm"
                          />
                          <span className="truncate">
                            {post.author_display_name}
                          </span>
                        </p>
                      </div>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {questions.length > 0 ? (
          <div>
            <h3 className="mb-3 text-sm font-medium text-fg-muted">
              ถาม-ตอบล่าสุด
            </h3>
            <ul className="grid gap-3 sm:grid-cols-3">
              {questions.map((thread) => (
                <li key={thread.id}>
                  <Link
                    href={`/threads/${thread.id}` as Route}
                    className="block rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  >
                    <Card className="p-4 transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-overlay">
                      <p className="font-display line-clamp-1 font-medium text-fg">
                        <Icon name="ui/chat" className="size-3.5" /> {thread.title}
                      </p>
                      <p className="mt-1 flex items-center justify-between text-xs text-fg-subtle">
                        <span>ถามโดย @{thread.author_handle}</span>
                        {thread.accepted_answer ? (
                          <Badge tone="mint"><Icon name="ui/check" className="size-3.5" /> มีคำตอบแล้ว</Badge>
                        ) : null}
                      </p>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                               */
/* ------------------------------------------------------------------ */

export default function HomePage() {
  // What the recommendation feed showed, so the discovery grid below can
  // skip it: the same recipe in two sections of one page makes the
  // catalogue look smaller than it is.
  const [recommended, setRecommended] = useState<string[]>([]);

  return (
    <>
      <Hero />
      <PageContainer className="pb-4">
        <ContinueLearning />
        <SkillLevels />
        <FeaturedCourses />
        <RecommendationFeed onShown={setRecommended} />
        <RecipeDiscovery exclude={recommended} />
        {/* Community sits after recipes and before categories: enough to
            say "you can post here", never enough to take over the page. */}
        <CommunityPreview />
        <CategoryExplorer />
      </PageContainer>
    </>
  );
}
