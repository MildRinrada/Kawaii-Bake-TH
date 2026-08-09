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
import { MediaFrame } from "@/components/content/media-frame";

type CourseProgress = components["schemas"]["CourseProgress"];


export function CourseDetailScreen({ slug }: { slug: string }) {
  const { status } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [enrolling, setEnrolling] = useState(false);

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
      toast("ลงทะเบียนเรียนสำเร็จ 🎉", "success");
      course.refetch();
    } catch {
      toast("ลงทะเบียนไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setEnrolling(false);
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
      <div className="overflow-hidden rounded-surface border border-edge shadow-raised">
        <div className="aspect-[21/8] w-full">
          <MediaFrame src={data.thumbnail_url} seed={data.slug} alt={data.title} />
        </div>
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1.7fr_1fr]">
        <div>
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
          {data.description ? (
            <p className="mt-5 whitespace-pre-wrap text-sm leading-relaxed text-fg">
              {data.description}
            </p>
          ) : null}

          <h2 className="font-display mb-4 mt-8 text-xl font-medium text-fg">
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
                    <Badge tone="mint">🎉 เรียนจบคอร์สแล้ว</Badge>
                  ) : null}
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
