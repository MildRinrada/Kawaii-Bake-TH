"use client";

/**
 * Recipe detail: an interactive baking workspace, not an article.
 *
 * The workspace (scaler → unit toggle → ingredient checklist → stepped
 * instructions with timers → focus mode) is driven entirely by real
 * recipe data  quantities scale from the stored decimals, timers come
 * from `duration_minutes` (or a duration the step text actually
 * states), substitutions come from the rule registry endpoint. Baking
 * progress, servings, units and personal notes persist per-recipe in
 * this browser (localStorage) so a baker can leave and resume.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type {
  GalleryPost,
  RecipeDetail,
  RecipeListItem,
  Review,
} from "@/lib/api/models";
import { MAX_RECIPE_COMMUNITY_POSTS } from "@/lib/community";
import type { components } from "@/lib/api/types";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Badge, DifficultyBadge, flavorFor } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Rating, StarPicker } from "@/components/ui/rating";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Icon } from "@/components/ui/icon";
import { CoverFrame } from "@/components/content/cover-frame";
import { RecipeCard } from "@/components/content/recipe-card";
import { CommunityPostCard } from "@/components/community/post-card";
import { cn } from "@/lib/cn";

/** One toast identity for favouriting, so rapid clicks rewrite a single
    message instead of stacking one per click. */
const FAVORITE_TOAST = "favorite";


type RatingSummary = components["schemas"]["RatingSummary"];
type Ingredient = components["schemas"]["RecipeIngredient"];
type Step = components["schemas"]["RecipeStep"];
type IngredientSubstitution = components["schemas"]["IngredientSubstitution"];
type SubstitutionOption = IngredientSubstitution["substitutions"][number];

/* ------------------------------------------------------------------ */
/* Quantity scaling + unit conversion                                  */
/* ------------------------------------------------------------------ */

type UnitSystem = "metric" | "imperial";

// Only true weight/volume units convert; spoon/piece measures stay put.
const IMPERIAL: Record<string, { unit: string; factor: number }> = {
  g: { unit: "oz", factor: 1 / 28.35 },
  kg: { unit: "lb", factor: 2.2046 },
  ml: { unit: "fl oz", factor: 1 / 29.574 },
};

/** Round to a kitchen-practical precision  no fake decimals. */
function practicalRound(value: number): number {
  if (value >= 100) return Math.round(value);
  if (value >= 10) return Math.round(value * 2) / 2;
  return Math.round(value * 4) / 4;
}

function formatAmount(value: number): string {
  const rounded = practicalRound(value);
  return Number.isInteger(rounded)
    ? String(rounded)
    : String(parseFloat(rounded.toFixed(2)));
}

function scaledQuantity(
  ingredient: Ingredient,
  factor: number,
  system: UnitSystem,
): string | null {
  if (ingredient.quantity === null) return null;
  const base = parseFloat(ingredient.quantity) * factor;
  const conversion =
    system === "imperial" ? IMPERIAL[ingredient.unit.toLowerCase()] : undefined;
  if (conversion) {
    return `${formatAmount(base * conversion.factor)} ${conversion.unit}`;
  }
  return `${formatAmount(base)} ${ingredient.unit}`.trim();
}

/** A step's timer length: the stored field first, else a duration the
 *  step text itself states ("พัก 30 นาที"). Never invented. */
function stepMinutes(step: Step): number | null {
  if (step.duration_minutes) return step.duration_minutes;
  const match = step.body.match(/(\d+)\s*นาที/);
  return match ? parseInt(match[1], 10) : null;
}

/* ------------------------------------------------------------------ */
/* Persistent baking session (this browser only)                       */
/* ------------------------------------------------------------------ */

interface BakeSession {
  servings: number;
  unitSystem: UnitSystem;
  checked: number[];
  done: number[];
  notes: string;
  /** Ingredient index → the substitute the baker chose to use instead. */
  swaps: Record<string, SubstitutionOption>;
}

function loadSession(slug: string, fallbackServings: number): BakeSession {
  const empty: BakeSession = {
    servings: fallbackServings,
    unitSystem: "metric",
    checked: [],
    done: [],
    notes: "",
    swaps: {},
  };
  if (typeof window === "undefined") return empty;
  try {
    const raw = window.localStorage.getItem(`kb-bake-${slug}`);
    if (!raw) return empty;
    return { ...empty, ...(JSON.parse(raw) as Partial<BakeSession>) };
  } catch {
    return empty;
  }
}

/* ------------------------------------------------------------------ */
/* Timers                                                              */
/* ------------------------------------------------------------------ */

interface BakeTimer {
  id: number;
  label: string;
  remaining: number;
  running: boolean;
}

function formatClock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function TimerDock({
  timers,
  onToggle,
  onDismiss,
}: {
  timers: BakeTimer[];
  onToggle: (id: number) => void;
  onDismiss: (id: number) => void;
}) {
  if (timers.length === 0) return null;
  return (
    <div
      aria-label="ตัวจับเวลา"
      className="fixed bottom-4 right-4 z-50 flex w-64 flex-col gap-2"
    >
      {timers.map((timer) => (
        <div
          key={timer.id}
          role="timer"
          className={cn(
            "flex items-center gap-3 rounded-surface border px-4 py-3 shadow-overlay backdrop-blur",
            timer.remaining === 0
              ? "border-success bg-success-subtle"
              : "border-lavender-ink/20 bg-surface/95",
          )}
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-fg-muted">{timer.label}</p>
            <p
              className={cn(
                "font-display text-xl font-medium tabular-nums",
                timer.remaining === 0 ? "text-success" : "text-fg",
              )}
            >
              {timer.remaining === 0 ? "เสร็จแล้ว!" : formatClock(timer.remaining)}
            </p>
          </div>
          {timer.remaining > 0 ? (
            <button
              type="button"
              onClick={() => onToggle(timer.id)}
              aria-label={timer.running ? "พักเวลา" : "จับเวลาต่อ"}
              className="rounded-full bg-surface-sunken px-3 py-1.5 text-xs font-medium text-fg-muted hover:bg-edge focus-visible:outline-2 focus-visible:outline-focus"
            >
              {timer.running ? "พัก" : "ต่อ"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => onDismiss(timer.id)}
            aria-label="ปิดตัวจับเวลา"
            className="flex size-13 items-center justify-center rounded-full hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
          >
            <Icon name="ui/close" tint className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Hero actions                                                        */
/* ------------------------------------------------------------------ */

function FavoriteButton({ slug }: { slug: string }) {
  const { status } = useAuth();
  const { toast } = useToast();
  const [favorited, setFavorited] = useState(false);
  const [busy, setBusy] = useState(false);
  if (status !== "authenticated") return null;

  async function toggle() {
    setBusy(true);
    try {
      if (favorited) {
        await api.delete(`/recipes/${slug}/favorite/`);
        setFavorited(false);
        toast("นำออกจากรายการโปรดแล้ว", "neutral", FAVORITE_TOAST);
      } else {
        await api.post(`/recipes/${slug}/favorite/`);
        setFavorited(true);
        toast("บันทึกเข้ารายการโปรดแล้ว", "success", FAVORITE_TOAST);
      }
    } catch {
      toast("ทำรายการไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant="secondary" loading={busy} onClick={() => void toggle()}>
      <Icon
        tint
        name={favorited ? "ui/heart-filled-2" : "ui/heart"}
        className="size-4"
      />
      {favorited ? "อยู่ในรายการโปรด" : "บันทึกเข้ารายการโปรด"}
    </Button>
  );
}

function ShareButton() {
  const { toast } = useToast();
  async function share() {
    try {
      if (navigator.share) {
        await navigator.share({ url: window.location.href, title: document.title });
      } else {
        await navigator.clipboard.writeText(window.location.href);
        toast("คัดลอกลิงก์แล้ว", "success");
      }
    } catch {
      // User dismissed the share sheet  nothing to report.
    }
  }
  return (
    <Button variant="secondary" onClick={() => void share()}>
      <Icon name="ui/share" tint className="size-4" /> แชร์
    </Button>
  );
}

/* ------------------------------------------------------------------ */
/* Review form                                                         */
/* ------------------------------------------------------------------ */

function ReviewForm({
  slug,
  onPosted,
  onCancel,
}: {
  slug: string;
  onPosted: () => void;
  onCancel: () => void;
}) {
  const { toast } = useToast();
  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (stars === 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/recipes/${slug}/reviews/`, {
        body: { rating: stars, comment },
      });
      toast("ขอบคุณสำหรับรีวิวนะ", "success");
      setStars(0);
      setComment("");
      onPosted();
    } catch (err) {
      if (err instanceof ApiError && err.code === "already_reviewed") {
        setError("คุณรีวิวสูตรนี้ไปแล้ว  แก้ไขได้จากรีวิวเดิมของคุณ");
      } else if (err instanceof ApiError && err.code === "own_content") {
        setError("รีวิวสูตรของตัวเองไม่ได้นะ");
      } else {
        setError("ส่งรีวิวไม่สำเร็จ ลองใหม่อีกครั้ง");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-5 rounded-control border border-edge bg-surface-sunken/60 p-4"
    >
      <p className="mb-2 text-sm font-medium text-fg">ทำสูตรนี้แล้วเป็นยังไงบ้าง?</p>
      {error ? (
        <p role="alert" className="mb-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="mb-3">
        <StarPicker value={stars} onChange={setStars} />
      </div>
      <Textarea
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        placeholder="เล่าผลลัพธ์ เคล็ดลับ หรือสิ่งที่ปรับ…"
        rows={2}
      />
      <div className="mt-3 flex items-center gap-2">
        {/* Full-strength primary, and genuinely disabled until a star is
            picked — the washed-out pink used to *look* disabled while
            being clickable, which is the worst of both. */}
        <Button type="submit" loading={busy} disabled={stars === 0}>
          ส่งรีวิว
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          ยกเลิก
        </Button>
        {stars === 0 ? (
          <span className="text-xs text-fg-subtle">เลือกดาวก่อนส่งได้</span>
        ) : null}
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Screen                                                              */
/* ------------------------------------------------------------------ */

export function RecipeDetailScreen({ slug }: { slug: string }) {
  const { status } = useAuth();
  const [writing, setWriting] = useState(false);
  /** Bumped by the hero CTA; the workspace opens focus mode on change. */
  const [focusRequest, setFocusRequest] = useState(0);
  const recipe = useApiQuery(
    (signal) => api.get<RecipeDetail>(`/recipes/${slug}/`, { signal }),
    [slug],
  );
  const rating = useApiQuery(
    (signal) => api.get<RatingSummary>(`/recipes/${slug}/rating/`, { signal }),
    [slug],
  );
  const reviews = useApiQuery(
    (signal) =>
      api.get<Paginated<Review>>(`/recipes/${slug}/reviews/`, {
        query: { page_size: 5 },
        signal,
      }),
    [slug],
  );
  const substitutions = useApiQuery(
    (signal) =>
      api.get<{ results: IngredientSubstitution[] }>(
        `/recipes/${slug}/substitutions/`,
        { signal },
      ),
    [slug],
  );
  // Related recipes, with the reason stated. Same category first; when
  // the catalogue has no sibling there, same difficulty - and the
  // heading says which of the two it is, so a suggestion is never an
  // unexplained assertion.
  const relatedCategory = recipe.data?.categories[0]?.slug ?? "";
  const relatedDifficulty = recipe.data?.difficulty ?? "";
  const related = useApiQuery(
    async (signal) => {
      if (relatedCategory) {
        const byCategory = await api.get<Paginated<RecipeListItem>>("/recipes/", {
          query: { category: relatedCategory, page_size: 4 },
          signal,
        });
        if (byCategory.results.some((item) => item.slug !== slug)) {
          return { reason: "category" as const, page: byCategory };
        }
      }
      if (!relatedDifficulty) return null;
      const byDifficulty = await api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { difficulty: relatedDifficulty, page_size: 4 },
        signal,
      });
      return { reason: "difficulty" as const, page: byDifficulty };
    },
    [relatedCategory, relatedDifficulty, slug],
  );

  if (recipe.loading) {
    return (
      <PageContainer aria-busy="true">
        <Skeleton className="mb-6 h-72 w-full rounded-surface" />
        <Skeleton className="mb-3 h-9 w-2/3" />
        <Skeleton className="h-40 w-full rounded-surface" />
      </PageContainer>
    );
  }
  if (recipe.error || !recipe.data) {
    return (
      <PageContainer>
        <ErrorState error={recipe.error} onRetry={recipe.refetch} />
      </PageContainer>
    );
  }
  const data = recipe.data;
  const relatedItems = (related.data?.page.results ?? [])
    .filter((item) => item.slug !== slug)
    .slice(0, 3);
  const relatedReason =
    related.data?.reason === "difficulty"
      ? "ระดับความยากใกล้เคียงกัน"
      : `อยู่ในหมวด ${data.categories[0]?.name ?? ""} เหมือนกัน`;

  return (
    <PageContainer>
      {/* ---------- Hero ----------
          Two columns rather than a full-width banner. The cover keeps the
          card's 4:3 (or 3:4 for a phone photo), so the picture the author
          framed is the picture shown — a 21:9 strip cut a plate of food
          down to its middle band — and the actions come up beside the
          title instead of below a 400px image. */}
      <div className="grid gap-6 lg:grid-cols-2 lg:items-center">
        <CoverFrame
          src={data.cover_image_url}
          seed={data.slug}
          alt={data.title}
        />

        <div id="overview" className="min-w-0 scroll-mt-32">
          <div className="mb-2 flex flex-wrap gap-1.5">
            <DifficultyBadge level={data.difficulty} />
            {data.categories.map((category) => (
              <Badge key={category.slug} tone={flavorFor(category.slug)}>
                {category.icon} {category.name}
              </Badge>
            ))}
          </div>
          <h1 className="font-display text-2xl font-medium text-fg sm:text-3xl">
            {data.title}
          </h1>
          <p className="mt-2 text-fg-muted">{data.summary}</p>
          <ul className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg-muted">
            {(
              [
                { icon: "clock", text: `${data.total_minutes} นาที` },
                { icon: "plate", text: `${data.servings} ที่` },
                { icon: "scroll", text: `${data.steps.length} ขั้นตอน` },
              ] as const
            ).map((item) => (
              <li key={item.icon} className="flex items-center gap-1.5">
                <Icon name={`ui/${item.icon}`} tint className="size-4 text-fg-subtle" />
                {item.text}
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-fg-muted">
            <span className="flex items-center gap-2">
              <Avatar
                src={data.author.avatar_url}
                name={data.author.display_name || data.author.username}
                size="sm"
              />
              {data.author.display_name || data.author.username}
            </span>
            {rating.data ? (
              <a
                href="#reviews"
                className="rounded-full hover:underline focus-visible:outline-2 focus-visible:outline-focus"
              >
                <Rating average={rating.data.average} count={rating.data.count} />
              </a>
            ) : null}
          </div>
          <div className="mt-5 flex flex-wrap gap-2.5">
            {/* The page's best feature is the CTA, not a button that
                scrolls the page for you. */}
            <Button
              onClick={() => setFocusRequest((count) => count + 1)}
              title="ทีละขั้นตอน ตัวใหญ่ พร้อมตัวจับเวลา  เหมาะกับตอนมือเลอะแป้ง"
            >
              <Icon name="ui/chef-hat" tint className="size-4" /> เริ่มโหมดทำขนม
            </Button>
            <FavoriteButton slug={slug} />
            <ShareButton />
          </div>
          <p className="mt-2 text-xs text-fg-subtle">
            โหมดทำขนมจะแสดงทีละขั้นตอนตัวใหญ่ กดจับเวลาได้ในหน้าเดียว
          </p>
        </div>
      </div>

      {/* No four-across stat band here: prep/bake/total/yield are four
          short numbers that were stretched across the full page width,
          and the sticky bar repeated two of them. They now live once, in
          the workspace's left column beside the scaler that changes
          them. */}

      {data.description ? (
        <p className="mt-5 max-w-3xl whitespace-pre-line text-sm leading-relaxed text-fg-muted">
          {data.description}
        </p>
      ) : null}

      {/* ---------- Interactive workspace ---------- */}
      <Workspace
        data={data}
        substitutions={substitutions.data?.results ?? []}
        focusRequest={focusRequest}
      />

      {/* ---------- Reviews ----------
          What people said comes first; the form is a button until it is
          wanted. A large empty compose box above one small real review
          weights the section towards writing over reading. */}
      <Card className="mt-10 scroll-mt-32" id="reviews">
        <CardHeader
          title="รีวิวจากคนที่ทำแล้ว"
          actions={
            rating.data ? (
              <Rating average={rating.data.average} count={rating.data.count} />
            ) : null
          }
        />
        <CardBody>
          {reviews.loading ? (
            <Skeleton className="h-20 w-full" />
          ) : !reviews.data || reviews.data.results.length === 0 ? (
            <p className="py-4 text-center text-sm text-fg-muted">
              ยังไม่มีรีวิว  ลองทำสูตรนี้แล้วมาเล่าให้ฟังนะ
            </p>
          ) : (
            <ul className="space-y-4">
              {reviews.data.results.map((review) => (
                <li
                  key={review.id}
                  className="border-b border-edge pb-4 last:border-0 last:pb-0"
                >
                  <div className="mb-1 flex items-center gap-2">
                    <Avatar
                      src={review.user.avatar_url}
                      name={review.user.display_name || review.user.username}
                      size="sm"
                    />
                    <span className="text-sm font-medium text-fg">
                      {review.user.display_name || review.user.username}
                    </span>
                    <Rating average={review.rating} className="ml-auto" />
                  </div>
                  {review.comment ? (
                    <p className="text-sm text-fg-muted">{review.comment}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}

          {status === "authenticated" ? (
            writing ? (
              <ReviewForm
                slug={slug}
                onCancel={() => setWriting(false)}
                onPosted={() => {
                  setWriting(false);
                  reviews.refetch();
                  rating.refetch();
                }}
              />
            ) : (
              <div className="mt-5 border-t border-edge pt-4">
                <Button variant="secondary" onClick={() => setWriting(true)}>
                  <Icon name="ui/edit" tint className="size-4" /> เขียนรีวิว
                </Button>
              </div>
            )
          ) : status === "anonymous" ? (
            <p className="mt-5 border-t border-edge pt-4 text-sm text-fg-muted">
              <Link href="/login" className="underline hover:text-fg">
                เข้าสู่ระบบ
              </Link>{" "}
              เพื่อเขียนรีวิวสูตรนี้
            </p>
          ) : null}
        </CardBody>
      </Card>

      {/* ---------- Community posts about this recipe ---------- */}
      <RecipeCommunitySection recipe={recipe.data} />

      {/* ---------- Related ---------- */}
      {relatedItems.length > 0 ? (
        <section className="mt-10">
          <div className="mb-4">
            <h2 className="font-display text-xl font-medium text-fg">
              ถ้าชอบสูตรนี้ ลองต่อเลย
            </h2>
            <p className="text-sm text-fg-muted">{relatedReason}</p>
          </div>
          {/* The same card as the list page, at the same size. Stretching
              one card across the row put its title in the middle of an
              acre of nothing and its meta a screen away. */}
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {relatedItems.map((item) => (
              <RecipeCard key={item.slug} recipe={item} />
            ))}
          </div>
        </section>
      ) : null}
    </PageContainer>
  );
}

/* ------------------------------------------------------------------ */
/* Community posts about this recipe                                   */
/* ------------------------------------------------------------------ */

/**
 * The recipe ↔ community bridge.
 *
 * Reads only posts explicitly attached to this recipe
 * (`GET /gallery/?recipe_id=`), capped by one shared constant rather
 * than a number sprinkled through the UI. The compose link carries the
 * recipe so the post opens with it already attached  the user is still
 * creating a *community post*, which the copy says out loud.
 */
function RecipeCommunitySection({ recipe }: { recipe: RecipeDetail }) {
  const { status } = useAuth();
  const posts = useApiQuery(
    (signal) =>
      api.get<Paginated<GalleryPost>>("/gallery/", {
        query: {
          recipe_id: recipe.id,
          page_size: MAX_RECIPE_COMMUNITY_POSTS,
        },
        signal,
      }),
    [recipe.id],
  );

  const items = posts.data?.results ?? [];
  const total = posts.data?.count ?? 0;
  const composeHref =
    `/community/create?recipe=${recipe.id}&recipe_slug=${encodeURIComponent(recipe.slug)}` as "/community/create";

  return (
    <section className="mt-10">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-xl font-medium text-fg">
          โพสต์จากชุมชนเกี่ยวกับสูตรนี้
        </h2>
        {total > items.length ? (
          <Link
            href={`/community?recipe=${recipe.id}` as "/community"}
            className="text-sm text-accent hover:text-accent-hover"
          >
            ดูโพสต์ทั้งหมด ({total}) →
          </Link>
        ) : null}
      </div>

      {posts.loading ? (
        <Skeleton className="h-40 w-full rounded-surface" />
      ) : items.length === 0 ? (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-display font-medium text-fg">
                ยังไม่มีใครโพสต์เกี่ยวกับสูตรนี้
              </p>
              <p className="text-sm text-fg-muted">
                ถ้าคุณลองอบแล้ว มาเล่าให้ชุมชนฟังเป็นคนแรกสิ
              </p>
            </div>
            {status === "authenticated" ? (
              <Link href={composeHref}>
                <Button variant="secondary">แชร์ประสบการณ์เกี่ยวกับสูตรนี้</Button>
              </Link>
            ) : (
              <Link href="/login">
                <Button variant="secondary">เข้าสู่ระบบเพื่อแชร์</Button>
              </Link>
            )}
          </CardBody>
        </Card>
      ) : (
        <>
          <ul className="space-y-4">
            {items.map((post) => (
              <li key={post.id}>
                <CommunityPostCard post={post} />
              </li>
            ))}
          </ul>
          <div className="mt-4 text-center">
            {status === "authenticated" ? (
              <Link href={composeHref}>
                <Button variant="secondary">แชร์ประสบการณ์เกี่ยวกับสูตรนี้</Button>
              </Link>
            ) : (
              <Link href="/login">
                <Button variant="secondary">เข้าสู่ระบบเพื่อแชร์</Button>
              </Link>
            )}
          </div>
        </>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Ingredients and their substitutes                                   */
/* ------------------------------------------------------------------ */

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "มั่นใจสูง",
  medium: "ปานกลาง",
  low: "พอแทนได้",
};

/** Confidence reads as a dot before the name, so it never wraps to its
    own line when the name is long — the badges used to land in a
    different place on every row. */
const CONFIDENCE_DOT: Record<string, string> = {
  high: "bg-mint-ink",
  medium: "bg-butter-ink",
  low: "bg-peach-ink",
};

/** A ratio the scaler can honour by itself: same amount, other name. */
const ONE_TO_ONE = /^\s*1\s*:\s*1\s*$/;

/**
 * The substitution list for one ingredient.
 *
 * It sits directly under the ingredient it replaces rather than in a
 * drawer at the bottom of the card, so choosing one never costs the
 * reader their place in the list. Everything shown is registry data:
 * where the ratio is not 1:1 the conversion is quoted verbatim and *no
 * amount is computed*, because "3/4 ถ้วย ต่อเนย 1 ถ้วย" cannot be turned
 * into grams without inventing a density.
 */
function SubstitutionOptions({
  options,
  applied,
  onApply,
}: {
  options: SubstitutionOption[];
  applied?: SubstitutionOption;
  onApply: (option: SubstitutionOption) => void;
}) {
  return (
    <ul className="mt-1.5 space-y-2.5 rounded-control bg-surface-sunken/70 p-3">
      {options.map((option) => {
        const oneToOne = ONE_TO_ONE.test(option.ratio);
        const inUse = applied?.name === option.name;
        return (
          <li key={option.name} className="space-y-1">
            <p className="flex items-center gap-1.5">
              <span
                aria-hidden
                className={cn(
                  "size-2 shrink-0 rounded-full",
                  CONFIDENCE_DOT[option.confidence] ?? "bg-fg-subtle",
                )}
              />
              <span className="text-sm font-medium text-fg">{option.name}</span>
              {oneToOne ? (
                <Badge tone="mint" className="font-mono">
                  1:1
                </Badge>
              ) : null}
              <span className="ml-auto shrink-0 text-xs text-fg-muted">
                {CONFIDENCE_LABELS[option.confidence] ?? option.confidence}
              </span>
            </p>
            {oneToOne ? null : (
              <p className="pl-3.5 text-xs leading-relaxed text-fg-muted">
                {option.ratio}
              </p>
            )}
            {option.note ? (
              <p className="pl-3.5 text-xs text-fg-muted">{option.note}</p>
            ) : null}
            <div className="flex justify-end">
              <Button
                size="sm"
                variant="secondary"
                disabled={inUse}
                onClick={() => onApply(option)}
              >
                {inUse ? (
                  <>
                    <Icon name="ui/check" tint className="size-3.5" /> ใช้อยู่
                  </>
                ) : (
                  "ใช้แทน"
                )}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function IngredientRow({
  index,
  ingredient,
  amount,
  checked,
  onToggle,
  options,
  swap,
  open,
  onOpenChange,
  onApply,
  onClear,
}: {
  index: number;
  ingredient: Ingredient;
  amount: string | null;
  checked: boolean;
  onToggle: () => void;
  options: SubstitutionOption[];
  swap?: SubstitutionOption;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply: (option: SubstitutionOption) => void;
  onClear: () => void;
}) {
  const oneToOne = swap ? ONE_TO_ONE.test(swap.ratio) : false;
  // A 1:1 swap keeps the scaled amount; anything else states the amount
  // of the *original* ingredient plus the registry's conversion.
  const showAmountInline = amount !== null && (!swap || oneToOne);

  return (
    <li>
      <div className="rounded-control px-2 py-2 transition-colors hover:bg-surface-sunken">
        <div className="flex items-start gap-3">
          <input
            id={`ingredient-${index}`}
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            className="mt-0.5 size-5 shrink-0 accent-accent"
          />
          <div className="min-w-0 flex-1">
            <label
              htmlFor={`ingredient-${index}`}
              className={cn(
                "block cursor-pointer text-sm text-fg",
                checked && "line-through opacity-60",
              )}
            >
              {showAmountInline ? (
                <strong className="font-medium">{amount}</strong>
              ) : null}{" "}
              {swap ? swap.name : ingredient.name}
              {ingredient.is_optional ? (
                <span className="text-fg-subtle"> · ไม่ใส่ก็ได้</span>
              ) : null}
              {ingredient.note ? (
                <span className="text-fg-subtle"> ({ingredient.note})</span>
              ) : null}
            </label>

            {swap ? (
              <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-berry-ink">
                <Icon name="ui/swap" tint className="size-3.5" />
                <span>
                  ใช้แทน {ingredient.name}
                  {amount ? ` ${amount}` : ""}
                  {oneToOne ? "" : ` · ${swap.ratio}`}
                </span>
                <button
                  type="button"
                  onClick={onClear}
                  className="underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                >
                  คืนค่าเดิม
                </button>
              </p>
            ) : null}

            {options.length > 0 ? (
              <button
                type="button"
                aria-expanded={open}
                onClick={() => onOpenChange(!open)}
                className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
              >
                <Icon name="ui/swap" tint className="size-3.5" />
                {swap ? "เปลี่ยนของทดแทน" : "ของทดแทน"} ({options.length})
                <Icon
                  name="ui/chevron-down"
                  tint
                  className={cn("size-3.5 transition-transform", open && "rotate-180")}
                />
              </button>
            ) : null}

            {open ? (
              <SubstitutionOptions
                options={options}
                applied={swap}
                onApply={onApply}
              />
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
}

/* ------------------------------------------------------------------ */
/* Workspace                                                           */
/* ------------------------------------------------------------------ */

function Workspace({
  data,
  substitutions,
  focusRequest,
}: {
  data: RecipeDetail;
  substitutions: IngredientSubstitution[];
  /** Increments when the hero asks for focus mode. */
  focusRequest: number;
}) {
  const { toast } = useToast();
  const [session, setSession] = useState<BakeSession>(() =>
    loadSession(data.slug, data.servings),
  );
  const [timers, setTimers] = useState<BakeTimer[]>([]);
  const [focusOpen, setFocusOpen] = useState(false);
  const [focusIndex, setFocusIndex] = useState(0);
  /** Which ingredient's substitution list is open — one at a time. */
  const [openSubs, setOpenSubs] = useState<number | null>(null);
  /** Live feedback for the notes box: idle → saving → saved → idle. */
  const [noteState, setNoteState] = useState<"idle" | "saving" | "saved">("idle");

  // Persist the baking session per recipe, in this browser.
  useEffect(() => {
    try {
      window.localStorage.setItem(`kb-bake-${data.slug}`, JSON.stringify(session));
    } catch {
      // Storage full/blocked  the session simply won't survive reload.
    }
  }, [data.slug, session]);

  // Notes are written to storage by the effect above on every keystroke,
  // which is invisible. Say so: a note the baker cannot tell was kept is
  // a note they will retype somewhere safer.
  const noteTouched = useRef(false);
  useEffect(() => {
    if (!noteTouched.current) {
      noteTouched.current = true;
      return;
    }
    setNoteState("saving");
    const settle = setTimeout(() => setNoteState("saved"), 400);
    const fade = setTimeout(() => setNoteState("idle"), 3000);
    return () => {
      clearTimeout(settle);
      clearTimeout(fade);
    };
  }, [session.notes]);

  // One shared ticker drives every running timer; a timer that reaches
  // zero stops itself (the updater stays pure).
  useEffect(() => {
    if (!timers.some((timer) => timer.running)) return;
    const handle = setInterval(() => {
      setTimers((current) =>
        current.map((timer) => {
          if (!timer.running || timer.remaining === 0) return timer;
          const remaining = timer.remaining - 1;
          return { ...timer, remaining, running: remaining > 0 };
        }),
      );
    }, 1000);
    return () => clearInterval(handle);
  }, [timers]);

  // Announce each finished timer exactly once  tracked in a ref, so
  // this effect performs no state writes.
  const announcedRef = useRef<Set<number>>(new Set());
  useEffect(() => {
    for (const timer of timers) {
      if (timer.remaining === 0 && !announcedRef.current.has(timer.id)) {
        announcedRef.current.add(timer.id);
        toast(`${timer.label} ครบเวลาแล้ว!`, "success");
      }
    }
  }, [timers, toast]);

  const factor = session.servings / data.servings;
  const checked = new Set(session.checked);
  const done = new Set(session.done);
  const steps = data.steps;
  const activeStep = steps.findIndex((_, index) => !done.has(index));
  const doneCount = steps.filter((_, index) => done.has(index)).length;
  const stepPercent = steps.length
    ? Math.round((doneCount / steps.length) * 100)
    : 0;

  // Ingredients grouped by their stored stage (single group when unset).
  const groups = new Map<string, Array<{ ingredient: Ingredient; index: number }>>();
  data.ingredients.forEach((ingredient, index) => {
    const key = ingredient.group || "";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push({ ingredient, index });
  });

  // Substitution candidates keyed by the ingredient name the API echoed
  // back (it builds its entries from this recipe's own lines, so the
  // names match exactly; the fold is belt and braces).
  const subsByIngredient = new Map<string, SubstitutionOption[]>();
  for (const entry of substitutions) {
    if (entry.substitutions.length) {
      subsByIngredient.set(entry.ingredient.trim().toLowerCase(), [
        ...entry.substitutions,
      ]);
    }
  }
  const optionsFor = (name: string) =>
    subsByIngredient.get(name.trim().toLowerCase()) ?? [];
  const swappableCount = data.ingredients.filter(
    (ingredient) => optionsFor(ingredient.name).length > 0,
  ).length;

  function update(partial: Partial<BakeSession>) {
    setSession((current) => ({ ...current, ...partial }));
  }

  function applySwap(index: number, option: SubstitutionOption) {
    update({ swaps: { ...session.swaps, [String(index)]: option } });
    setOpenSubs(null);
  }

  function clearSwap(index: number) {
    const next = { ...session.swaps };
    delete next[String(index)];
    update({ swaps: next });
  }

  function toggleChecked(index: number) {
    const next = new Set(session.checked);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    update({ checked: [...next] });
  }

  function toggleDone(index: number) {
    const next = new Set(session.done);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    update({ done: [...next] });
  }

  function startTimer(label: string, minutes: number) {
    setTimers((current) => [
      ...current,
      {
        id: Date.now() + current.length,
        label,
        remaining: minutes * 60,
        running: true,
      },
    ]);
    toast(`เริ่มจับเวลา ${minutes} นาที`, "success");
  }

  function toggleTimer(id: number) {
    setTimers((current) =>
      current.map((timer) =>
        timer.id === id ? { ...timer, running: !timer.running } : timer,
      ),
    );
  }

  function dismissTimer(id: number) {
    setTimers((current) => current.filter((timer) => timer.id !== id));
  }

  const resumeAtRef = useRef(0);
  useEffect(() => {
    resumeAtRef.current = activeStep === -1 ? steps.length - 1 : activeStep;
  });
  useEffect(() => {
    if (focusRequest === 0) return;
    setFocusIndex(Math.max(0, resumeAtRef.current));
    setFocusOpen(true);
  }, [focusRequest]);

  return (
    <div id="workspace" className="mt-10 scroll-mt-32">
      <div className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        {/* ---------- Ingredients panel ----------
            The column flows at its natural height: a capped, scrollable
            column meant two scrollbars fighting each other and cut off
            the top of whatever card the box happened to start on. The
            ingredient card alone is sticky (below), which is the part
            you actually need in view while reading the method. */}
        {/* Not `self-start`: the column has to stretch to the row so the
            sticky card below has somewhere to travel. */}
        <div id="ingredients" className="space-y-4 scroll-mt-32">
          <Card>
            <CardHeader title="เวลาและการปรับสูตร" />
            <CardBody className="space-y-4">
              <dl className="grid gap-1 border-b border-edge pb-3 text-sm">
                {(
                  [
                    { icon: "timer", label: "เตรียม", value: `${data.prep_minutes} นาที` },
                    { icon: "fire", label: "อบ/ทำ", value: `${data.cook_minutes} นาที` },
                  ] as const
                ).map((item) => (
                  <div key={item.label} className="flex items-center gap-1.5">
                    <Icon name={`ui/${item.icon}`} tint className="size-4 text-fg-subtle" />
                    <dt className="text-fg-muted">{item.label}</dt>
                    <dd className="ml-auto font-medium text-fg">{item.value}</dd>
                  </div>
                ))}
              </dl>
              <div>
                <p className="mb-1.5 text-sm text-fg-muted">จำนวนที่จะทำ</p>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    aria-label="ลดจำนวน"
                    disabled={session.servings <= 1}
                    onClick={() =>
                      update({ servings: Math.max(1, session.servings - 1) })
                    }
                    className="flex size-11 items-center justify-center rounded-full bg-surface-sunken text-lg font-medium hover:bg-edge disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-focus"
                  >
                    −
                  </button>
                  <p className="min-w-16 text-center">
                    <span className="font-display text-2xl font-medium text-fg">
                      {session.servings}
                    </span>{" "}
                    <span className="text-sm text-fg-muted">ที่</span>
                  </p>
                  <button
                    type="button"
                    aria-label="เพิ่มจำนวน"
                    onClick={() => update({ servings: session.servings + 1 })}
                    className="flex size-11 items-center justify-center rounded-full bg-surface-sunken text-lg font-medium hover:bg-edge focus-visible:outline-2 focus-visible:outline-focus"
                  >
                    +
                  </button>
                  {session.servings !== data.servings ? (
                    <button
                      type="button"
                      onClick={() => update({ servings: data.servings })}
                      className="text-xs text-accent underline focus-visible:outline-2 focus-visible:outline-focus"
                    >
                      คืนค่าเดิม ({data.servings})
                    </button>
                  ) : null}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-sm text-fg-muted">หน่วยชั่งตวง</p>
                <div className="inline-flex rounded-full bg-surface-sunken p-1" role="group">
                  {(
                    [
                      ["metric", "กรัม/มล."],
                      ["imperial", "oz/lb"],
                    ] as const
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={session.unitSystem === value}
                      onClick={() => update({ unitSystem: value })}
                      className={cn(
                        "rounded-full px-4 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus",
                        session.unitSystem === value
                          ? "bg-surface font-medium text-fg shadow-raised"
                          : "text-fg-muted",
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {session.unitSystem === "imperial" ? (
                  <p className="mt-1.5 text-xs text-fg-subtle">
                    แปลงเฉพาะหน่วยชั่งตวงสากล| ช้อน/ฟอง คงเดิม
                  </p>
                ) : null}
              </div>
            </CardBody>
          </Card>

          <Card className="lg:sticky lg:top-32">
            <CardHeader
              title="ส่วนผสม"
              actions={
                <span className="text-sm text-fg-muted" aria-live="polite">
                  เตรียมแล้ว {checked.size}/{data.ingredients.length}
                </span>
              }
            />
            <CardBody className="space-y-4">
              {swappableCount > 0 ? (
                <p className="flex items-center gap-1.5 text-xs text-fg-muted">
                  <Icon name="ui/swap" tint className="size-3.5 text-accent" />
                  ขาดวัตถุดิบ? แตะ &ldquo;ของทดแทน&rdquo; ใต้รายการนั้นได้เลย
                  ({swappableCount} รายการมีตัวเลือก)
                </p>
              ) : null}

              {[...groups.entries()].map(([groupName, items], groupIndex) => (
                <div
                  key={groupName || "หลัก"}
                  className={cn(
                    groupIndex > 0 && "border-t border-edge pt-4",
                  )}
                >
                  {groupName ? (
                    <p className="font-display mb-1.5 text-sm font-medium text-berry-ink">
                      {groupName}
                    </p>
                  ) : null}
                  <ul className="space-y-0.5">
                    {items.map(({ ingredient, index }) => (
                      <IngredientRow
                        key={index}
                        index={index}
                        ingredient={ingredient}
                        amount={scaledQuantity(
                          ingredient,
                          factor,
                          session.unitSystem,
                        )}
                        checked={checked.has(index)}
                        onToggle={() => toggleChecked(index)}
                        options={optionsFor(ingredient.name)}
                        swap={session.swaps?.[String(index)]}
                        open={openSubs === index}
                        onOpenChange={(open) => setOpenSubs(open ? index : null)}
                        onApply={(option) => applySwap(index, option)}
                        onClear={() => clearSwap(index)}
                      />
                    ))}
                  </ul>
                </div>
              ))}
            </CardBody>
          </Card>
        </div>

        {/* ---------- Steps panel ---------- */}
        <div className="space-y-6" id="steps">
          <Card>
            <CardHeader title="วิธีทำ" />
            <CardBody>
              {/* One progress readout, not three: the bar and its own
                  caption. */}
              <p className="mb-1.5 flex items-center justify-between text-sm text-fg-muted">
                <span>ความคืบหน้า</span>
                <span aria-live="polite">
                  ทำแล้ว {doneCount} จาก {steps.length} ขั้น
                </span>
              </p>
              <ProgressBar
                percent={stepPercent}
                label={`ทำแล้ว ${doneCount} จาก ${steps.length} ขั้น`}
                className="mb-5"
              />
              <p className="mb-3 text-xs text-fg-subtle">
                แตะที่การ์ดขั้นตอนเพื่อทำเครื่องหมายว่าทำเสร็จแล้ว
              </p>
              <ol className="space-y-4">
                {steps.map((step, index) => {
                  const minutes = stepMinutes(step);
                  const isDone = done.has(index);
                  const isActive = index === activeStep;
                  return (
                    // The whole card is the target. A per-step checkbox
                    // with its own "ทำเสร็จแล้ว" label added a control
                    // row to every step for one bit of state; the number
                    // badge already had a place to show it.
                    <li
                      key={index}
                      onClick={(event) => {
                        // Anything genuinely clickable inside acts for
                        // itself (the timer, the number badge).
                        if ((event.target as HTMLElement).closest("button,a")) {
                          return;
                        }
                        toggleDone(index);
                      }}
                      className={cn(
                        "cursor-pointer rounded-surface border px-3 py-2.5 transition-colors",
                        isActive
                          ? "border-berry-ink/25 bg-berry-soft/50"
                          : "border-edge hover:bg-surface-sunken/60",
                        isDone && "opacity-60",
                      )}
                    >
                      <div className="flex gap-4">
                        <button
                          type="button"
                          role="checkbox"
                          aria-checked={isDone}
                          aria-label={`ขั้นที่ ${index + 1} ทำเสร็จแล้ว`}
                          onClick={() => toggleDone(index)}
                          className={cn(
                            "font-display flex size-11 shrink-0 items-center justify-center rounded-full text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                            isDone
                              ? "bg-mint-soft text-mint-ink"
                              : isActive
                                ? "bg-berry-ink text-fg-inverted"
                                : "bg-surface-sunken text-fg-muted",
                          )}
                        >
                          {isDone ? (
                            <Icon name="ui/check" tint className="size-5" />
                          ) : (
                            index + 1
                          )}
                        </button>
                        <div className="min-w-0 flex-1 space-y-2">
                          {isActive ? (
                            <p className="text-xs font-medium text-berry-ink">
                              ขั้นตอนปัจจุบัน
                            </p>
                          ) : null}
                          <p
                            className={cn(
                              "text-sm leading-relaxed text-fg",
                              isDone && "line-through",
                            )}
                          >
                            {step.body}
                          </p>
                          {step.image_url ? (
                            <div className="max-w-sm overflow-hidden rounded-control">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={step.image_url}
                                alt={`ภาพประกอบขั้นที่ ${index + 1}`}
                                loading="lazy"
                                className="w-full object-cover"
                              />
                            </div>
                          ) : null}
                          {minutes ? (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() =>
                                startTimer(`ขั้นที่ ${index + 1}`, minutes)
                              }
                            >
                              <Icon name="ui/timer" tint className="size-4" />
                              จับเวลา {minutes} นาที
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
              {activeStep === -1 && steps.length > 0 ? (
                <p className="mt-5 rounded-control bg-mint-soft px-4 py-3 text-center text-sm font-medium text-mint-ink">
                  <Icon name="ui/party" tint className="size-4 shrink-0" /> ทำครบทุกขั้นแล้ว อย่าลืมมารีวิวเล่าผลงานนะ
                </p>
              ) : null}
            </CardBody>
          </Card>

          {/* Personal notes */}
          <Card>
            <CardHeader
              title="โน้ตส่วนตัว"
              actions={
                <span
                  aria-live="polite"
                  className="flex items-center gap-1 text-xs"
                >
                  {noteState === "saved" ? (
                    <span className="flex items-center gap-1 text-success">
                      <Icon name="ui/check" tint className="size-3.5" />
                      บันทึกแล้ว
                    </span>
                  ) : noteState === "saving" ? (
                    <span className="text-fg-subtle">กำลังบันทึก…</span>
                  ) : null}
                </span>
              }
            />
            <CardBody>
              <Textarea
                value={session.notes}
                onChange={(event) => update({ notes: event.target.value })}
                placeholder={'เช่น "เตาบ้านเราต้องอบเพิ่ม 5 นาที" หรือ "ลดน้ำตาลลง 10g กำลังดี"'}
                rows={3}
              />
              <p className="mt-1.5 text-xs text-fg-subtle">
                บันทึกไว้ในเบราว์เซอร์เครื่องนี้เท่านั้น  แยกจากตัวสูตรจริง
              </p>
            </CardBody>
          </Card>

          {(session.checked.length > 0 ||
            session.done.length > 0 ||
            session.servings !== data.servings) ? (
            <p className="text-center">
              <button
                type="button"
                onClick={() =>
                  update({
                    checked: [],
                    done: [],
                    servings: data.servings,
                  })
                }
                className="text-xs text-fg-subtle underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
              >
                ล้างความคืบหน้าและเริ่มทำใหม่
              </button>
            </p>
          ) : null}
        </div>
      </div>

      {/* ---------- Focus mode ---------- */}
      {focusOpen && steps.length > 0 ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="โหมดทำขนม"
          className="fixed inset-0 z-50 flex flex-col bg-canvas"
        >
          <div className="flex items-center justify-between border-b border-edge px-4 py-3 sm:px-6">
            <p className="font-display font-medium text-fg">
              <Icon name="ui/chef-hat" tint className="size-4" /> ขั้นที่ {focusIndex + 1} จาก {steps.length}
            </p>
            <button
              type="button"
              onClick={() => setFocusOpen(false)}
              aria-label="ปิดโหมดทำขนม"
              className="flex size-11 items-center justify-center rounded-full hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
            >
              <Icon name="ui/close" tint className="size-4" />
            </button>
          </div>
          <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 overflow-y-auto px-6 py-8">
            <ProgressBar
              percent={Math.round(((focusIndex + 1) / steps.length) * 100)}
              label="ตำแหน่งขั้นตอน"
            />
            <p className="text-xl leading-relaxed text-fg sm:text-2xl">
              {steps[focusIndex].body}
            </p>
            {steps[focusIndex].image_url ? (
              <div className="overflow-hidden rounded-surface">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={steps[focusIndex].image_url!}
                  alt={`ภาพประกอบขั้นที่ ${focusIndex + 1}`}
                  className="w-full object-cover"
                />
              </div>
            ) : null}
            {stepMinutes(steps[focusIndex]) ? (
              <Button
                variant="secondary"
                size="lg"
                onClick={() =>
                  startTimer(
                    `ขั้นที่ ${focusIndex + 1}`,
                    stepMinutes(steps[focusIndex])!,
                  )
                }
              >
                <Icon name="ui/timer" tint className="size-5" />
                จับเวลา {stepMinutes(steps[focusIndex])} นาที
              </Button>
            ) : null}
          </div>
          <div className="border-t border-edge bg-surface px-4 py-4 sm:px-6">
            <div className="mx-auto flex w-full max-w-2xl gap-3">
              <Button
                variant="secondary"
                size="lg"
                disabled={focusIndex === 0}
                onClick={() => setFocusIndex((value) => Math.max(0, value - 1))}
              >
                ← ก่อนหน้า
              </Button>
              <Button
                size="lg"
                className="flex-1"
                onClick={() => {
                  if (!done.has(focusIndex)) toggleDone(focusIndex);
                  if (focusIndex < steps.length - 1) {
                    setFocusIndex(focusIndex + 1);
                  } else {
                    setFocusOpen(false);
                  }
                }}
              >
                {focusIndex < steps.length - 1
                  ? "ทำเสร็จแล้ว → ขั้นถัดไป"
                  : "เสร็จเรียบร้อย"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <TimerDock
        timers={timers}
        onToggle={toggleTimer}
        onDismiss={dismissTimer}
      />
    </div>
  );
}
