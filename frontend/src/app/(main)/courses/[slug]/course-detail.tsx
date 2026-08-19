"use client";

/**
 * Course detail: banner, meta, enroll action, syllabus with per-lesson
 * completion (merged from the progress endpoint when enrolled), and a
 * soft progress bar. All from the real API.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/types";
import type { CourseDetail, LessonSyllabusItem } from "@/lib/api/models";
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
import { Skeleton } from "@/components/ui/skeleton";
import { LessonCard } from "@/components/content/lesson-card";
import { CoverFrame } from "@/components/content/cover-frame";
import { Icon } from "@/components/ui/icon";

type CourseProgress = components["schemas"]["CourseProgress"];


export function CourseDetailScreen({ slug }: { slug: string }) {
  const { status } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [enrolling, setEnrolling] = useState(false);
  const [unenrolling, setUnenrolling] = useState(false);

  const course = useApiQuery(
    (signal) => api.get<CourseDetail>(`/courses/${slug}/`, { signal }),
    [slug],
  );
  const syllabus = useApiQuery(
    (signal) => api.get<LessonSyllabusItem[]>(`/courses/${slug}/lessons/`, { signal }),
    [slug],
  );
  const enrolled = course.data?.is_enrolled ?? false;
  const progress = useApiQuery(
    async (signal) => {
      if (!enrolled) return null;
      return api.get<CourseProgress>(`/courses/${slug}/progress/`, { signal });
    },
    [slug, enrolled],
  );

  async function enroll() {
    if (status !== "authenticated") {
      router.push(`/login?next=/courses/${slug}`);
      return;
    }
    setEnrolling(true);
    try {
      await api.post(`/courses/${slug}/enroll/`);
      toast("ลงทะเบียนเรียนสำเร็จ", "success");
      course.refetch();
    } catch {
      toast("ลงทะเบียนไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setEnrolling(false);
    }
  }

  async function unenroll() {
    // Soft on the backend - progress and history survive, and re-enrolling
    // restores them - but it still drops the learner out of the course
    // right now, so a stray click deserves a confirmation.
    if (!window.confirm("เลิกเรียนคอร์สนี้? ประวัติการเรียนจะยังอยู่ ลงทะเบียนใหม่ได้ทุกเมื่อ")) {
      return;
    }
    setUnenrolling(true);
    try {
      await api.delete(`/courses/${slug}/unenroll/`);
      toast("เลิกเรียนคอร์สนี้แล้ว", "neutral");
      course.refetch();
    } catch {
      toast("เลิกเรียนไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setUnenrolling(false);
    }
  }

  if (course.loading) {
    return (
      <PageContainer aria-busy="true">
        <Skeleton className="mb-6 h-64 w-full rounded-surface" />
        <Skeleton className="mb-3 h-9 w-2/3" />
        <Skeleton className="h-48 w-full rounded-surface" />
      </PageContainer>
    );
  }
  if (course.error || !course.data) {
    return (
      <PageContainer>
        <ErrorState error={course.error} onRetry={course.refetch} />
      </PageContainer>
    );
  }
  const data = course.data;
  const completedIds = new Set(
    (progress.data?.lessons ?? [])
      .filter((lesson) => lesson.completed)
      .map((lesson) => lesson.id),
  );

  return (
    <PageContainer>
      {/* Same hero contract as a recipe: the thumbnail keeps the card's
          4:3 (3:4 if the file is portrait) instead of being sliced into a
          21:8 strip, and the title sits beside it rather than under 440px
          of banner. */}
      <div className="grid gap-6 lg:grid-cols-2 lg:items-center">
        <CoverFrame
          src={data.thumbnail_url}
          seed={data.slug}
          alt={data.title}
          kind="course"
        />

        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap gap-1.5">
            <DifficultyBadge level={data.difficulty} />
            <Badge tone="lavender">{data.lesson_count} บทเรียน</Badge>
            {data.categories.map((category) => (
              <Badge key={category.slug} tone={flavorFor(category.slug)}>
                {category.name}
              </Badge>
            ))}
          </div>
          <h1 className="font-display text-2xl font-medium text-fg sm:text-3xl">
            {data.title}
          </h1>
          <p className="mt-2 text-fg-muted">{data.summary}</p>
          <p className="mt-3 flex items-center gap-2 text-sm text-fg-muted">
            <Avatar
              src={data.instructor.avatar_url}
              name={data.instructor.display_name || data.instructor.username}
              size="sm"
            />
            สอนโดย {data.instructor.display_name || data.instructor.username}
          </p>
        </div>
      </div>

      {/* Kept outside the two-column grid on purpose: a description of
          varying length must not push "บทเรียนในคอร์ส" (and the sticky
          "การเรียนของฉัน" card beside it) down by a different amount every
          time - the two column tops stay level only if nothing but the
          heading and the card lead their columns. */}
      {data.description ? (
        <p className="mt-8 whitespace-pre-wrap text-sm leading-relaxed text-fg">
          {data.description}
        </p>
      ) : null}

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.7fr_1fr]">
        <div>
          <h2 className="font-display mb-4 text-xl font-medium text-fg">
            บทเรียนในคอร์ส
          </h2>
          {syllabus.loading ? (
            <div className="space-y-2" aria-busy="true">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : syllabus.error ? (
            <ErrorState error={syllabus.error} onRetry={syllabus.refetch} />
          ) : !syllabus.data || syllabus.data.length === 0 ? (
            <p className="text-sm text-fg-muted">ยังไม่มีบทเรียน</p>
          ) : (
            <ol className="space-y-2">
              {syllabus.data.map((lesson, index) => (
                <li key={lesson.id}>
                  <LessonCard
                    lesson={lesson}
                    index={index + 1}
                    completed={completedIds.has(lesson.id)}
                  />
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="lg:sticky lg:top-24 lg:self-start">
          <Card>
            <CardHeader title={enrolled ? "การเรียนของฉัน" : "เริ่มเรียนคอร์สนี้"} />
            <CardBody className="space-y-4">
              {enrolled && progress.data ? (
                <>
                  <ProgressBar
                    percent={progress.data.percent}
                    label="ความคืบหน้าของคอร์ส"
                  />
                  <p className="text-sm text-fg-muted">
                    เรียนแล้ว {progress.data.completed_lessons} จาก{" "}
                    {progress.data.total_lessons} บทเรียน ({progress.data.percent}%)
                  </p>
                  {data.is_completed ? (
                    <Badge tone="mint">
                      <Icon name="ui/party" className="size-3.5" /> เรียนจบคอร์สแล้ว
                    </Badge>
                  ) : null}
                  <Button
                    variant="danger"
                    size="sm"
                    className="w-full"
                    loading={unenrolling}
                    onClick={() => void unenroll()}
                  >
                    เลิกเรียนคอร์สนี้
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-fg-muted">
                    ลงทะเบียนฟรี เรียนได้ตามจังหวะของคุณ
                    จบครบทุกบทรับใบประกาศนียบัตร
                  </p>
                  <Button
                    className="w-full"
                    loading={enrolling}
                    onClick={() => void enroll()}
                  >
                    {status === "authenticated"
                      ? "ลงทะเบียนเรียน"
                      : "เข้าสู่ระบบเพื่อลงทะเบียน"}
                  </Button>
                </>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
