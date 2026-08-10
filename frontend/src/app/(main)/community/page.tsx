"use client";

/**
 * The community feed — KawaiiBake's photo-first baking space.
 *
 * Everything on this page is backed by `GET /gallery/`, whose real
 * filters are `recipe_id`, `course_id`, `author` and `category` (the
 * *attached recipe's* category). Those are what the chip bar offers.
 *
 * Deliberately absent, because the gallery app has no such data:
 * post types beyond "has a recipe attached", free tags, a popularity
 * sort (the feed is newest-first, full stop), likes, comments and
 * bookmarks. Each is reported rather than mocked.
 *
 * The composer expands in place — writing a post never leaves the feed —
 * and a freshly published post is prepended immediately, so the feed
 * reflects the write without a full refetch.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Category,
  GalleryPost,
  RecipeListItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { CommunityPostCard } from "@/components/community/post-card";
import { PostComposerForm } from "@/components/community/post-composer-form";
import { Icon } from "@/components/ui/icon";
import { CategoryTile } from "@/components/content/category-tile";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 10;

/* ------------------------------------------------------------------ */
/* Skeletons                                                           */
/* ------------------------------------------------------------------ */

function PostSkeleton() {
  return (
    <Card className="overflow-hidden" aria-hidden>
      <div className="flex items-center gap-3 p-4">
        <Skeleton className="size-13 rounded-full" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-3.5 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <div className="px-4">
        <Skeleton className="h-4 w-3/4" />
      </div>
      {/* A photo placeholder, not a full square: a real card's image is
          capped, and a viewport-tall grey block reads as a broken page. */}
      <Skeleton className="mt-3 h-56 w-full rounded-none" />
      <div className="p-4">
        <Skeleton className="h-9 w-40 rounded-full" />
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Composer                                                            */
/* ------------------------------------------------------------------ */

function InlineComposer({ onPublished }: { onPublished: (post: GalleryPost) => void }) {
  const { status, user } = useAuth();
  const [open, setOpen] = useState(false);

  if (status === "anonymous") {
    return (
      <Card>
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
            <Button>เข้าสู่ระบบเพื่อสร้างโพสต์</Button>
          </Link>
        </CardBody>
      </Card>
    );
  }

  if (status !== "authenticated") return null;

  const displayName = user?.display_name || user?.username || "คุณ";

  if (!open) {
    return (
      <Card>
        <CardBody className="space-y-3">
          <div className="flex items-center gap-3">
            <Avatar src={user?.avatar_url} name={displayName} />
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="flex-1 rounded-full bg-surface-sunken px-4 py-2.5 text-left text-sm text-fg-subtle transition-colors hover:bg-accent-subtle hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              มีอะไรอยากแบ่งปันเกี่ยวกับการทำขนม?
            </button>
          </div>
          <div className="flex flex-wrap gap-2 border-t border-edge pt-3">
            {[
              { icon: "ui/camera" as const, label: "รูปภาพ" },
              { icon: "ui/paperclip" as const, label: "แนบสูตร" },
            ].map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => setOpen(true)}
                className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
              >
                <Icon name={item.icon} className="size-4" />
                {item.label}
              </button>
            ))}
            <Button
              size="sm"
              className="ml-auto"
              onClick={() => setOpen(true)}
            >
              + สร้างโพสต์
            </Button>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <h2 className="font-display mb-3 text-base font-medium text-fg">
          สร้างโพสต์
        </h2>
        <PostComposerForm
          autoFocus
          onCancel={() => setOpen(false)}
          onPublished={(post) => {
            setOpen(false);
            onPublished(post);
          }}
        />
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Feed                                                                */
/* ------------------------------------------------------------------ */

function CommunityFeed() {
  const params = useSearchParams();
  const router = useRouter();
  const { status } = useAuth();

  const recipeId = params.get("recipe");
  const category = params.get("category");
  const author = params.get("author");

  const [page, setPage] = useState(1);
  const [fresh, setFresh] = useState<GalleryPost[]>([]);

  const feed = useApiQuery(
    (signal) =>
      api.get<Paginated<GalleryPost>>("/gallery/", {
        query: {
          recipe_id: recipeId ?? undefined,
          category: category ?? undefined,
          author: author ?? undefined,
          page,
          page_size: PAGE_SIZE,
        },
        signal,
      }),
    [recipeId, category, author, page],
  );

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  // One list read enriches every attachment on the page. The public feed
  // is exactly the set a viewer may open, so a recipe missing from it
  // correctly falls back to the compact chip.
  const recipes = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { page_size: 100 },
        signal,
      }),
    [],
  );
  const recipeBySlug = new Map(
    (recipes.data?.results ?? []).map((recipe) => [recipe.slug, recipe]),
  );

  function setFilter(next: Record<string, string | null>) {
    const query = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value === null) query.delete(key);
      else query.set(key, value);
    }
    setPage(1);
    setFresh([]);
    router.replace(`/community${query.size ? `?${query}` : ""}` as "/community", {
      scroll: false,
    });
  }

  const serverPosts = feed.data?.results ?? [];
  // Posts published in this session lead the feed until the next fetch.
  const posts = page === 1 ? [...fresh, ...serverPosts] : serverPosts;
  const pages = Math.max(1, Math.ceil((feed.data?.count ?? 0) / PAGE_SIZE));
  const filtered = Boolean(recipeId || category || author);

  const activeCategoryName =
    categories.data?.find((item) => item.slug === category)?.name ?? category;

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,42rem)_18rem] lg:justify-center lg:gap-8">
      <div className="mx-auto w-full max-w-2xl lg:mx-0">
        {/* ---- Hero ---------------------------------------------- */}
        <header className="kb-hero mb-5 rounded-surface px-5 py-6 sm:px-7 sm:py-8">
          <h1 className="font-display text-2xl font-medium text-fg sm:text-3xl">
            ชุมชนคนรักการอบขนม
          </h1>
          <p className="mt-1.5 max-w-lg text-sm text-fg-muted">
            มาแบ่งปันผลงาน ถามคำถาม และเรียนรู้เรื่องอบขนมไปด้วยกัน
          </p>
          <div className="mt-4">
            {status === "authenticated" ? (
              <Link href="/community/create">
                <Button>+ สร้างโพสต์</Button>
              </Link>
            ) : status === "anonymous" ? (
              <Link href="/login">
                <Button>เข้าสู่ระบบเพื่อสร้างโพสต์</Button>
              </Link>
            ) : null}
          </div>
        </header>

        {/* ---- Composer ------------------------------------------ */}
        <div className="mb-5">
          <InlineComposer
            onPublished={(post) => setFresh((current) => [post, ...current])}
          />
        </div>

        {/* ---- Filters ------------------------------------------- */}
        <div className="mb-4">
          <div
            role="group"
            aria-label="กรองโพสต์ตามหมวดของสูตรที่แนบ"
            className="-mx-1 flex snap-x items-start gap-2.5 overflow-x-auto px-1 pb-1"
          >
            <button
              type="button"
              aria-pressed={!category}
              onClick={() => setFilter({ category: null })}
              className={cn(
                "flex aspect-square w-20 shrink-0 snap-start items-center justify-center rounded-surface text-sm font-medium shadow-raised transition-colors sm:w-24",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                !category
                  ? "bg-accent text-fg-inverted"
                  : "bg-surface text-fg-muted hover:text-fg",
              )}
            >
              ทั้งหมด
            </button>
            {(categories.data ?? []).map((item) => (
              <CategoryTile
                key={item.slug}
                compact
                slug={item.slug}
                name={item.name}
                active={category === item.slug}
                onClick={() =>
                  setFilter({ category: category === item.slug ? null : item.slug })
                }
              />
            ))}
          </div>
          <p className="mt-1.5 text-xs text-fg-subtle">
            เรียงจากใหม่ไปเก่า — หมวดกรองจากสูตรที่โพสต์แนบไว้
          </p>
        </div>

        {/* ---- Active filter summary ----------------------------- */}
        {filtered ? (
          <Card className="mb-4">
            <CardBody className="flex flex-wrap items-center gap-2 py-3">
              <span className="text-sm text-fg-muted">
                {recipeId ? "กำลังดูโพสต์ที่แนบสูตรนี้" : null}
                {category ? `หมวด ${activeCategoryName}` : null}
                {author ? `โพสต์ของ @${author}` : null}
              </span>
              <button
                type="button"
                onClick={() =>
                  setFilter({ recipe: null, category: null, author: null })
                }
                className="ml-auto text-sm text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
              >
                ล้างตัวกรอง
              </button>
            </CardBody>
          </Card>
        ) : null}

        {/* ---- Feed ---------------------------------------------- */}
        <div aria-live="polite" aria-busy={feed.loading}>
          {feed.loading && posts.length === 0 ? (
            <div className="space-y-4">
              <PostSkeleton />
              <PostSkeleton />
              <PostSkeleton />
            </div>
          ) : feed.error ? (
            <Card>
              <CardBody className="py-10 text-center">
                <p className="font-display mt-3 font-medium text-fg">
                  ไม่สามารถโหลดโพสต์ได้
                </p>
                <div className="mt-4">
                  <ErrorState error={feed.error} onRetry={feed.refetch} />
                </div>
              </CardBody>
            </Card>
          ) : posts.length === 0 ? (
            <Card>
              <CardBody className="flex flex-col items-center gap-3 py-14 text-center">
                <p className="font-display text-base font-medium text-fg">
                  {filtered ? "ยังไม่มีโพสต์ในหมวดนี้" : "ยังไม่มีโพสต์ในชุมชน"}
                </p>
                <p className="max-w-sm text-sm text-fg-muted">
                  มาเป็นคนแรกที่แบ่งปันผลงานกันไหม?
                </p>
                {status === "authenticated" ? (
                  <Link href="/community/create">
                    <Button>+ สร้างโพสต์</Button>
                  </Link>
                ) : (
                  <Link href="/login">
                    <Button>เข้าสู่ระบบเพื่อสร้างโพสต์</Button>
                  </Link>
                )}
              </CardBody>
            </Card>
          ) : (
            <>
              <ul className="space-y-4">
                {posts.map((post) => (
                  <li key={post.id}>
                    <CommunityPostCard
                      post={post}
                      recipeDetails={
                        post.recipe
                          ? (recipeBySlug.get(post.recipe.slug) ?? null)
                          : null
                      }
                    />
                  </li>
                ))}
              </ul>

              {pages > 1 ? (
                <nav
                  aria-label="หน้าของฟีดชุมชน"
                  className="mt-6 flex items-center justify-center gap-3"
                >
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((value) => value - 1)}
                  >
                    ← ใหม่กว่า
                  </Button>
                  <span className="text-sm text-fg-muted">
                    หน้า {page} / {pages}
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page >= pages}
                    onClick={() => setPage((value) => value + 1)}
                  >
                    เก่ากว่า →
                  </Button>
                </nav>
              ) : null}
            </>
          )}
        </div>

        <p className="mt-8 text-center text-sm text-fg-muted">
          มีสูตรใหม่อยากแบ่งปัน?{" "}
          <Link href="/recipes/create" className="text-accent hover:underline">
            สร้างสูตรอาหาร
          </Link>
        </p>
      </div>

      {/* ---- Sidebar (desktop only) ------------------------------ */}
      <aside className="hidden lg:block">
        <div className="sticky top-20 space-y-4">
          <Card>
            <CardBody>
              <h2 className="font-display text-sm font-medium text-fg">
                หมวดที่ชุมชนกำลังแชร์
              </h2>
              <p className="mt-0.5 text-xs text-fg-subtle">
                จากหมวดของสูตรที่โพสต์แนบไว้
              </p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {(categories.data ?? []).slice(0, 8).map((item) => (
                  <li key={item.slug}>
                    <button
                      type="button"
                      onClick={() => setFilter({ category: item.slug })}
                      className={cn(
                        "rounded-full px-2.5 py-1 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-focus",
                        category === item.slug
                          ? "bg-accent-subtle font-medium text-fg"
                          : "bg-surface-sunken text-fg-muted hover:text-fg",
                      )}
                    >
                      #{item.name}
                    </button>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>

          <RecentBakers
            posts={posts}
            active={author}
            onPick={(handle) =>
              setFilter({ author: author === handle ? null : handle })
            }
          />

          <Card>
            <CardBody className="space-y-2 text-xs text-fg-muted">
              <p className="font-display text-sm font-medium text-fg">
                เกี่ยวกับชุมชนนี้
              </p>
              <p>
                แชร์ผลงานของคุณ ถามเทคนิค หรือแนบสูตรที่ใช้ก็ได้ ทุกโพสต์จะแสดงเป็นสาธารณะ
              </p>
              <p>
                ตอนนี้ระบบไลก์ คอมเมนต์ และบันทึกโพสต์ยังไม่เปิดให้ใช้งาน
              </p>
            </CardBody>
          </Card>
        </div>
      </aside>
    </div>
  );
}

/**
 * Bakers who appear in the posts currently loaded — a real, visible fact,
 * not a follower ranking. No follow graph exists, so nothing here claims
 * one.
 */
function RecentBakers({
  posts,
  active,
  onPick,
}: {
  posts: GalleryPost[];
  active: string | null;
  onPick: (handle: string) => void;
}) {
  // Filtering is by handle (the API's `?author=` takes a username), but
  // the avatar and label shown are the real display name and photo — the
  // handle stays the unique key underneath.
  const bakers = new Map<string, { displayName: string; avatarUrl: string | null }>();
  for (const post of posts) {
    if (!bakers.has(post.author_handle)) {
      bakers.set(post.author_handle, {
        displayName: post.author_display_name,
        avatarUrl: post.author_avatar_url,
      });
    }
  }
  const entries = [...bakers.entries()].slice(0, 6);
  if (entries.length === 0) return null;

  return (
    <Card>
      <CardBody>
        <h2 className="font-display text-sm font-medium text-fg">
          นักอบขนมในฟีดนี้
        </h2>
        <ul className="mt-3 space-y-1">
          {entries.map(([handle, baker]) => (
            <li key={handle}>
              <button
                type="button"
                onClick={() => onPick(handle)}
                aria-pressed={active === handle}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-control px-2 py-1.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-focus",
                  active === handle
                    ? "bg-accent-subtle"
                    : "hover:bg-surface-sunken",
                )}
              >
                <Avatar src={baker.avatarUrl} name={baker.displayName} size="sm" />
                <span className="min-w-0 flex-1 truncate text-sm text-fg">
                  {baker.displayName}
                </span>
                {active === handle ? (
                  <span className="shrink-0 text-xs text-accent">กำลังดู</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

export default function CommunityPage() {
  return (
    <PageContainer>
      <Suspense
        fallback={
          <div className="mx-auto max-w-2xl space-y-4">
            <Skeleton className="h-40 w-full rounded-surface" />
            <PostSkeleton />
          </div>
        }
      >
        <CommunityFeed />
      </Suspense>
    </PageContainer>
  );
}
