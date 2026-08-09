"use client";

/**
 * Achievements — the badge collection.
 *
 * Two endpoints, and the split between them is the whole design:
 *   - `GET /achievements/` is the badge **catalogue** — what exists to
 *     earn (system-owned display metadata, ADR 0024).
 *   - `GET /me/achievements/` is the **ledger** — append-only facts about
 *     what this caller earned, and when.
 *
 * Locked badges are catalogue entries with no matching fact. The frontend
 * decides nothing about earning: it joins the two lists on `slug` and
 * renders. No status is computed, stored or guessed here.
 *
 * No progress bar appears on a locked badge because no endpoint reports
 * partial progress toward one — the unlock condition is shown instead.
 * The skill card uses the real gamification standing, including the
 * server-stated `xp_for_next_level`, so the level curve is never
 * restated on this side.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Route } from "next";

import { api, type Paginated } from "@/lib/api/client";
import type { Achievement, GamificationSummary, Schemas } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

type Badge = Schemas["Badge"];

/* ------------------------------------------------------------------ */
/* Presentation grouping                                               */
/* ------------------------------------------------------------------ */

/**
 * Badge definitions carry no category field, so grouping is derived from
 * the slug — a presentation convenience that lives here and is never
 * pushed back into the API model. An unknown slug simply lands in
 * "อื่น ๆ" rather than inventing a bucket for it.
 */
const GROUPS: Record<string, string> = {
  course_completed: "courses",
  first_course: "courses",
  ten_courses: "courses",
  quiz_master: "quizzes",
  recipe_author: "recipes",
};

const GROUP_LABELS: Array<{ key: string; label: string }> = [
  { key: "all", label: "ทั้งหมด" },
  { key: "courses", label: "คอร์ส" },
  { key: "quizzes", label: "แบบทดสอบ" },
  { key: "recipes", label: "สูตรอาหาร" },
  { key: "other", label: "อื่น ๆ" },
];

function groupOf(slug: string): string {
  return GROUPS[slug] ?? "other";
}

/** Only routes that exist — a badge never links somewhere invented. */
const NEXT_STEP: Record<string, { href: Route; label: string }> = {
  course_completed: { href: "/courses", label: "ไปเรียนคอร์ส" },
  first_course: { href: "/courses", label: "เริ่มคอร์สแรก" },
  ten_courses: { href: "/courses", label: "ดูคอร์สทั้งหมด" },
  // Quizzes live inside lessons, so the course catalogue is the honest
  // way in — there is no standalone quiz route.
  quiz_master: { href: "/courses", label: "ไปทำแบบทดสอบในบทเรียน" },
  recipe_author: { href: "/recipes/create", label: "เขียนสูตรของคุณ" },
};

const TONES = [
  "bg-berry-soft text-berry-ink",
  "bg-peach-soft text-peach-ink",
  "bg-butter-soft text-butter-ink",
  "bg-lavender-soft text-lavender-ink",
  "bg-mint-soft text-mint-ink",
];

function toneFor(slug: string): string {
  let hash = 0;
  for (const char of slug) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return TONES[hash % TONES.length];
}

function thaiDate(iso: string): string {
  return new Date(iso).toLocaleDateString("th-TH", { dateStyle: "long" });
}

/* ------------------------------------------------------------------ */
/* Joined view model                                                   */
/* ------------------------------------------------------------------ */

interface BadgeState {
  badge: Badge;
  /** The earned fact, when the ledger has one for this slug. */
  earned: Achievement | null;
}

/* ------------------------------------------------------------------ */
/* Celebration                                                         */
/* ------------------------------------------------------------------ */

const SPRINKLES = ["🧁", "🍪", "✨", "🍰", "⭐", "🍩", "✨", "🥐"];

function Sprinkles() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {SPRINKLES.map((glyph, index) => (
        <span
          key={index}
          className="kb-sprinkle absolute text-lg"
          style={{
            left: `${8 + index * 11}%`,
            animationDelay: `${index * 70}ms`,
            ["--kb-spin" as string]: `${index % 2 ? 240 : -200}deg`,
          }}
        >
          {glyph}
        </span>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Detail dialog                                                       */
/* ------------------------------------------------------------------ */

function BadgeDetail({
  state,
  onClose,
}: {
  state: BadgeState | null;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (state && !element.open) element.showModal();
    if (!state && element.open) element.close();
  }, [state]);

  const earned = state?.earned ?? null;
  const step = state ? NEXT_STEP[state.badge.slug] : undefined;

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) onClose();
      }}
      aria-label={state ? `รายละเอียดเหรียญ ${state.badge.title_th}` : "รายละเอียดเหรียญ"}
      className={cn(
        "border border-edge bg-surface-raised p-0 shadow-overlay backdrop:bg-black/40",
        // Bottom sheet on phones, centred card from sm up.
        "m-0 mt-auto w-full max-w-full rounded-t-surface",
        "sm:m-auto sm:w-full sm:max-w-sm sm:rounded-surface",
      )}
    >
      {state ? (
        <div className="relative">
          {earned ? <Sprinkles /> : null}
          <div className="px-6 pb-6 pt-7 text-center">
            <span
              aria-hidden
              className={cn(
                "mx-auto flex size-24 items-center justify-center rounded-full text-5xl",
                earned
                  ? cn(toneFor(state.badge.slug), "kb-badge-pop shadow-raised")
                  : "bg-surface-sunken grayscale",
              )}
            >
              {earned ? state.badge.icon || "🏅" : "🔒"}
            </span>

            <h2 className="font-display mt-4 text-lg font-medium text-fg">
              {state.badge.title_th}
            </h2>
            <p className="text-xs text-fg-subtle">{state.badge.title_en}</p>

            <p className="mt-3 text-sm text-fg-muted">
              {state.badge.description_th || state.badge.description_en}
            </p>

            {earned ? (
              <div className="mt-4 rounded-control bg-success-subtle px-3 py-2">
                <p className="text-sm font-medium text-success">✓ ปลดล็อกแล้ว</p>
                <p className="text-xs text-fg-muted">
                  ได้รับเมื่อ {thaiDate(earned.awarded_at)}
                </p>
              </div>
            ) : (
              <div className="mt-4 rounded-control bg-surface-sunken px-3 py-2 text-left">
                <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
                  เงื่อนไขการปลดล็อก
                </p>
                <p className="mt-0.5 text-sm text-fg">
                  {state.badge.description_th || state.badge.description_en}
                </p>
              </div>
            )}

            <div className="mt-5 flex justify-center gap-2">
              {!earned && step ? (
                <Link href={step.href}>
                  <Button size="sm">{step.label}</Button>
                </Link>
              ) : null}
              <Button size="sm" variant="secondary" onClick={onClose}>
                ปิด
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Badge card                                                          */
/* ------------------------------------------------------------------ */

function BadgeCard({
  state,
  onOpen,
}: {
  state: BadgeState;
  onOpen: () => void;
}) {
  const earned = state.earned !== null;
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`${state.badge.title_th} — ${earned ? "ปลดล็อกแล้ว" : "ยังไม่ปลดล็อก"}`}
      className="group h-full w-full text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Card
        className={cn(
          "flex h-full flex-col items-center gap-2 p-4 text-center transition-transform duration-150 group-hover:-translate-y-0.5",
          earned ? "shadow-raised" : "border-dashed bg-surface/70",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "relative flex size-16 items-center justify-center rounded-full text-3xl",
            earned
              ? cn(toneFor(state.badge.slug), "shadow-raised")
              : "bg-surface-sunken text-fg-subtle grayscale",
          )}
        >
          {earned ? state.badge.icon || "🏅" : state.badge.icon || "🏅"}
          {!earned ? (
            <span className="absolute -bottom-0.5 -right-0.5 flex size-6 items-center justify-center rounded-full bg-surface text-xs shadow-raised">
              🔒
            </span>
          ) : null}
        </span>

        <h3
          className={cn(
            "font-display text-sm font-medium",
            earned ? "text-fg" : "text-fg-muted",
          )}
        >
          {state.badge.title_th}
        </h3>
        <p className="line-clamp-2 text-xs text-fg-muted">
          {state.badge.description_th}
        </p>
        <p className="mt-auto pt-1 text-xs">
          {earned ? (
            <span className="text-success">
              ✓ {thaiDate(state.earned!.awarded_at)}
            </span>
          ) : (
            <span className="text-fg-subtle">รอให้คุณปลดล็อก</span>
          )}
        </p>
      </Card>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function AchievementsContent() {
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState<BadgeState | null>(null);
  const [syncing, setSyncing] = useState(false);

  const catalog = useApiQuery(
    (signal) => api.get<Badge[]>("/achievements/", { signal }),
    [],
  );
  const mine = useApiQuery(
    (signal) =>
      api.get<Paginated<Achievement>>("/me/achievements/", {
        query: { page_size: 100 },
        signal,
      }),
    [],
  );
  const standing = useApiQuery(
    (signal) => api.get<GamificationSummary>("/me/gamification/", { signal }),
    [],
  );

  const loading = catalog.loading || mine.loading;
  const error = catalog.error ?? mine.error;

  // Join catalogue × ledger on slug. The ledger's `achievement_type` is
  // the same identity as the badge slug, and an earned achievement whose
  // badge was deactivated still counts — it just has no catalogue row.
  const earnedByType = new Map(
    (mine.data?.results ?? []).map((row) => [row.achievement_type, row]),
  );
  const states: BadgeState[] = (catalog.data ?? []).map((badge) => ({
    badge,
    earned: earnedByType.get(badge.slug) ?? null,
  }));

  const earnedCount = states.filter((state) => state.earned).length;
  const total = states.length;
  const percent = total > 0 ? Math.round((earnedCount / total) * 100) : 0;

  const visible = states.filter(
    (state) => filter === "all" || groupOf(state.badge.slug) === filter,
  );
  const unlocked = visible.filter((state) => state.earned);
  const locked = visible.filter((state) => !state.earned);

  // Only offer a filter the catalogue actually has badges for.
  const availableGroups = new Set(states.map((state) => groupOf(state.badge.slug)));

  const level = standing.data?.level;

  if (error) {
    return (
      <Card>
        <CardBody className="py-10 text-center">
          <p aria-hidden className="text-4xl">
            🏆
          </p>
          <p className="font-display mt-3 font-medium text-fg">
            โหลดความสำเร็จไม่สำเร็จ
          </p>
          <div className="mt-4">
            <ErrorState
              error={error}
              onRetry={() => {
                catalog.refetch();
                mine.refetch();
              }}
            />
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <>
      {/* ---- Header ------------------------------------------------ */}
      <header className="mb-6">
        <h1 className="font-display text-2xl font-medium text-fg sm:text-3xl">
          ความสำเร็จของฉัน 🏆
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          ทุกครั้งที่คุณเรียนรู้และลงมือทำ คืออีกหนึ่งก้าวของนักอบขนม
        </p>

        {loading ? (
          <Skeleton className="mt-4 h-16 w-full max-w-md rounded-surface" />
        ) : (
          <div className="mt-4 max-w-md">
            <p className="flex items-baseline gap-2">
              <span className="font-display text-2xl font-medium text-fg">
                {earnedCount} / {total}
              </span>
              <span className="text-sm text-fg-muted">ปลดล็อกแล้ว</span>
              <span className="ml-auto text-sm font-medium text-accent">
                {percent}%
              </span>
            </p>
            <div
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="ความคืบหน้าการปลดล็อกความสำเร็จ"
              className="mt-1.5 h-3 w-full overflow-hidden rounded-full bg-surface-sunken"
            >
              <div
                className="h-full rounded-full bg-accent/80 transition-[width] duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
        )}
      </header>

      {/* ---- Skill standing ---------------------------------------- */}
      {level ? (
        <Card className="kb-hero mb-6 border-none">
          <CardBody className="flex flex-wrap items-center gap-5">
            <div>
              <p className="text-xs uppercase tracking-wide text-fg-subtle">
                เส้นทางนักอบขนม
              </p>
              <p className="font-display text-xl font-medium text-fg">
                เลเวล {level.current_level}
              </p>
              <p className="text-xs text-fg-muted">
                สะสมทั้งหมด {level.total_xp} XP
              </p>
            </div>

            <div className="min-w-48 flex-1">
              <p className="flex justify-between text-xs text-fg-muted">
                <span>ความคืบหน้าสู่เลเวล {level.current_level + 1}</span>
                <span className="font-mono">
                  {level.current_xp}/{level.xp_for_next_level} XP
                </span>
              </p>
              {/* A rising-dough bar: the fill is the dough, and the
                  denominator comes from the server (ADR 0024). */}
              <div
                role="progressbar"
                aria-valuenow={level.current_xp}
                aria-valuemin={0}
                aria-valuemax={level.xp_for_next_level}
                aria-label={`ความคืบหน้าสู่เลเวล ${level.current_level + 1}`}
                className="mt-1 flex h-6 w-full items-end overflow-hidden rounded-full border border-edge bg-surface"
              >
                <div
                  className="h-full rounded-full bg-butter-soft transition-[width] duration-500"
                  style={{
                    width: `${Math.min(100, Math.round((level.current_xp / Math.max(1, level.xp_for_next_level)) * 100))}%`,
                  }}
                />
              </div>
            </div>

            {standing.data?.streak ? (
              <div className="text-center">
                <p className="text-2xl" aria-hidden>
                  🔥
                </p>
                <p className="text-sm font-medium text-fg">
                  {standing.data.streak.current} วัน
                </p>
                <p className="text-xs text-fg-subtle">ต่อเนื่อง</p>
              </div>
            ) : null}

            {/* XP is derived from the domains' facts on demand, so an
                account whose activity predates the ledger reads zero
                until it is reconciled. This is the backend's own
                idempotent rebuild — not a client-side calculation. */}
            <div className="w-full sm:w-auto">
              <Button
                size="sm"
                variant="ghost"
                loading={syncing}
                onClick={async () => {
                  setSyncing(true);
                  try {
                    await api.post("/me/gamification/recalculate/");
                    standing.refetch();
                  } finally {
                    setSyncing(false);
                  }
                }}
              >
                ↻ คำนวณคะแนนใหม่
              </Button>
            </div>
          </CardBody>
        </Card>
      ) : null}

      {/* ---- Filters ------------------------------------------------ */}
      {!loading && total > 0 ? (
        <div
          role="group"
          aria-label="กรองความสำเร็จตามหมวด"
          className="-mx-1 mb-5 flex gap-2 overflow-x-auto px-1 pb-1"
        >
          {GROUP_LABELS.filter(
            (group) => group.key === "all" || availableGroups.has(group.key),
          ).map((group) => (
            <button
              key={group.key}
              type="button"
              aria-pressed={filter === group.key}
              onClick={() => setFilter(group.key)}
              className={cn(
                "shrink-0 whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                filter === group.key
                  ? "border-accent bg-accent-subtle font-medium text-fg"
                  : "border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
              )}
            >
              {group.label}
            </button>
          ))}
        </div>
      ) : null}

      {/* ---- Grids -------------------------------------------------- */}
      {loading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" aria-busy="true">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="h-48 w-full rounded-surface" />
          ))}
        </div>
      ) : total === 0 ? (
        <Card>
          <EmptyState
            icon="🧁"
            title="ยังไม่มีเหรียญให้เก็บในตอนนี้"
            description="ทีมงานกำลังเตรียมความสำเร็จชุดใหม่ให้คุณ"
          />
        </Card>
      ) : earnedCount === 0 ? (
        <>
          <Card className="mb-6">
            <EmptyState
              icon="🧁"
              title="เส้นทางนักอบขนมของคุณกำลังเริ่มต้น 🧁"
              description="เรียนคอร์สแรก ทำสูตรแรก หรือเริ่มบทเรียนเพื่อปลดล็อกความสำเร็จ"
              action={
                <Link href="/courses">
                  <Button>เริ่มเรียน</Button>
                </Link>
              }
            />
          </Card>
          <LockedSection locked={locked} onOpen={setOpen} />
        </>
      ) : (
        <div className="space-y-8">
          {unlocked.length > 0 ? (
            <section>
              <h2 className="font-display mb-3 text-lg font-medium text-fg">
                ปลดล็อกแล้ว ✨{" "}
                <span className="text-sm font-normal text-fg-muted">
                  {unlocked.length} เหรียญ
                </span>
              </h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {unlocked.map((state) => (
                  <BadgeCard
                    key={state.badge.slug}
                    state={state}
                    onOpen={() => setOpen(state)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <LockedSection locked={locked} onOpen={setOpen} />
        </div>
      )}

      <BadgeDetail state={open} onClose={() => setOpen(null)} />
    </>
  );
}

function LockedSection({
  locked,
  onOpen,
}: {
  locked: BadgeState[];
  onOpen: (state: BadgeState) => void;
}) {
  if (locked.length === 0) {
    return (
      <Card>
        <CardBody className="py-8 text-center">
          <p aria-hidden className="text-3xl">
            🎉
          </p>
          <p className="font-display mt-2 font-medium text-fg">
            เก็บครบทุกเหรียญในหมวดนี้แล้ว!
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <section>
      <h2 className="font-display mb-1 text-lg font-medium text-fg">
        รอให้คุณปลดล็อก 🔒{" "}
        <span className="text-sm font-normal text-fg-muted">
          {locked.length} เหรียญ
        </span>
      </h2>
      <p className="mb-3 text-xs text-fg-subtle">
        แตะเหรียญเพื่อดูเงื่อนไขการปลดล็อก
      </p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {locked.map((state) => (
          <BadgeCard
            key={state.badge.slug}
            state={state}
            onOpen={() => onOpen(state)}
          />
        ))}
      </div>
    </section>
  );
}

export default function AchievementsPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <AchievementsContent />
      </RequireAuth>
    </PageContainer>
  );
}
