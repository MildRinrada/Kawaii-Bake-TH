"use client";

/**
 * The learning surface: lesson content, optional video embed, linked
 * recipe, and the complete/uncomplete action. The enrollment gate's 401
 * and 403 `enrollment_required` answers get designed states with a real
 * way forward  never a dead end.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { LessonDetail } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useToast } from "@/components/ui/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";

function GateState({ error }: { error: ApiError }) {
  const isAuth = error.status === 401;
  return (
    <EmptyState
      icon={
        <Icon
          name={isAuth ? "ui/lock" : "ui/graduation"}
          className="size-8 text-fg-subtle"
        />
      }
      title={isAuth ? "เข้าสู่ระบบเพื่อเรียนบทนี้" : "บทเรียนนี้สำหรับผู้ลงทะเบียน"}
      description={
        isAuth
          ? "บทเรียนเปิดให้ผู้เรียนที่เข้าสู่ระบบและลงทะเบียนคอร์สแล้ว"
          : "ลงทะเบียนคอร์สก่อน แล้วกลับมาเรียนบทนี้ได้เลย"
      }
      action={
        <Link href={isAuth ? "/login" : "/courses"}>
          <Button variant="secondary">
            {isAuth ? "ไปหน้าเข้าสู่ระบบ" : "ดูคอร์สทั้งหมด"}
          </Button>
        </Link>
      }
    />
  );
}

export function LessonScreen({ lessonId }: { lessonId: string }) {
  const { toast } = useToast();
  const [completed, setCompleted] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  const lesson = useApiQuery(
    (signal) => api.get<LessonDetail>(`/lessons/${lessonId}/`, { signal }),
    [lessonId],
  );

  async function toggleComplete() {
    setBusy(true);
    try {
      if (completed) {
        await api.delete(`/lessons/${lessonId}/complete/`);
        setCompleted(false);
        toast("ยกเลิกการทำเครื่องหมายเรียนจบแล้ว");
      } else {
        await api.post(`/lessons/${lessonId}/complete/`);
        setCompleted(true);
        toast("เรียนจบบทเรียนแล้ว เก่งมาก!", "success");
      }
    } catch (error) {
      toast(
        error instanceof ApiError ? error.message : "ทำรายการไม่สำเร็จ",
        "danger",
      );
    } finally {
      setBusy(false);
    }
  }

  if (lesson.loading) {
    return (
      <PageContainer aria-busy="true">
        <Skeleton className="mb-4 h-8 w-1/2" />
        <Skeleton className="h-72 w-full rounded-surface" />
      </PageContainer>
    );
  }
  if (lesson.error) {
    const gated =
      lesson.error instanceof ApiError &&
      (lesson.error.status === 401 || lesson.error.status === 403);
    return (
      <PageContainer>
        {gated ? (
          <GateState error={lesson.error as ApiError} />
        ) : (
          <ErrorState error={lesson.error} onRetry={lesson.refetch} />
        )}
      </PageContainer>
    );
  }
  const data = lesson.data!;

  return (
    <PageContainer className="max-w-3xl">
      <nav aria-label="เส้นทาง" className="mb-3 text-sm text-fg-muted">
        <Link
          href={`/courses/${data.course_slug}`}
          className="rounded-control underline-offset-2 hover:text-fg hover:underline focus-visible:outline-2 focus-visible:outline-focus"
        >
          ← {data.course_title}
        </Link>
      </nav>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Badge tone="lavender">บทที่ {data.position + 1}</Badge>
        {data.duration_minutes ? (
          <Badge>
            <Icon name="ui/clock" className="size-3.5" /> {data.duration_minutes} นาที
          </Badge>
        ) : null}
        {data.is_preview ? <Badge tone="butter">บทตัวอย่าง</Badge> : null}
      </div>
      <h1 className="font-display text-2xl font-medium text-fg sm:text-3xl">
        {data.title}
      </h1>

      {data.video_url ? (
        <p className="mt-4 rounded-control bg-lavender-soft px-4 py-3 text-sm text-lavender-ink">
          <Icon name="ui/camera" className="mr-1 inline-block size-4 align-[-3px]" />
          บทเรียนนี้มีวิดีโอประกอบ {" "}
          <a
            href={data.video_url}
            target="_blank"
            rel="noreferrer"
            className="font-medium underline underline-offset-2"
          >
            เปิดดูวิดีโอ
          </a>
        </p>
      ) : null}

      <Card className="mt-6">
        <CardBody>
          <div className="whitespace-pre-wrap text-[0.95rem] leading-relaxed text-fg">
            {data.content}
          </div>
        </CardBody>
      </Card>

      {data.recipe ? (
        <Link
          href={`/recipes/${(data.recipe as { slug: string }).slug}`}
          className="mt-4 block rounded-control bg-peach-soft px-4 py-3 text-sm text-peach-ink transition-colors hover:bg-peach-soft/70 focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/bowl" className="mr-1 inline-block size-4 align-[-3px]" />
          สูตรประกอบบทเรียน:{" "}
          <span className="font-medium underline underline-offset-2">
            {(data.recipe as { title: string }).title}
          </span>
        </Link>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-surface border border-edge bg-surface px-5 py-4 shadow-raised">
        <p className="text-sm text-fg-muted">
          {completed ? "บทเรียนนี้เรียนจบแล้ว ✓" : "เรียนจบบทนี้แล้วใช่ไหม?"}
        </p>
        <Button
          variant={completed ? "secondary" : "primary"}
          loading={busy}
          onClick={() => void toggleComplete()}
        >
          {completed ? "เรียนจบแล้ว ✓" : "ทำเครื่องหมายว่าเรียนจบ"}
        </Button>
      </div>
    </PageContainer>
  );
}
