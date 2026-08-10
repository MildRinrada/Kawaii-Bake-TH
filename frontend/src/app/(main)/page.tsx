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
import { useState } from "react";
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
import { Card, CardBody } from "@/components/ui/card";
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
  children,
  className,
}: {
  title: string;
  description?: string;
  href?: Route;
  hrefLabel?: string;
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
        {href ? (
          <Link
            href={href}
            className="rounded-full px-3 py-1 text-sm font-medium text-accent hover:bg-accent-subtle focus-visible:outline-2 focus-visible:outline-focus"
          >
            {hrefLabel}
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function CardGridSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div aria-busy="true" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
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
   right so it never sits under the headline, and purely decorative — the
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
      <ArtIcon
        src={BANNER.home}
        className="kb-float pointer-events-none absolute inset-y-0 right-0 hidden h-full w-[58%] object-cover object-right lg:block"
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
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/courses">
              <Button size="lg">
                เริ่มเรียนเลย
              </Button>
            </Link>
            <Link href="/recipes">
              <Button size="lg" variant="secondary">
                สำรวจสูตรขนม
              </Button>
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
      className="mt-10"
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
    description: "ยังไม่เคยอบก็เริ่มได้ — อุปกรณ์ วัตถุดิบ และสูตรแรกที่สำเร็จแน่",
    className: "bg-mint-soft text-mint-ink",
  },
  {
    difficulty: "intermediate",
    icon: "croissant" as const,
    name: "ระดับกลาง",
    description: "อบเป็นแล้ว อยากไปต่อ — เทคนิคแป้ง ครีม และการขึ้นรูป",
    className: "bg-butter-soft text-butter-ink",
  },
  {
    difficulty: "advanced",
    icon: "chef-hat" as const,
    name: "ขั้นสูง",
    description: "เก็บรายละเอียดระดับร้าน — งานตกแต่งและสูตรที่ท้าทาย",
    className: "bg-peach-soft text-peach-ink",
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
              "group rounded-surface p-6 shadow-raised transition-[transform,box-shadow] duration-150",
              "hover:-translate-y-0.5 hover:shadow-overlay",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
              level.className,
            )}
          >
            <Icon name={`ui/${level.icon}`} className="size-8" />
            <h3 className="font-display mt-3 text-lg font-medium">
              {level.name}
            </h3>
            <p className="mt-1 text-sm opacity-90">{level.description}</p>
            <p className="mt-4 text-sm font-medium">
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
      ) : (
        <div className="space-y-5">
          <FeaturedCourseCard course={courses.data.results[0]} />
          {courses.data.results.length > 1 ? (
            <div className="flex snap-x gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-3 sm:overflow-visible sm:pb-0">
              {courses.data.results.slice(1).map((course) => (
                <div key={course.slug} className="w-70 shrink-0 snap-start sm:w-auto">
                  <CourseCard course={course} />
                </div>
              ))}
            </div>
          ) : null}
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
        <div className="aspect-video w-full overflow-hidden md:aspect-auto md:w-1/2">
          <MediaFrame src={course.thumbnail_url} seed={course.slug} />
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

function RecommendationFeed() {
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
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
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

function RecipeDiscovery() {
  const recipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { page_size: 6 },
        signal,
      }),
    [],
  );

  return (
    <Section
      title="สูตรขนมล่าสุด"
      description="ทำตามได้เลย พร้อมส่วนผสมและวิธีทำครบทุกขั้นตอน"
      href="/recipes"
    >
      {/* The recipe section owns recipe authoring; the community section
          below owns post creation. The two CTAs never share a section. */}
      <div className="mb-4 flex justify-end">
        <Link href="/recipes/create">
          <Button variant="secondary" size="sm">
            + เพิ่มสูตรอาหาร
          </Button>
        </Link>
      </div>
      {recipes.loading ? (
        <CardGridSkeleton count={6} />
      ) : recipes.error ? (
        <ErrorState error={recipes.error} onRetry={recipes.refetch} />
      ) : !recipes.data || recipes.data.results.length === 0 ? (
        <EmptyState title="ยังไม่มีสูตรขนม" description="สูตรแรกกำลังจะมาเร็ว ๆ นี้" />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {recipes.data.results.map((recipe) => (
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

  const items = categories.data ?? [];
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
 * The homepage's community entry point.
 *
 * A composer-shaped invitation, not a working editor: tapping it opens
 * `/community/create`, where the real post is written. Anonymous
 * visitors get a sign-in call instead — the backend refuses anonymous
 * writes anyway, so showing a composer that cannot submit would be a
 * lie.
 */
function CommunityComposerCard() {
  const { status, user } = useAuth();

  if (status === "anonymous") {
    return (
      <Card className="kb-hero border-none">
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-display font-medium text-fg">
              อยากแบ่งปันขนมของคุณกับชุมชน?
            </p>
            <p className="text-sm text-fg-muted">
              เข้าสู่ระบบเพื่อโพสต์ผลงาน รูปถ่าย และเทคนิคของคุณ
            </p>
          </div>
          <Link href="/login">
            <Button>เข้าสู่ระบบเพื่อโพสต์</Button>
          </Link>
        </CardBody>
      </Card>
    );
  }

  if (status !== "authenticated") return null;

  return (
    <Card>
      <CardBody className="space-y-3">
        <p className="text-sm text-fg-muted">
          มีอะไรอยากแบ่งปันเกี่ยวกับการทำขนม?
        </p>
        <div className="flex items-center gap-3">
          <Avatar
            src={user?.avatar_url}
            name={user?.display_name || user?.username || "คุณ"}
          />
          <Link
            href="/community/create"
            className="flex-1 rounded-full bg-surface-sunken px-4 py-2.5 text-sm text-fg-subtle transition-colors hover:bg-accent-subtle hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            เขียนโพสต์…
          </Link>
          <Link href="/community/create" className="shrink-0">
            <Button size="sm">+ สร้างโพสต์</Button>
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}

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
      <CommunityComposerCard />

      <div className="mt-5 grid gap-6 lg:grid-cols-[3fr_2fr]">
        {posts.length > 0 ? (
          <div>
            <h3 className="mb-3 text-sm font-medium text-fg-muted">
              ผลงานล่าสุด
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {posts.slice(0, 6).map((post) => (
                <figure key={post.id} className="group relative overflow-hidden rounded-control">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={post.images[0].url}
                    alt={post.caption || `ผลงานของ ${post.author_display_name}`}
                    loading="lazy"
                    className="aspect-square w-full object-cover transition-transform duration-200 group-hover:scale-105"
                  />
                  <figcaption className="absolute inset-x-0 bottom-0 truncate bg-fg/55 px-2 py-1 text-xs text-fg-inverted">
                    {post.author_display_name}
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        ) : null}
        {questions.length > 0 ? (
          <div>
            <h3 className="mb-3 text-sm font-medium text-fg-muted">
              ถาม-ตอบล่าสุด
            </h3>
            <ul className="space-y-3">
              {questions.map((thread) => {
                const target = thread.recipe
                  ? (`/recipes/${thread.recipe.slug}` as Route)
                  : thread.course
                    ? (`/courses/${thread.course.slug}` as Route)
                    : null;
                const body = (
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
                );
                return (
                  <li key={thread.id}>
                    {target ? (
                      <Link
                        href={target}
                        className="block rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      >
                        {body}
                      </Link>
                    ) : (
                      body
                    )}
                  </li>
                );
              })}
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
  return (
    <>
      <Hero />
      <PageContainer className="pb-4">
        <ContinueLearning />
        <SkillLevels />
        <FeaturedCourses />
        <RecommendationFeed />
        <RecipeDiscovery />
        {/* Community sits after recipes and before categories: enough to
            say "you can post here", never enough to take over the page. */}
        <CommunityPreview />
        <CategoryExplorer />
      </PageContainer>
    </>
  );
}
