"use client";

/**
 * One question thread: the question, its target, every answer, and the
 * two writes the API offers here - answering (`POST .../answers/`) and
 * the asker choosing the accepted answer (`POST .../accept/`).
 *
 * This is the page notification links (`/threads/{id}`) point at; the
 * legacy `/qa/threads/{id}` path redirects here so links delivered
 * before the rename keep working. Hidden/removed threads 404 from the
 * API and render the error state - existence stays the backend's
 * decision.
 */

import Link from "next/link";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type { QaAnswer, QaThread } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { describeAdminError } from "@/components/admin/lifecycle";
import { cn } from "@/lib/cn";

function thaiDateTime(iso: string): string {
  return new Date(iso).toLocaleString("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function ThreadDetail({ threadId }: { threadId: string }) {
  const { status, user } = useAuth();
  const { toast } = useToast();

  const thread = useApiQuery(
    (signal) => api.get<QaThread>(`/qa/threads/${threadId}/`, { signal }),
    [threadId],
  );
  const answers = useApiQuery(
    (signal) =>
      api.get<Paginated<QaAnswer>>(`/qa/threads/${threadId}/answers/`, {
        query: { page_size: 50 },
        signal,
      }),
    [threadId],
  );

  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const [accepting, setAccepting] = useState<number | null>(null);

  const data = thread.data;
  const isAsker =
    status === "authenticated" && data?.author_handle === user?.username;
  const acceptedId = data?.accepted_answer?.id ?? null;

  async function postAnswer() {
    if (!draft.trim()) return;
    setPosting(true);
    try {
      await api.post(`/qa/threads/${threadId}/answers/`, {
        body: { body: draft.trim() },
      });
      setDraft("");
      toast("โพสต์คำตอบแล้ว", "success");
      answers.refetch();
      thread.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setPosting(false);
    }
  }

  async function accept(answer: QaAnswer) {
    setAccepting(answer.id);
    try {
      await api.post(`/qa/threads/${threadId}/accept/`, {
        body: { answer_id: answer.id },
      });
      toast("เลือกเป็นคำตอบที่ดีที่สุดแล้ว ⭐", "success");
      thread.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setAccepting(null);
    }
  }

  if (thread.error) {
    return (
      <PageContainer>
        <ErrorState error={thread.error} onRetry={thread.refetch} />
      </PageContainer>
    );
  }
  if (thread.loading || !data) {
    return (
      <PageContainer>
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-32 w-full rounded-surface" />
          <Skeleton className="h-24 w-full rounded-surface" />
        </div>
      </PageContainer>
    );
  }

  const target = data.recipe ?? data.course;
  const targetHref = data.recipe
    ? `/recipes/${data.recipe.slug}`
    : data.course
      ? `/courses/${data.course.slug}`
      : null;
  const rows = answers.data?.results ?? [];

  return (
    <PageContainer>
      <Link
        href="/threads"
        className="text-sm text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
      >
        ← กลับไปหน้ากระทู้
      </Link>

      {/* ---- The question ---- */}
      <Card className="mt-3">
        <CardBody>
          <div className="flex flex-wrap items-center gap-1.5">
            {acceptedId ? (
              <Badge tone="success">มีคำตอบที่เลือกแล้ว</Badge>
            ) : data.status === "answered" ? (
              <Badge tone="mint">ตอบแล้ว</Badge>
            ) : (
              <Badge tone="butter">รอคำตอบ</Badge>
            )}
            {target && targetHref ? (
              <Link
                href={targetHref}
                className="rounded-full bg-surface-sunken px-2.5 py-0.5 text-xs text-fg-muted hover:text-fg"
              >
                {data.recipe ? "สูตร" : "คอร์ส"}: {target.title}
              </Link>
            ) : null}
          </div>
          <h1 className="font-display mt-2 text-xl font-medium text-fg sm:text-2xl">
            {data.title}
          </h1>
          {data.body ? (
            <p className="mt-2 whitespace-pre-wrap text-sm text-fg-muted">
              {data.body}
            </p>
          ) : null}
          <p className="mt-3 text-xs text-fg-subtle">
            ถามโดย @{data.author_handle} · {thaiDateTime(data.created_at)}
          </p>
        </CardBody>
      </Card>

      {/* ---- Answers ---- */}
      <h2 className="font-display mt-6 text-lg font-medium text-fg">
        คำตอบ ({answers.data?.count ?? 0})
      </h2>
      {answers.loading ? (
        <Skeleton className="mt-3 h-24 w-full rounded-surface" />
      ) : rows.length === 0 ? (
        <p className="mt-3 text-sm text-fg-muted">
          ยังไม่มีคำตอบ - เป็นคนแรกที่ช่วยตอบได้เลย
        </p>
      ) : (
        <ul className="mt-3 space-y-3">
          {rows.map((answer) => {
            const isAccepted = answer.id === acceptedId;
            return (
              <li key={answer.id}>
                <Card
                  className={cn(
                    isAccepted && "border-success/50 bg-success-subtle/30",
                  )}
                >
                  <CardBody>
                    {isAccepted ? (
                      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-success">
                        <Icon name="ui/check-circle" className="size-4" />
                        คำตอบที่ผู้ถามเลือก
                      </p>
                    ) : null}
                    <p className="whitespace-pre-wrap text-sm text-fg">
                      {answer.body}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-fg-subtle">
                        โดย @{answer.author_handle} ·{" "}
                        {thaiDateTime(answer.created_at)}
                      </p>
                      {isAsker && !isAccepted ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={accepting === answer.id}
                          onClick={() => void accept(answer)}
                        >
                          เลือกเป็นคำตอบที่ดีที่สุด
                        </Button>
                      ) : null}
                    </div>
                  </CardBody>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      {/* ---- Answer form ---- */}
      <div className="mt-6">
        {status === "authenticated" ? (
          <Card>
            <CardBody className="space-y-2.5">
              <p className="text-sm font-medium text-fg">ร่วมตอบคำถามนี้</p>
              <Textarea
                rows={3}
                value={draft}
                maxLength={4000}
                placeholder="แชร์ประสบการณ์หรือเทคนิคของคุณ…"
                aria-label="คำตอบของคุณ"
                onChange={(event) => setDraft(event.target.value)}
              />
              <div className="flex justify-end">
                <Button
                  size="sm"
                  disabled={!draft.trim()}
                  loading={posting}
                  onClick={() => void postAnswer()}
                >
                  โพสต์คำตอบ
                </Button>
              </div>
            </CardBody>
          </Card>
        ) : (
          <Card className="kb-hero border-none">
            <CardBody className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-fg-muted">
                เข้าสู่ระบบเพื่อร่วมตอบคำถามนี้
              </p>
              <Link href="/login">
                <Button size="sm">เข้าสู่ระบบ</Button>
              </Link>
            </CardBody>
          </Card>
        )}
      </div>
    </PageContainer>
  );
}
