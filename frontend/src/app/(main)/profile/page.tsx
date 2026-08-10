"use client";

/**
 * Profile — the user's baking identity and learning hub.
 *
 * Every number, status and event on this page is read from a real
 * endpoint: identity and completion from `/me/settings/`, learning from
 * `/me/progress/`, saved content from `/users/me/favorites/`, credentials
 * from `/me/certificates/` and `/me/achievements/`, community posts from
 * `/gallery/?author=`. Zero-valued metrics are dropped rather than shown,
 * and the activity timeline is assembled from those same records'
 * real timestamps — nothing here is synthesised to look complete.
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
import { EXPERIENCE_LABELS, EditProfileDialog } from "./edit-profile-dialog";

const PREVIEW_LIMIT = 6;

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
/* Activity timeline — merged from real records' own timestamps         */
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
        icon: { kind: "ui", name: "heart-filled" },
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

  return events
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, 8);
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function ProfileContent() {
  const { refresh } = useAuth();
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);

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

  // Only metrics with something to report — a wall of zeros is not a
  // learning identity.
  const metrics = [
    { label: "คอร์สที่เรียนจบ", value: completedCourses.length, icon: "graduation" as UiIconName },
    { label: "กำลังเรียน", value: learning.length, icon: "book-open" as UiIconName },
    { label: "ใบประกาศนียบัตร", value: issued.length, icon: "scroll" as UiIconName },
    { label: "สูตรที่บันทึกไว้", value: savedRecipes.data?.count ?? 0, icon: "heart-filled" as UiIconName },
    { label: "คอร์สที่บันทึกไว้", value: savedCourses.data?.count ?? 0, icon: "bookmark" as UiIconName },
    { label: "ความสำเร็จ", value: badges.length, icon: "trophy" as UiIconName },
  ].filter((metric) => metric.value > 0);

  return (
    <div className="space-y-8">
      {/* 1 — Identity ------------------------------------------------ */}
      <Card className="overflow-hidden">
        <div className="kb-hero h-24" aria-hidden />
        <CardBody className="-mt-12 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
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
          {profile.bio ? (
            <p className="whitespace-pre-wrap text-sm text-fg">{profile.bio}</p>
          ) : (
            <p className="text-sm text-fg-subtle">
              ยังไม่มีคำแนะนำตัวเลย เล่าให้เราฟังหน่อยว่าคุณชอบอบอะไร
            </p>
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

      {/* 2 — Learning identity --------------------------------------- */}
      {metrics.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {metrics.map((metric) => (
            <Card key={metric.label} className="px-4 py-3 text-center">
              <Icon name={`ui/${metric.icon}`} className="mx-auto size-5 text-fg-muted" />
              <p className="font-display text-xl font-medium text-fg">
                {metric.value}
              </p>
              <p className="text-xs text-fg-muted">{metric.label}</p>
            </Card>
          ))}
        </div>
      ) : null}

      {/* 3 — Currently learning -------------------------------------- */}
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
              icon={<Icon name="ui/book" className="size-8 text-fg-subtle" />}
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
          <div className="grid gap-4 lg:grid-cols-2">
            {learning.map((course) => (
              <Card key={course.slug} className="flex gap-4 overflow-hidden">
                <div className="w-24 shrink-0">
                  <MediaFrame src={null} seed={course.slug} />
                </div>
                <div className="min-w-0 flex-1 py-3 pr-4">
                  <h3 className="font-display truncate font-medium text-fg">
                    {course.title}
                  </h3>
                  <p className="mt-0.5 text-xs text-fg-muted">
                    {course.total_lessons > 0
                      ? `บทที่ ${Math.min(course.completed_lessons + 1, course.total_lessons)} จาก ${course.total_lessons}`
                      : "ยังไม่มีบทเรียน"}
                  </p>
                  <div className="mt-2 flex items-center gap-3">
                    <ProgressBar
                      percent={course.percentage}
                      label={`ความคืบหน้า ${course.title}`}
                      className="h-2"
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

      {/* 4 — Certificates preview ------------------------------------ */}
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
            className="text-sm text-accent hover:text-accent-hover"
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
              icon={<Icon name="ui/scroll" className="size-8 text-fg-subtle" />}
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
          <ul className="-mx-1 flex snap-x gap-4 overflow-x-auto px-1 pb-2">
            {issued.slice(0, PREVIEW_LIMIT).map((certificate) => (
              <li
                key={certificate.id}
                className="w-72 shrink-0 snap-start sm:w-80"
              >
                <Link
                  href="/certificates"
                  className="group block rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  <div className="transition-transform duration-150 group-hover:-translate-y-0.5">
                    <CertificateSheet certificate={certificate} />
                  </div>
                  <p className="font-display mt-2 truncate text-sm font-medium text-fg">
                    {certificate.course_title}
                  </p>
                  <p className="text-xs text-fg-subtle">
                    ออกให้ {formatThaiDate(certificate.issued_at)}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 5–8 — Saved content + secondary column ----------------------- */}
      <div className="grid gap-8 lg:grid-cols-3">
        <div className="space-y-8 lg:col-span-2">
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
                  className="text-sm text-accent hover:text-accent-hover"
                >
                  ดูรายการโปรดทั้งหมด →
                </Link>
              ) : null
            }
          >
            {savedRecipes.loading ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 3 }, (_, index) => (
                  <Skeleton key={index} className="h-64 rounded-surface" />
                ))}
              </div>
            ) : recipeFavorites.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Icon name="ui/heart" className="size-8 text-fg-subtle" />}
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
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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

          {/* Saved courses — kept separate from what is being learned */}
          <Section
            title="คอร์สที่บันทึกไว้"
            hint="ตั้งใจจะเรียนทีหลัง — คนละกลุ่มกับคอร์สที่กำลังเรียนอยู่"
            action={
              courseFavorites.length > 0 ? (
                <Link
                  href="/favorites"
                  className="text-sm text-accent hover:text-accent-hover"
                >
                  ดูรายการโปรดทั้งหมด →
                </Link>
              ) : null
            }
          >
            {savedCourses.loading ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 3 }, (_, index) => (
                  <Skeleton key={index} className="h-64 rounded-surface" />
                ))}
              </div>
            ) : courseFavorites.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Icon name="ui/bookmark" className="size-8 text-fg-subtle" />}
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
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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

          {/* Community creations — only when the user actually posted */}
          {myPosts.length > 0 ? (
            <Section
              title="ผลงานที่แชร์ไว้"
              hint={`${posts.data?.count ?? myPosts.length} ชิ้นในแกลเลอรีของชุมชน`}
            >
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {myPosts.slice(0, 4).map((post) => (
                  <li key={post.id}>
                    <div className="aspect-square overflow-hidden rounded-surface border border-edge">
                      <MediaFrame
                        src={post.images[0]?.url}
                        seed={String(post.id)}
                      />
                    </div>
                    {post.caption ? (
                      <p className="mt-1 line-clamp-1 text-xs text-fg-muted">
                        {post.caption}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}
        </div>

        {/* Secondary column ----------------------------------------- */}
        <aside className="space-y-6">
          {/* Recent activity */}
          <Card>
            <CardHeader title="ความเคลื่อนไหวล่าสุด" />
            <CardBody>
              {activity.length === 0 ? (
                <p className="text-sm text-fg-muted">
                  ยังไม่มีความเคลื่อนไหว — ความสำเร็จของคุณจะมาปรากฏที่นี่
                </p>
              ) : (
                <ol className="space-y-3">
                  {activity.map((event) => (
                    <li
                      key={`${event.at}-${event.text}`}
                      className="flex gap-3 text-sm"
                    >
                      <span
                        aria-hidden
                        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-sunken"
                      >
                        {event.icon.kind === "ui" ? (
                          <Icon name={`ui/${event.icon.name}`} className="size-4 text-fg-muted" />
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
              )}
            </CardBody>
          </Card>

          {/* Achievements — badge metadata comes from the backend */}
          {badges.length > 0 ? (
            <Card>
              <CardHeader
                title="ความสำเร็จ"
                actions={
                  <Link
                    href="/achievements"
                    className="text-sm text-accent hover:text-accent-hover"
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

          {/* Profile preferences — profile-level only, not app settings */}
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
                    ยังไม่ได้เลือก — ช่วยให้เราแนะนำได้ตรงใจขึ้น
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
                  <p className="mt-1 text-xs text-fg-muted">
                    ยังขาด: {completion.missing.join(", ")}
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
