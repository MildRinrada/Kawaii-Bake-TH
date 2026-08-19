"use client";

/**
 * The community feed  KawaiiBake's photo-first baking space.
 *
 * Everything on this page is backed by `GET /gallery/`, whose real
 * filters are `recipe_id`, `course_id`, `author` and `category` (the
 * *attached recipe's* category). Those are what the chip bar offers.
 *
 * Likes and comments are real (ADR 0032) and live on each card.
 * Deliberately absent, because the gallery app has no such data:
 * post types beyond "has a recipe attached", free tags, a popularity
 * sort (the feed is newest-first, full stop) and bookmarks. Each is
 * reported rather than mocked.
 *
 * The composer expands in place  writing a post never leaves the feed 
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
  const { status, user } = useAuth();

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
        {/* No hero banner: it repeated the sidebar's "about" card and
            pushed a second "create post" button within 100px of the
            composer's own. The feed starts immediately instead. */}
        <h1 className="sr-only">ชุมชนคนรักการอบขนม</h1>

        {/* ---- Composer ------------------------------------------ */}
        <div className="mb-5">
          <InlineComposer
            onPublished={(post) => setFresh((current) => [post, ...current])}
          />
        </div>

        {/* ---- Feed scope: everyone vs. mine --------------------- */}
        {/* "My posts" is the author filter pointed at yourself. It also
            surfaces your hidden posts (the backend's visibility rule
            already shows an owner their own unpublished work), so this
            doubles as the place to manage everything you've shared. */}
        {status === "authenticated" && user ? (
          <div
            role="group"
            aria-label="ขอบเขตฟีด"
            className="mb-4 flex w-fit rounded-full bg-surface p-1 shadow-raised"
          >
            {[
              { label: "ฟีดทั้งหมด", mine: false },
              { label: "โพสต์ของฉัน", mine: true },
            ].map((option) => {
              const active = option.mine
                ? author === user.username
                : author !== user.username;
              return (
                <button
                  key={option.label}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setFilter({ author: option.mine ? user.username : null })
                  }
                  className={cn(
                    "rounded-full px-4 py-1.5 text-sm transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                    active
                      ? "bg-fg font-medium text-fg-inverted"
                      : "text-fg-muted hover:text-fg",
                  )}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        ) : null}

        {/* ---- Filters ------------------------------------------- */}
        {/* Text chips, not photo tiles: 250px of scrolling artwork stood
            between the reader and the first post, and the same list was
            duplicated in the sidebar. This is now the only one. */}
        <div
          role="group"
          aria-label="กรองโพสต์ตามหมวดของสูตรที่แนบ"
          className="mb-4 flex flex-wrap items-center gap-2"
        >
          <button
            type="button"
            aria-pressed={!category}
            onClick={() => setFilter({ category: null })}
            className={cn(
              "rounded-full px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus",
              !category
                ? "bg-fg font-medium text-fg-inverted shadow-raised"
                : "border border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
            )}
          >
            ทั้งหมด
          </button>
          {(categories.data ?? []).map((item) => (
            <button
              key={item.slug}
              type="button"
              aria-pressed={category === item.slug}
              title="กรองจากหมวดของสูตรที่โพสต์แนบไว้"
              onClick={() =>
                setFilter({ category: category === item.slug ? null : item.slug })
              }
              className={cn(
                "rounded-full px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus",
                category === item.slug
                  ? "bg-fg font-medium text-fg-inverted shadow-raised"
                  : "border border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
              )}
            >
              #{item.name}
            </button>
          ))}
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
                className="ml-auto text-sm text-fg-muted underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
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
                  <div className="flex flex-wrap justify-center gap-2">
                    <Link href="/community/create">
                      <Button>
                        <Icon name="ui/plus" tint className="size-4" /> สร้างโพสต์
                      </Button>
                    </Link>
                    <Link href="/recipes/create">
                      <Button variant="secondary">แชร์สูตรอาหารแทน</Button>
                    </Link>
                  </div>
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
                      onMutated={() => {
                        // A fresh post may be the one just deleted; drop
                        // the optimistic list and trust the server.
                        setFresh([]);
                        feed.refetch();
                      }}
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
      </div>

      {/* ---- Sidebar (desktop only) ------------------------------ */}
      <aside className="hidden lg:block">
        <div className="sticky top-20 space-y-4">
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
                กดถูกใจและคอมเมนต์ได้เมื่อเข้าสู่ระบบ
                เจ้าของโพสต์จะได้รับการแจ้งเตือน
                ส่วนการบันทึกโพสต์ยังไม่เปิดให้ใช้งาน
              </p>
            </CardBody>
          </Card>
        </div>
      </aside>
    </div>
  );
}

/**
 * Bakers who appear in the posts currently loaded  a real, visible fact,
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
  // the avatar and label shown are the real display name and photo  the
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
  // Under three bakers the list is either you alone or you and one
  // other - a section that tells the reader nothing.
  const entries = [...bakers.entries()].slice(0, 6);
  if (entries.length < 3) return null;

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
