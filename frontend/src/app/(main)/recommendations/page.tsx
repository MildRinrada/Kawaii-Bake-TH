"use client";

/**
 * Recommendations: a personal baking roadmap, not an algorithmic dump.
 *
 * Every section is powered by the deterministic backend engine and owns
 * a *reason*: the ranked feed is bucketed by its reason codes (saved →
 * interests → explore), progress comes from `/me/progress/`, and the
 * "adjust my taste" panel writes the exact profile fields the engine
 * reads (favorite categories + experience level) — so the controls
 * genuinely change the output. Sections with nothing to say disappear
 * instead of rendering empty shells.
 */

import Link from "next/link";
import { useState } from "react";
import type { Route } from "next";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Category,
  CourseListItem,
  FavoriteItem,
  MyCourseProgress,
  OwnProfile,
  RecipeListItem,
  RecommendedCourse,
  RecommendedRecipe,
} from "@/lib/api/models";
import { REASON_LABELS } from "@/lib/recommendations";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { useFormSubmit } from "@/lib/forms/use-form";
import { Badge, DifficultyBadge, flavorFor } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { CourseCard } from "@/components/content/course-card";
import { MediaFrame } from "@/components/content/media-frame";
import { RecipeCard } from "@/components/content/recipe-card";
import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ */
/* Vocabulary                                                          */
/* ------------------------------------------------------------------ */

const LEVEL_LABELS: Record<string, string> = {
  beginner: "มือใหม่หัดอบ",
  intermediate: "พออบเป็น",
  advanced: "สายอบตัวจริง",
  professional: "มืออาชีพ",
};

const NEXT_LEVEL: Record<string, string> = {
  beginner: "intermediate",
  intermediate: "advanced",
  advanced: "professional",
  professional: "professional",
};

// Feed items are bucketed by the engine's own reason codes.
const SAVED_REASONS = new Set([
  "similar_to_your_favorites",
  "from_a_creator_you_like",
]);
const INTEREST_REASONS = new Set([
  "matches_your_favorite_categories",
  "similar_to_content_you_reviewed",
]);

const MAX_FAVORITE_CATEGORIES = 10;

/* ------------------------------------------------------------------ */
/* Small shared pieces                                                 */
/* ------------------------------------------------------------------ */

function Reasons({ reasons, max = 2 }: { reasons: string[]; max?: number }) {
  if (!reasons.length) return null;
  return (
    <p className="mt-2 flex flex-wrap gap-1.5">
      {reasons.slice(0, max).map((reason) => (
        <Badge key={reason} tone="lavender">
          ✨ {REASON_LABELS[reason] ?? reason}
        </Badge>
      ))}
    </p>
  );
}

function Section({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("mt-12", className)}>
      <h2 className="font-display text-xl font-medium text-fg sm:text-2xl">
        {title}
      </h2>
      {description ? (
        <p className="mt-1 text-sm text-fg-muted">{description}</p>
      ) : null}
      <div className="mt-5">{children}</div>
    </section>
  );
}

/** Secondary rows: horizontal scroll on mobile, grid from sm up. */
function ScrollRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex snap-x gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-2 sm:overflow-visible sm:pb-0 lg:grid-cols-3">
      {children}
    </div>
  );
}

function RowItem({ children }: { children: React.ReactNode }) {
  return <div className="w-70 shrink-0 snap-start sm:w-auto">{children}</div>;
}

/* ------------------------------------------------------------------ */
/* Taste panel — writes the fields the engine actually reads          */
/* ------------------------------------------------------------------ */

function TastePanel({
  profile,
  categories,
  onboarding,
  onSaved,
}: {
  profile: OwnProfile;
  categories: Category[];
  onboarding: boolean;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const form = useFormSubmit();
  const [selected, setSelected] = useState<string[]>(profile.favorite_categories);
  const [level, setLevel] = useState(profile.experience_level);

  function toggle(slug: string) {
    setSelected((current) =>
      current.includes(slug)
        ? current.filter((item) => item !== slug)
        : current.length < MAX_FAVORITE_CATEGORIES
          ? [...current, slug]
          : current,
    );
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const ok = await form.submit(async () => {
      await api.patch("/users/profile/update/", {
        body: { favorite_categories: selected, experience_level: level },
      });
    });
    if (ok) {
      toast("ปรับคำแนะนำให้ใหม่แล้ว ✨", "success");
      onSaved();
    }
  }

  return (
    <Card
      className={cn(
        "p-5 sm:p-6",
        onboarding && "border border-berry-ink/15 bg-berry-soft/40",
      )}
    >
      <form onSubmit={save} className="space-y-4">
        {onboarding ? (
          <div>
            <h2 className="font-display text-lg font-medium text-fg">
              บอกเราหน่อยว่าชอบอบอะไร 🧁
            </h2>
            <p className="mt-1 text-sm text-fg-muted">
              เลือกหมวดที่ชอบและระดับของคุณ
              แล้วเราจะคัดสูตรกับคอร์สให้ตรงใจขึ้นทันที
            </p>
          </div>
        ) : null}
        {form.formError ? (
          <p role="alert" className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger">
            {form.formError}
          </p>
        ) : null}

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">
            หมวดที่ชอบ{" "}
            <span className="font-normal text-fg-subtle">
              (เลือกได้สูงสุด {MAX_FAVORITE_CATEGORIES})
            </span>
          </legend>
          <div className="flex flex-wrap gap-2">
            {categories.map((category) => {
              const active = selected.includes(category.slug);
              return (
                <button
                  key={category.slug}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggle(category.slug)}
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-sm transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-focus",
                    active
                      ? "bg-accent font-medium text-fg-inverted shadow-raised"
                      : "bg-surface text-fg-muted shadow-raised hover:text-fg",
                  )}
                >
                  {category.icon ? `${category.icon} ` : ""}
                  {category.name}
                </button>
              );
            })}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">
            ระดับของคุณ
          </legend>
          <div className="flex flex-wrap gap-2" role="group">
            {Object.entries(LEVEL_LABELS).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={level === value}
                onClick={() => setLevel(value)}
                className={cn(
                  "rounded-full px-3.5 py-1.5 text-sm transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-focus",
                  level === value
                    ? "bg-lavender-ink font-medium text-fg-inverted shadow-raised"
                    : "bg-surface text-fg-muted shadow-raised hover:text-fg",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        <Button type="submit" loading={form.submitting}>
          {onboarding ? "ปรับแต่งคำแนะนำของฉัน" : "บันทึกความสนใจ"}
        </Button>
      </form>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Hero recommendation                                                 */
/* ------------------------------------------------------------------ */

function HeroRecommendation({
  item,
  authenticated,
}: {
  item: RecommendedRecipe;
  authenticated: boolean;
}) {
  const { toast } = useToast();
  const recipe = item.recipe as unknown as RecipeListItem;

  async function saveForLater() {
    try {
      await api.post(`/recipes/${recipe.slug}/favorite/`);
      toast("บันทึกเข้ารายการโปรดแล้ว 🔖", "success");
    } catch {
      toast("บันทึกไม่สำเร็จ ลองอีกครั้งนะ", "danger");
    }
  }

  return (
    <Card className="mt-6 overflow-hidden md:flex">
      <div className="aspect-video w-full overflow-hidden md:aspect-auto md:w-1/2">
        <MediaFrame src={recipe.cover_image_url} seed={recipe.slug} />
      </div>
      <div className="flex flex-col justify-center gap-3 p-6 md:w-1/2 md:p-8">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="berry">
            {authenticated ? "🎯 แนะนำให้ลองต่อไป" : "🔥 กำลังเป็นที่นิยม"}
          </Badge>
          <DifficultyBadge level={recipe.difficulty} />
          {recipe.categories.slice(0, 1).map((category) => (
            <Badge key={category.slug} tone={flavorFor(category.slug)}>
              {category.name}
            </Badge>
          ))}
        </div>
        <h2 className="font-display text-xl font-medium text-fg sm:text-2xl">
          {recipe.title}
        </h2>
        <p className="line-clamp-2 text-sm text-fg-muted">{recipe.summary}</p>
        <Reasons reasons={item.reasons} max={3} />
        <p className="text-xs text-fg-subtle">
          ⏱ ประมาณ {recipe.total_minutes} นาที · โดย{" "}
          {recipe.author.display_name || recipe.author.username}
        </p>
        <div className="mt-1 flex flex-wrap gap-2.5">
          <Link href={`/recipes/${recipe.slug}`}>
            <Button>ดูสูตรนี้เลย</Button>
          </Link>
          {authenticated ? (
            <Button variant="secondary" onClick={() => void saveForLater()}>
              🔖 บันทึกไว้ก่อน
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function RecommendationsPage() {
  const { status } = useAuth();
  const authenticated = status === "authenticated";
  const [panelOpen, setPanelOpen] = useState(false);

  const profile = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<OwnProfile>("/users/profile/", { signal })
        : Promise.resolve(null),
    [status],
  );
  const progress = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<{ courses: MyCourseProgress[] }>("/me/progress/", { signal })
        : Promise.resolve({ courses: [] as MyCourseProgress[] }),
    [status],
  );
  const favorites = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<Paginated<FavoriteItem>>("/users/me/favorites/", {
            query: { type: "recipe", page_size: 1 },
            signal,
          })
        : Promise.resolve(null),
    [status],
  );
  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );
  const recRecipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecommendedRecipe>>("/recommendations/recipes/", {
        query: { page_size: 12 },
        signal,
      }),
    [status],
  );
  const recCourses = useApiQuery(
    (signal) =>
      api.get<Paginated<RecommendedCourse>>("/recommendations/courses/", {
        query: { page_size: 6 },
        signal,
      }),
    [status],
  );

  function refetchFeed() {
    profile.refetch();
    recRecipes.refetch();
    recCourses.refetch();
  }

  /* ---------- Derived layout data (plain code, no extra state) ----- */

  const recipeItems = (recRecipes.data?.results ?? []).filter(
    (item) => item.recipe,
  );
  const hero = recipeItems[0] ?? null;
  const rest = recipeItems.slice(1);
  const savedBucket = rest.filter((item) =>
    item.reasons.some((reason) => SAVED_REASONS.has(reason)),
  );
  const interestBucket = rest.filter(
    (item) =>
      !savedBucket.includes(item) &&
      item.reasons.some((reason) => INTEREST_REASONS.has(reason)),
  );
  const exploreBucket = rest.filter(
    (item) => !savedBucket.includes(item) && !interestBucket.includes(item),
  );

  const courseItems = (recCourses.data?.results ?? [])
    .filter((item) => item.course)
    .map((item) => ({
      ...item,
      course: item.course as unknown as CourseListItem,
    }));
  const nextCourses = courseItems
    .filter((item) => !item.course.is_enrolled)
    .slice(0, 3);

  const allProgress = progress.data?.courses ?? [];
  // Priority = closest to the finish line first; completed courses feed
  // the "next steps" story instead of dominating this strip.
  const inProgress = [...allProgress]
    .filter((course) => course.percentage < 100)
    .sort((a, b) => b.percentage - a.percentage)
    .slice(0, 4);
  const completedCourses = allProgress.filter((course) => course.completed_at);

  const level = profile.data?.experience_level ?? "";
  const firstFavorite = favorites.data?.results?.[0]?.recipe as
    | { title?: string }
    | null
    | undefined;
  const isNewUser =
    authenticated &&
    profile.data !== null &&
    profile.data !== undefined &&
    profile.data.favorite_categories.length === 0 &&
    allProgress.length === 0 &&
    (favorites.data?.count ?? 0) === 0;

  const loading = recRecipes.loading || status === "loading";

  return (
    <PageContainer>
      {/* ---------- Header ---------- */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-medium text-fg sm:text-3xl">
            แนะนำสำหรับคุณ ✨
          </h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            {authenticated
              ? "คัดจากหมวดที่คุณชอบ ของที่บันทึก รีวิว และคอร์สที่เรียนอยู่"
              : "เข้าสู่ระบบเพื่อรับคำแนะนำที่ตรงกับรสมือของคุณ"}
            {authenticated && level ? (
              <Badge tone="lavender">👩‍🍳 {LEVEL_LABELS[level] ?? level}</Badge>
            ) : null}
          </p>
        </div>
        {authenticated && profile.data && !isNewUser ? (
          <Button
            variant="secondary"
            size="sm"
            aria-expanded={panelOpen}
            onClick={() => setPanelOpen((value) => !value)}
          >
            {panelOpen ? "ปิดการปรับความสนใจ" : "⚙️ ปรับความสนใจ"}
          </Button>
        ) : null}
      </div>

      {/* ---------- Taste controls / first-time onboarding ---------- */}
      {authenticated && profile.data && categories.data ? (
        isNewUser ? (
          <div className="mt-6">
            <TastePanel
              profile={profile.data}
              categories={categories.data}
              onboarding
              onSaved={refetchFeed}
            />
          </div>
        ) : panelOpen ? (
          <div className="mt-6">
            <TastePanel
              key={profile.data.favorite_categories.join(",")}
              profile={profile.data}
              categories={categories.data}
              onboarding={false}
              onSaved={refetchFeed}
            />
          </div>
        ) : null
      ) : null}

      {/* ---------- Content ---------- */}
      {loading ? (
        <div aria-busy="true" className="mt-6 space-y-6">
          <Skeleton className="h-72 w-full rounded-surface" />
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }, (_, index) => (
              <Skeleton key={index} className="h-64 w-full rounded-surface" />
            ))}
          </div>
        </div>
      ) : recRecipes.error ? (
        <div className="mt-6">
          <ErrorState error={recRecipes.error} onRetry={recRecipes.refetch} />
        </div>
      ) : !hero ? (
        <div className="mt-6">
          <EmptyState
            icon="✨"
            title="ยังไม่มีคำแนะนำตอนนี้"
            description="ลองกลับมาใหม่เมื่อมีสูตรและคอร์สเพิ่มขึ้น"
          />
        </div>
      ) : (
        <>
          <HeroRecommendation item={hero} authenticated={authenticated} />

          {/* Continue learning */}
          {inProgress.length > 0 ? (
            <Section
              title="เรียนต่อจากที่ค้างไว้ 📖"
              description="เรียงตามคอร์สที่ใกล้จบก่อน — อีกนิดเดียวเอง"
            >
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
                      เรียนแล้ว {course.completed_lessons} จาก{" "}
                      {course.total_lessons} บทเรียน
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
                        เรียนต่อ →
                      </Button>
                    </Link>
                  </div>
                ))}
              </div>
            </Section>
          ) : null}

          {/* Learning progression */}
          {authenticated && nextCourses.length > 0 ? (
            <Section
              title="ก้าวถัดไปของคุณ 🎯"
              description="เส้นทางเรียนที่ต่อยอดจากระดับและคอร์สของคุณ"
            >
              <div className="rounded-surface bg-surface-sunken/60 p-5 sm:p-6">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-fg-muted">ตอนนี้คุณคือ</span>
                  <Badge tone="mint">
                    {LEVEL_LABELS[level] ?? "นักอบ"}
                  </Badge>
                  {completedCourses.length > 0 ? (
                    <>
                      <span className="text-fg-muted">· เรียนจบแล้ว</span>
                      {completedCourses.slice(0, 2).map((course) => (
                        <Badge key={course.slug} tone="mint">
                          ✓ {course.title}
                        </Badge>
                      ))}
                    </>
                  ) : null}
                  <span aria-hidden className="text-fg-subtle">
                    →
                  </span>
                  <span className="text-fg-muted">เป้าหมายถัดไป</span>
                  <Badge tone="lavender">
                    {LEVEL_LABELS[NEXT_LEVEL[level] ?? "intermediate"] ??
                      "ระดับถัดไป"}
                  </Badge>
                </div>
                <div className="mt-5">
                  <ScrollRow>
                    {nextCourses.map((item, index) => (
                      <RowItem key={index}>
                        <CourseCard course={item.course} />
                        <Reasons reasons={item.reasons} />
                      </RowItem>
                    ))}
                  </ScrollRow>
                </div>
              </div>
            </Section>
          ) : null}

          {/* Based on your interests */}
          {interestBucket.length > 0 ? (
            <Section
              title="จากหมวดที่คุณชอบ 💐"
              description={
                profile.data && profile.data.favorite_categories.length > 0
                  ? `คุณบอกว่าชอบ: ${profile.data.favorite_categories.join(", ")}`
                  : "อิงจากหมวดและของที่คุณเคยรีวิว"
              }
            >
              <ScrollRow>
                {interestBucket.slice(0, 6).map((item, index) => (
                  <RowItem key={index}>
                    <RecipeCard
                      recipe={item.recipe as unknown as RecipeListItem}
                    />
                    <Reasons reasons={item.reasons} />
                  </RowItem>
                ))}
              </ScrollRow>
            </Section>
          ) : null}

          {/* Because you saved */}
          {savedBucket.length > 0 ? (
            <Section
              title="เพราะคุณบันทึกไว้ 🔖"
              description={
                firstFavorite?.title
                  ? `ต่อยอดจาก “${firstFavorite.title}” และรายการโปรดอื่น ๆ ของคุณ`
                  : "ต่อยอดจากรายการโปรดของคุณ"
              }
            >
              <ScrollRow>
                {savedBucket.slice(0, 6).map((item, index) => (
                  <RowItem key={index}>
                    <RecipeCard
                      recipe={item.recipe as unknown as RecipeListItem}
                    />
                    <Reasons reasons={item.reasons} />
                  </RowItem>
                ))}
              </ScrollRow>
            </Section>
          ) : null}

          {/* Explore / recipes to bake now — the shortcuts stay useful
              even when the ranked feed was fully absorbed above. */}
          <Section
            title="อยากอบเลยวันนี้ 🥣"
            description="เลือกตามเวลาและระดับที่คุณมี — พาไปหน้าสูตรพร้อมตัวกรอง"
          >
              <div className="mb-4 flex flex-wrap gap-2">
                <Link
                  href={"/recipes?max_total_minutes=30" as Route}
                  className="rounded-full bg-surface px-3.5 py-1.5 text-sm text-fg-muted shadow-raised hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                >
                  ⚡ เสร็จใน 30 นาที
                </Link>
                <Link
                  href={"/recipes?difficulty=easy" as Route}
                  className="rounded-full bg-surface px-3.5 py-1.5 text-sm text-fg-muted shadow-raised hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                >
                  🌱 ง่ายสำหรับมือใหม่
                </Link>
                <Link
                  href={"/recipes?difficulty=hard,expert" as Route}
                  className="rounded-full bg-surface px-3.5 py-1.5 text-sm text-fg-muted shadow-raised hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                >
                  🏆 ท้าทายฝีมือ
                </Link>
              </div>
              {exploreBucket.length > 0 ? (
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {exploreBucket.slice(0, 6).map((item, index) => (
                    <div key={index}>
                      <RecipeCard
                        recipe={item.recipe as unknown as RecipeListItem}
                      />
                      <Reasons reasons={item.reasons} />
                    </div>
                  ))}
                </div>
              ) : null}
            </Section>

          {/* Anonymous: invite to personalize */}
          {!authenticated ? (
            <Card className="mt-12 border border-berry-ink/15 bg-berry-soft/40 p-6 text-center sm:p-8">
              <h2 className="font-display text-lg font-medium text-fg">
                อยากได้คำแนะนำที่ตรงใจกว่านี้?
              </h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-fg-muted">
                สมัครสมาชิกแล้วบอกเราว่าชอบอบอะไร —
                สูตรและคอร์สจะถูกคัดใหม่ให้เข้ากับคุณโดยเฉพาะ
              </p>
              <div className="mt-4 flex justify-center gap-3">
                <Link href="/register">
                  <Button>สมัครฟรี</Button>
                </Link>
                <Link href="/login">
                  <Button variant="secondary">เข้าสู่ระบบ</Button>
                </Link>
              </div>
            </Card>
          ) : null}
        </>
      )}
    </PageContainer>
  );
}
