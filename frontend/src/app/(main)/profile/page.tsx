"use client";

/**
 * Profile  the user's baking identity and learning hub.
 *
 * Every number, status and event on this page is read from a real
 * endpoint: identity and completion from `/me/settings/`, learning from
 * `/me/progress/`, saved content from `/users/me/favorites/`, credentials
 * from `/me/certificates/` and `/me/achievements/`, community posts from
 * `/gallery/?author=`. Zero-valued metrics are dropped rather than shown,
 * and the activity timeline is assembled from those same records'
 * real timestamps  nothing here is synthesised to look complete.
 *
 * Deliberately absent because the backend has no such concept: personal
 * notes / baking log (the recipe workspace keeps its checklist in this
 * browser only), collections, a persisted measurement-unit preference,
 * skill *progression* (the level is a profile attribute, not a computed
 * score), memberships and shopping lists. Account configuration stays in
 * `/settings`; this page edits the profile only.
 */

import Link from "next/link";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Achievement,
  Category,
  Certificate,
  CourseListItem,
  FavoriteItem,
  GalleryPost,
  MyCourseProgress,
  MySettings,
  RecipeListItem,
} from "@/lib/api/models";
import { cn } from "@/lib/cn";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { monthYearThai, relativeThai } from "@/lib/datetime";
import { Avatar } from "@/components/ui/avatar";
import { Badge, flavorFor } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { badgeArt } from "@/lib/assets";
import { ArtIcon, Icon, type UiIconName } from "@/components/ui/icon";
import { MediaFrame } from "@/components/content/media-frame";
import { PageContainer } from "@/components/ui/page-container";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Skeleton } from "@/components/ui/skeleton";
import { RecipeCard } from "@/components/content/recipe-card";
import { CourseCard } from "@/components/content/course-card";
import {
  CertificateSheet,
  formatThaiDate,
} from "@/components/content/certificate-sheet";
import { CoverEditor } from "./cover-editor";
import { EXPERIENCE_LABELS, EditProfileDialog } from "./edit-profile-dialog";

const PREVIEW_LIMIT = 6;
const ACTIVITY_PAGE = 5;

/** `profile_completion.missing` ships raw field names; humans read Thai. */
const COMPLETION_LABELS: Record<string, string> = {
  bio: "คำแนะนำตัว",
  location: "ที่อยู่",
  birthday: "วันเกิด",
  favorite_categories: "หมวดที่สนใจ",
  avatar: "รูปโปรไฟล์",
  display_name: "ชื่อที่แสดง",
  experience_level: "ระดับฝีมือ",
  website: "เว็บไซต์",
};

/** "วันนี้" / "เมื่อวาน" / "N วันที่แล้ว" - the timeline's day buckets. */
function dayBucket(iso: string): string {
  const start = (value: Date) =>
    new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  const days = Math.round(
    (start(new Date()) - start(new Date(iso))) / 86_400_000,
  );
  if (days <= 0) return "วันนี้";
  if (days === 1) return "เมื่อวาน";
  if (days < 7) return `${days} วันที่แล้ว`;
  if (days < 30) return `${Math.floor(days / 7)} สัปดาห์ที่แล้ว`;
  return monthYearThai(iso);
}

/* ------------------------------------------------------------------ */
/* Section shell                                                       */
/* ------------------------------------------------------------------ */

function Section({
  title,
  hint,
  action,
  children,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-medium text-fg">{title}</h2>
          {hint ? <p className="text-sm text-fg-muted">{hint}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Activity timeline  merged from real records' own timestamps         */
/* ------------------------------------------------------------------ */

/** Either a monochrome UI glyph or a badge's own catalogue artwork. */
type ActivityIcon =
  | { kind: "ui"; name: UiIconName }
  | { kind: "badge"; slug: string };

interface ActivityEvent {
  at: string;
  icon: ActivityIcon;
  text: string;
  href?: string;
}

function buildActivity(
  courses: MyCourseProgress[],
  certificates: Certificate[],
  achievements: Achievement[],
  savedRecipes: FavoriteItem[],
  savedCourses: FavoriteItem[],
  posts: GalleryPost[],
): ActivityEvent[] {
  const events: ActivityEvent[] = [];

  for (const course of courses) {
    if (course.completed_at) {
      events.push({
        at: course.completed_at,
        icon: { kind: "ui", name: "check" },
        text: `เรียนจบคอร์ส ${course.title}`,
        href: `/courses/${course.slug}`,
      });
    }
  }
  for (const certificate of certificates) {
    events.push({
      at: certificate.issued_at,
      icon: { kind: "ui", name: "trophy" },
      text: `ได้รับใบประกาศนียบัตร ${certificate.course_title}`,
      href: "/certificates",
    });
  }
  for (const achievement of achievements) {
    events.push({
      at: achievement.awarded_at,
      icon: { kind: "badge", slug: achievement.achievement_type },
      text: `ปลดล็อก ${achievement.badge?.title_th || achievement.achievement_type}`,
      href: "/achievements",
    });
  }
  for (const favorite of savedRecipes) {
    const recipe = favorite.recipe as unknown as RecipeListItem | null;
    if (recipe) {
      events.push({
        at: favorite.favorited_at,
        icon: { kind: "ui", name: "heart" },
        text: `บันทึกสูตร ${recipe.title}`,
        href: `/recipes/${recipe.slug}`,
      });
    }
  }
  for (const favorite of savedCourses) {
    const course = favorite.course as unknown as CourseListItem | null;
    if (course) {
      events.push({
        at: favorite.favorited_at,
        icon: { kind: "ui", name: "heart-filled" },
        text: `บันทึกคอร์ส ${course.title}`,
        href: `/courses/${course.slug}`,
      });
    }
  }
  for (const post of posts) {
    events.push({
      at: post.created_at,
      icon: { kind: "ui", name: "camera" },
      // No gallery route exists yet, so this event is a record, not a link.
      text: post.caption
        ? `แชร์ผลงาน “${post.caption.slice(0, 40)}”`
        : "แชร์ผลงานลงแกลเลอรี",
    });
  }

  return events.sort(
    (a, b) => new Date(b.at).getTime() - new Date(a.at).getTime(),
  );
}

/** The timeline, cut into day buckets in the order they occurred. */
function groupByDay(
  events: ActivityEvent[],
): Array<{ bucket: string; items: ActivityEvent[] }> {
  const groups: Array<{ bucket: string; items: ActivityEvent[] }> = [];
  for (const event of events) {
    const bucket = dayBucket(event.at);
    const last = groups[groups.length - 1];
    if (last && last.bucket === bucket) last.items.push(event);
    else groups.push({ bucket, items: [event] });
  }
  return groups;
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function ProfileContent() {
  const { refresh } = useAuth();
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [activityShown, setActivityShown] = useState(ACTIVITY_PAGE);

  const settings = useApiQuery(
    (signal) => api.get<MySettings>("/me/settings/", { signal }),
    [],
  );
  const progress = useApiQuery(
    (signal) =>
      api.get<{ courses: MyCourseProgress[] }>("/me/progress/", { signal }),
    [],
  );
  const savedRecipes = useApiQuery(
    (signal) =>
      api.get<Paginated<FavoriteItem>>("/users/me/favorites/", {
        query: { type: "recipe", page_size: 12 },
        signal,
      }),
    [],
  );
  const savedCourses = useApiQuery(
    (signal) =>
      api.get<Paginated<FavoriteItem>>("/users/me/favorites/", {
        query: { type: "course", page_size: 12 },
        signal,
      }),
    [],
  );
  const certificates = useApiQuery(
    (signal) => api.get<Paginated<Certificate>>("/me/certificates/", { signal }),
    [],
  );
  const achievements = useApiQuery(
    (signal) => api.get<Paginated<Achievement>>("/me/achievements/", { signal }),
    [],
  );
  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const username = settings.data?.profile.username ?? null;
  const posts = useApiQuery(
    (signal) =>
      username
        ? api.get<Paginated<GalleryPost>>("/gallery/", {
            query: { author: username, page_size: 8 },
            signal,
          })
        : Promise.resolve(null),
    [username],
  );

  if (settings.loading) {
    return (
      <div aria-busy="true" className="space-y-5">
        <Skeleton className="h-48 w-full rounded-surface" />
        <Skeleton className="h-24 w-full rounded-surface" />
        <Skeleton className="h-64 w-full rounded-surface" />
      </div>
    );
  }
  if (settings.error || !settings.data) {
    return <ErrorState error={settings.error} onRetry={settings.refetch} />;
  }

  const { profile, profile_completion: completion } = settings.data;
  const categoryNames = new Map(
    (categories.data ?? []).map((category) => [category.slug, category.name]),
  );

  const courses = progress.data?.courses ?? [];
  const learning = courses
    .filter((course) => !course.completed_at)
    .sort((a, b) => b.percentage - a.percentage);
  const completedCourses = courses.filter((course) => course.completed_at);

  const recipeFavorites = savedRecipes.data?.results ?? [];
  const courseFavorites = savedCourses.data?.results ?? [];
  const issued = certificates.data?.results ?? [];
  const badges = achievements.data?.results ?? [];
  const myPosts = posts.data?.results ?? [];

  const activity = buildActivity(
    courses,
    issued,
    badges,
    recipeFavorites,
    courseFavorites,
    myPosts,
  );

  // Only metrics with something to report  a wall of zeros is not a
  // learning identity.
  const metrics = [
    { label: "คอร์สที่เรียนจบ", value: completedCourses.length, icon: "graduation" as UiIconName },
    { label: "กำลังเรียน", value: learning.length, icon: "book-open" as UiIconName },
    { label: "ใบประกาศนียบัตร", value: issued.length, icon: "scroll" as UiIconName },
    { label: "สูตรที่บันทึกไว้", value: savedRecipes.data?.count ?? 0, icon: "heart" as UiIconName },
    { label: "คอร์สที่บันทึกไว้", value: savedCourses.data?.count ?? 0, icon: "bookmark" as UiIconName },
    { label: "ความสำเร็จ", value: badges.length, icon: "trophy" as UiIconName },
  ].filter((metric) => metric.value > 0);

  return (
    <div className="space-y-8">
      {/* 1  Identity ------------------------------------------------ */}
      <Card className="overflow-hidden">
        <CoverEditor
          coverUrl={profile.cover_url}
          onChanged={() => settings.refetch()}
        />
        {/* `relative z-10`: the banner above is positioned, and a positioned
            element paints over a static one whatever the DOM order says 
            without this the cover would cover the avatar pulled up into it. */}
        <CardBody className="relative z-10 -mt-12 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-end gap-4">
            <Avatar
              src={profile.avatar_url}
              name={profile.display_name || profile.username}
              size="lg"
              className="size-24 text-3xl ring-4 ring-surface-raised"
            />
            <div className="pb-1">
              <h1 className="font-display text-2xl font-medium text-fg">
                {profile.display_name || profile.username}
              </h1>
              <p className="text-sm text-fg-muted">@{profile.username}</p>
            </div>
          </div>
          <Button variant="secondary" onClick={() => setEditing(true)}>
            <Icon name="ui/edit" className="size-4" /> แก้ไขโปรไฟล์
          </Button>
        </CardBody>
        <CardBody className="border-t border-edge pt-4">
          {/* The learning identity lives with the identity, not in a row
              of six cards: five one-digit numbers never needed a grid. */}
          {metrics.length > 0 ? (
            <p className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fg-muted">
              {metrics.map((metric, index) => (
                <span key={metric.label} className="flex items-center gap-1.5">
                  {index > 0 ? (
                    <span aria-hidden className="text-fg-subtle">
                      ·
                    </span>
                  ) : null}
                  <Icon
                    tint
                    name={`ui/${metric.icon}`}
                    className="size-4 text-fg-subtle"
                  />
                  <strong className="font-medium text-fg">{metric.value}</strong>
                  {metric.label}
                </span>
              ))}
            </p>
          ) : null}
          {profile.bio ? (
            <p className="whitespace-pre-wrap text-sm text-fg">{profile.bio}</p>
          ) : (
            // Grey, not pink: an unwritten bio is an invitation, not a
            // validation error - and the invitation opens the editor.
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="rounded-control text-left text-sm text-fg-subtle underline decoration-dotted underline-offset-4 hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
            >
              ยังไม่มีคำแนะนำตัวเลย เล่าให้เราฟังหน่อยว่าคุณชอบอบอะไร
            </button>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <Badge tone="lavender">
              {EXPERIENCE_LABELS[profile.experience_level] ??
                profile.experience_level}
            </Badge>
            {profile.location ? (
              <Badge>
                <Icon name="ui/pin" className="size-3.5" /> {profile.location}
              </Badge>
            ) : null}
            {profile.favorite_categories.map((slug) => (
              <Badge key={slug} tone={flavorFor(slug)}>
                {categoryNames.get(slug) ?? slug}
              </Badge>
            ))}
            <span className="text-xs text-fg-subtle">
              เข้าร่วมเมื่อ {monthYearThai(profile.joined_at)}
            </span>
          </div>
        </CardBody>
      </Card>

      {/* Two columns from directly under the cover: everything the page
          says about *doing* on the left, everything it says about *being*
          on the right. Nothing below has to span the full width alone. */}
      <div className="grid gap-8 lg:grid-cols-3">
        <div className="space-y-8 lg:col-span-2">

      {/* 1  Currently learning -------------------------------------- */}
      <Section
        title="กำลังเรียนอยู่"
        hint={
          completedCourses.length > 0
            ? `เรียนต่อจากที่ค้างไว้ได้เลย ตอนนี้คุณเรียนจบไปแล้ว ${completedCourses.length} คอร์ส`
            : "เรียนต่อจากที่ค้างไว้ได้เลย"
        }
      >
        {progress.loading ? (
          <Skeleton className="h-28 w-full rounded-surface" />
        ) : learning.length === 0 ? (
          <Card>
            <EmptyState
              icon={<Icon tint name="ui/book" className="size-8 text-fg-subtle" />}
              title="ยังไม่มีคอร์สที่กำลังเรียน"
              description="เริ่มคอร์สแรกเพื่อเริ่มต้นเส้นทางการอบของคุณ"
              action={
                <Link href="/courses">
                  <Button>ดูคอร์สเรียน</Button>
                </Link>
              }
            />
          </Card>
        ) : (
          // One course in progress gets the full width as a wide row;
          // two or more share the two-up grid.
          <div className={cn("grid gap-4", learning.length > 1 && "lg:grid-cols-2")}>
            {learning.map((course) => (
              <Card key={course.slug} className="flex gap-4 overflow-hidden">
                <div className={cn("shrink-0", learning.length > 1 ? "w-24" : "w-32 sm:w-44")}>
                  <MediaFrame src={null} seed={course.slug} />
                </div>
                <div className="min-w-0 flex-1 py-3 pr-4">
                  <h3 className="font-display truncate font-medium text-fg">
                    {course.title}
                  </h3>
                  {/* Says the same thing as the percentage - "บทที่ 1
                      จาก 2" next to 0% read as a contradiction. */}
                  <p className="mt-0.5 text-xs text-fg-muted">
                    {course.total_lessons > 0
                      ? `เรียนจบแล้ว ${course.completed_lessons} จาก ${course.total_lessons} บท`
                      : "ยังไม่มีบทเรียน"}
                  </p>
                  <div className="mt-2 flex items-center gap-3">
                    <ProgressBar
                      percent={course.percentage}
                      label={`ความคืบหน้า ${course.title}`}
                      className="h-2 flex-1"
                    />
                    <span className="shrink-0 text-xs font-medium text-fg-muted">
                      {course.percentage}%
                    </span>
                  </div>
                  <Link
                    href={`/courses/${course.slug}`}
                    className="mt-2 inline-block"
                  >
                    <Button size="sm" variant="secondary">
                      เรียนต่อ
                    </Button>
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Section>

      {/* 2  Community creations -------------------------------------
          Sits high on purpose: what the baker *made* outranks what they
          merely saved. Each post is a real card - cover, title, date,
          the recipe it was baked from - and the section is always
          present so "share your first bake" is reachable. */}
      <Section
        title="ผลงานที่แชร์ไว้"
        hint={
          myPosts.length > 0
            ? `${posts.data?.count ?? myPosts.length} ชิ้นในแกลเลอรีของชุมชน`
            : "รูปขนมที่คุณแชร์ให้ชุมชนดู"
        }
        action={
          myPosts.length > 0 && username ? (
            <Link
              href={`/community?author=${username}` as "/community"}
              className="text-sm text-fg-muted hover:text-fg"
            >
              จัดการโพสต์ทั้งหมด →
            </Link>
          ) : null
        }
      >
        {posts.loading ? (
          <Skeleton className="h-44 w-full rounded-surface" />
        ) : myPosts.length === 0 ? (
          <Card>
            <EmptyState
              icon={<Icon tint name="ui/camera" className="size-8 text-fg-subtle" />}
              title="ยังไม่เคยแชร์ผลงาน"
              description="ถ่ายรูปขนมที่เพิ่งอบเสร็จมาอวดชุมชน แล้วมันจะมาอยู่ตรงนี้"
              action={
                <Link href="/community/create">
                  <Button>
                    <Icon name="ui/plus" className="size-4" /> แชร์ผลงาน
                  </Button>
                </Link>
              }
            />
          </Card>
        ) : (
          <ul
            className={cn(
              "grid gap-4",
              myPosts.length > 1 && "sm:grid-cols-2 xl:grid-cols-3",
            )}
          >
            {myPosts.slice(0, PREVIEW_LIMIT).map((post) => {
              const horizontal = myPosts.length === 1;
              return (
                <li key={post.id}>
                  <Link
                    href={`/community/posts/${post.id}`}
                    className="group block h-full rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  >
                    <Card
                      className={cn(
                        "flex h-full overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay",
                        horizontal ? "flex-col sm:flex-row" : "flex-col",
                      )}
                    >
                      <div
                        className={cn(
                          "aspect-4/3 w-full shrink-0 overflow-hidden",
                          horizontal && "sm:w-2/5",
                        )}
                      >
                        <MediaFrame
                          src={post.images[0]?.url}
                          seed={String(post.id)}
                        />
                      </div>
                      <div className="flex flex-1 flex-col gap-1.5 p-4">
                        <h3 className="font-display line-clamp-2 font-medium text-fg group-hover:text-accent-hover">
                          {/* A caption is optional; the recipe it was
                              baked from is the honest fallback title. */}
                          {post.caption?.trim() ||
                            post.recipe?.title ||
                            "ผลงานของฉัน"}
                        </h3>
                        <p className="flex flex-wrap items-center gap-x-2 text-xs text-fg-subtle">
                          <span>{relativeThai(post.created_at)}</span>
                          {post.images.length > 1 ? (
                            <span>· {post.images.length} รูป</span>
                          ) : null}
                          {post.status !== "active" ? (
                            <Badge tone="butter">ซ่อนอยู่</Badge>
                          ) : null}
                        </p>
                        {post.recipe || post.course ? (
                          <p className="mt-auto pt-1 text-xs text-fg-muted">
                            จาก{post.recipe ? "สูตร" : "คอร์ส"}{" "}
                            <span className="text-fg">
                              {post.recipe?.title ?? post.course?.title}
                            </span>
                          </p>
                        ) : null}
                      </div>
                    </Card>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      {/* 3  Certificates preview ------------------------------------ */}
      <Section
        title="ใบประกาศนียบัตรของฉัน"
        hint={
          issued.length > 0
            ? `ได้รับแล้ว ${issued.length} ใบ`
            : "เรียนจบคอร์สเพื่อรับใบแรก"
        }
        action={
          <Link
            href="/certificates"
            className="text-sm text-fg-muted hover:text-fg"
          >
            ดูทั้งหมด →
          </Link>
        }
      >
        {certificates.loading ? (
          <Skeleton className="h-44 w-full rounded-surface" />
        ) : issued.length === 0 ? (
          <Card>
            <EmptyState
              icon={<Icon tint name="ui/scroll" className="size-8 text-fg-subtle" />}
              title="ยังไม่มีใบประกาศนียบัตร"
              description="เรียนจบคอร์สให้ครบทุกบทเพื่อรับใบประกาศใบแรกของคุณ"
              action={
                <Link href="/certificates">
                  <Button variant="secondary">ดูสถานะใบประกาศ</Button>
                </Link>
              }
            />
          </Card>
        ) : (
          // A single certificate lies down (sheet left, details right)
          // instead of leaving two thirds of the row empty.
          <ul
            className={cn(
              issued.length === 1
                ? "block"
                : "-mx-1 flex snap-x gap-4 overflow-x-auto px-1 pb-2",
            )}
          >
            {issued.slice(0, PREVIEW_LIMIT).map((certificate) => (
              <li
                key={certificate.id}
                className={cn(
                  issued.length === 1
                    ? "w-full"
                    : "w-72 shrink-0 snap-start sm:w-80",
                )}
              >
                <Link
                  href="/certificates"
                  className={cn(
                    "group rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                    issued.length === 1
                      ? "flex flex-col gap-4 sm:flex-row sm:items-center"
                      : "block",
                  )}
                >
                  <div
                    className={cn(
                      "transition-transform duration-150 group-hover:-translate-y-0.5",
                      issued.length === 1 && "w-full shrink-0 sm:w-80",
                    )}
                  >
                    <CertificateSheet certificate={certificate} />
                  </div>
                  <div className={cn(issued.length === 1 ? "min-w-0" : "")}>
                    <p className="font-display mt-2 truncate text-sm font-medium text-fg sm:mt-0">
                      {certificate.course_title}
                    </p>
                    <p className="text-xs text-fg-subtle">
                      ออกให้ {formatThaiDate(certificate.issued_at)}
                    </p>
                    {issued.length === 1 ? (
                      <p className="mt-2 text-sm text-fg-muted">
                        เรียนจบครบทุกบทแล้ว ดาวน์โหลดหรือแชร์ใบนี้ได้ที่หน้าใบประกาศนียบัตร
                      </p>
                    ) : null}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 4  Saved content ------------------------------------------- */}
          {/* Saved recipes */}
          <Section
            title="สูตรที่บันทึกไว้"
            hint={
              savedRecipes.data?.count
                ? `${savedRecipes.data.count} สูตรรอให้คุณลงมืออบ`
                : undefined
            }
            action={
              recipeFavorites.length > 0 ? (
                <Link
                  href="/favorites"
                  className="text-sm text-fg-muted hover:text-fg"
                >
                  ดูรายการโปรดทั้งหมด →
                </Link>
              ) : null
            }
          >
            {savedRecipes.loading ? (
              <div className="grid gap-4 sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]">
                {Array.from({ length: 3 }, (_, index) => (
                  <Skeleton key={index} className="h-64 rounded-surface" />
                ))}
              </div>
            ) : recipeFavorites.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Icon tint name="ui/heart" className="size-8 text-fg-subtle" />}
                  title="ยังไม่มีสูตรที่บันทึกไว้"
                  description="กดหัวใจในสูตรที่อยากอบไว้ทีหลัง แล้วมันจะมารออยู่ตรงนี้"
                  action={
                    <Link href="/recipes">
                      <Button>ดูสูตรขนม</Button>
                    </Link>
                  }
                />
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]">
                {recipeFavorites
                  .slice(0, PREVIEW_LIMIT)
                  .map((favorite, index) => (
                    <RecipeCard
                      key={`recipe-${index}`}
                      recipe={favorite.recipe as unknown as RecipeListItem}
                    />
                  ))}
              </div>
            )}
          </Section>

          {/* Saved courses  kept separate from what is being learned */}
          <Section
            title="คอร์สที่บันทึกไว้"
            hint="ตั้งใจจะเรียนทีหลัง  คนละกลุ่มกับคอร์สที่กำลังเรียนอยู่"
            action={
              courseFavorites.length > 0 ? (
                <Link
                  href="/favorites"
                  className="text-sm text-fg-muted hover:text-fg"
                >
                  ดูรายการโปรดทั้งหมด →
                </Link>
              ) : null
            }
          >
            {savedCourses.loading ? (
              <div className="grid gap-4 sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]">
                {Array.from({ length: 3 }, (_, index) => (
                  <Skeleton key={index} className="h-64 rounded-surface" />
                ))}
              </div>
            ) : courseFavorites.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Icon tint name="ui/bookmark" className="size-8 text-fg-subtle" />}
                  title="ยังไม่มีคอร์สที่บันทึกไว้"
                  description="เจอคอร์สที่น่าสนใจแต่ยังไม่พร้อมเรียน? กดหัวใจเก็บไว้ก่อนได้"
                  action={
                    <Link href="/courses">
                      <Button variant="secondary">ดูคอร์สเรียน</Button>
                    </Link>
                  }
                />
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]">
                {courseFavorites
                  .slice(0, PREVIEW_LIMIT)
                  .map((favorite, index) => (
                    <CourseCard
                      key={`course-${index}`}
                      course={favorite.course as unknown as CourseListItem}
                    />
                  ))}
              </div>
            )}
          </Section>

        </div>

        {/* Secondary column: who this baker is. Sticky on desktop so it
            stays with the reader down a long left column. */}
        <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start">
          {/* Recent activity - grouped by day and cut to five, because
              eight undifferentiated rows read as noise. */}
          <Card>
            <CardHeader title="ความเคลื่อนไหวล่าสุด" />
            <CardBody>
              {activity.length === 0 ? (
                <p className="text-sm text-fg-muted">
                  ยังไม่มีความเคลื่อนไหว  ความสำเร็จของคุณจะมาปรากฏที่นี่
                </p>
              ) : (
                <>
                  <div className="space-y-4">
                    {groupByDay(activity.slice(0, activityShown)).map((group) => (
                      <div key={group.bucket}>
                        <p className="mb-1.5 text-xs font-medium text-fg-subtle">
                          {group.bucket}
                        </p>
                        <ol className="space-y-3">
                          {group.items.map((event) => (
                            <li
                              key={`${event.at}-${event.text}`}
                              className="flex gap-3 text-sm"
                            >
                              <span
                                aria-hidden
                                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-sunken"
                              >
                                {event.icon.kind === "ui" ? (
                                  <Icon
                                    tint
                                    name={`ui/${event.icon.name}`}
                                    className="size-4 text-fg-muted"
                                  />
                                ) : (
                                  <ArtIcon src={badgeArt(event.icon.slug, true)} className="size-5" />
                                )}
                              </span>
                              <div className="min-w-0">
                                {event.href ? (
                                  <Link
                                    href={event.href as "/certificates"}
                                    className="line-clamp-2 text-fg hover:text-accent-hover"
                                  >
                                    {event.text}
                                  </Link>
                                ) : (
                                  <p className="line-clamp-2 text-fg">{event.text}</p>
                                )}
                                <time
                                  dateTime={event.at}
                                  className="text-xs text-fg-subtle"
                                >
                                  {relativeThai(event.at)}
                                </time>
                              </div>
                            </li>
                          ))}
                        </ol>
                      </div>
                    ))}
                  </div>
                  {activity.length > activityShown ? (
                    <button
                      type="button"
                      onClick={() =>
                        setActivityShown((shown) => shown + ACTIVITY_PAGE)
                      }
                      className="mt-3 text-sm text-fg-muted underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                    >
                      ดูเพิ่ม ({activity.length - activityShown})
                    </button>
                  ) : null}
                </>
              )}
            </CardBody>
          </Card>

          {/* Achievements  badge metadata comes from the backend */}
          {badges.length > 0 ? (
            <Card>
              <CardHeader
                title="ความสำเร็จ"
                actions={
                  <Link
                    href="/achievements"
                    className="text-sm text-fg-muted hover:text-fg"
                  >
                    ดูทั้งหมด →
                  </Link>
                }
              />
              <CardBody className="flex flex-wrap gap-2">
                {badges.slice(0, 8).map((badge) => (
                  <span
                    key={badge.id}
                    title={badge.badge?.description_th ?? undefined}
                    className="flex items-center gap-1.5 rounded-full bg-butter-soft px-3 py-1 text-sm text-butter-ink"
                  >
                    <ArtIcon src={badgeArt(badge.achievement_type, true)} className="size-5" />
                    {badge.badge?.title_th || badge.achievement_type}
                  </span>
                ))}
              </CardBody>
            </Card>
          ) : null}

          {/* Profile preferences  profile-level only, not app settings */}
          <Card>
            <CardHeader title="ข้อมูลโปรไฟล์" />
            <CardBody className="space-y-4">
              <div>
                <p className="text-xs text-fg-subtle">ระดับฝีมือ</p>
                <p className="text-sm text-fg">
                  {EXPERIENCE_LABELS[profile.experience_level] ??
                    profile.experience_level}
                </p>
              </div>
              <div>
                <p className="text-xs text-fg-subtle">หมวดที่สนใจ</p>
                {profile.favorite_categories.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {profile.favorite_categories.map((slug) => (
                      <Badge key={slug} tone={flavorFor(slug)}>
                        {categoryNames.get(slug) ?? slug}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-fg-muted">
                    ยังไม่ได้เลือก  ช่วยให้เราแนะนำได้ตรงใจขึ้น
                  </p>
                )}
              </div>
              <div>
                <p className="text-xs text-fg-subtle">ความครบถ้วนของโปรไฟล์</p>
                <div className="mt-1.5 flex items-center gap-3">
                  <ProgressBar
                    percent={completion.percent}
                    label="ความครบถ้วนของโปรไฟล์"
                    className="h-2"
                  />
                  <span className="shrink-0 text-xs text-fg-muted">
                    {completion.percent}%
                  </span>
                </div>
                {completion.missing.length > 0 ? (
                  // Field names translated, and each one opens the
                  // editor - naming a gap without a way to fill it is
                  // just nagging.
                  <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-fg-muted">
                    ยังขาด:
                    {completion.missing.map((field) => (
                      <button
                        key={field}
                        type="button"
                        onClick={() => setEditing(true)}
                        className="rounded-full bg-surface-sunken px-2 py-0.5 text-fg-muted underline decoration-dotted underline-offset-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                      >
                        {COMPLETION_LABELS[field] ?? field}
                      </button>
                    ))}
                  </p>
                ) : (
                  <p className="mt-1 flex items-center gap-1 text-xs text-fg-muted"><Icon name="ui/party" className="size-3.5" /> ครบแล้ว</p>
                )}
              </div>
              <div className="border-t border-edge pt-3">
                <p className="text-xs text-fg-muted">
                  ความคืบหน้าการเรียน รายการโปรด และความเคลื่อนไหวของคุณเป็นข้อมูลส่วนตัว
                  เห็นได้เฉพาะคุณเท่านั้น
                </p>
                <Link href="/settings" className="mt-2 inline-block">
                  <Button variant="ghost" size="sm">
                    ตั้งค่าบัญชีและความเป็นส่วนตัว →
                  </Button>
                </Link>
              </div>
            </CardBody>
          </Card>
        </aside>
      </div>

      {editing ? (
        <EditProfileDialog
          open
          profile={profile}
          categories={categories.data ?? []}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            toast("บันทึกโปรไฟล์แล้ว", "success");
            settings.refetch();
            void refresh();
          }}
        />
      ) : null}
    </div>
  );
}

export default function ProfilePage() {
  return (
    <PageContainer>
      <RequireAuth>
        <ProfileContent />
      </RequireAuth>
    </PageContainer>
  );
}
