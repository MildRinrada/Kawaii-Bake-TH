"use client";

/**
 * The Thai-first AI assistant: conversation list + chat pane (stacked on
 * mobile, side-by-side on desktop). Real conversations, real replies —
 * the mock provider answers offline in development.
 */

import { useEffect, useRef, useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Conversation, ConversationDetail, Message } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";

function Bubble({ message }: { message: Message }) {
  const mine = message.role === "user";
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-surface px-4 py-2.5 text-sm leading-relaxed",
          mine
            ? "rounded-br-md bg-accent text-fg-inverted"
            : "rounded-bl-md bg-surface-sunken text-fg",
        )}
      >
        {message.content}
      </div>
    </div>
  );
}

function AssistantContent() {
  const { toast } = useToast();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Listing is owner-scoped and lives under /me/ (the assistant app's
  // `me.py` urlconf); /assistant/conversations/ is create-only.
  const conversations = useApiQuery(
    (signal) =>
      api.get<Paginated<Conversation>>("/me/assistant/conversations/", {
        signal,
      }),
    [],
  );
  const detail = useApiQuery(
    async (signal) => {
      if (activeId === null) return null;
      return api.get<ConversationDetail>(
        `/assistant/conversations/${activeId}/`,
        { signal },
      );
    },
    [activeId],
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [detail.data]);

  async function newConversation() {
    try {
      const conversation = await api.post<Conversation>(
        "/assistant/conversations/",
        { body: { language: "th" } },
      );
      conversations.refetch();
      setActiveId(conversation.id);
    } catch {
      toast("สร้างบทสนทนาไม่สำเร็จ", "danger");
    }
  }

  async function send() {
    const content = draft.trim();
    if (!content || activeId === null) return;
    setSending(true);
    try {
      await api.post(`/assistant/conversations/${activeId}/messages/`, {
        body: { content },
      });
      setDraft("");
      detail.refetch();
      conversations.refetch();
    } catch (error) {
      toast(
        error instanceof ApiError ? error.message : "ส่งข้อความไม่สำเร็จ",
        "danger",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="ผู้ช่วย AI 🤖"
        description="ถามเรื่องการอบขนมเป็นภาษาไทยได้เลย"
        actions={
          <Button variant="secondary" size="sm" onClick={() => void newConversation()}>
            + บทสนทนาใหม่
          </Button>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <Card className="self-start">
          <CardBody className="p-2">
            {conversations.loading ? (
              <Skeleton className="h-24 w-full" aria-busy="true" />
            ) : conversations.error ? (
              <ErrorState error={conversations.error} onRetry={conversations.refetch} />
            ) : !conversations.data || conversations.data.results.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-fg-muted">
                ยังไม่มีบทสนทนา
              </p>
            ) : (
              <ul className="max-h-96 space-y-1 overflow-y-auto">
                {conversations.data.results.map((conversation) => (
                  <li key={conversation.id}>
                    <button
                      type="button"
                      onClick={() => setActiveId(conversation.id)}
                      className={cn(
                        "w-full truncate rounded-control px-3 py-2 text-left text-sm",
                        "focus-visible:outline-2 focus-visible:outline-focus",
                        activeId === conversation.id
                          ? "bg-lavender-soft font-medium text-lavender-ink"
                          : "text-fg-muted hover:bg-surface-sunken",
                      )}
                    >
                      {conversation.title || `บทสนทนา #${conversation.id}`}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card className="flex min-h-[28rem] flex-col">
          {activeId === null ? (
            <CardBody className="flex flex-1 items-center justify-center">
              <EmptyState
                icon="💬"
                title="เริ่มคุยกับผู้ช่วยได้เลย"
                description="สร้างบทสนทนาใหม่ แล้วถามได้ทุกเรื่อง — แป้ง เนย เตาอบ เทคนิค"
                action={
                  <Button onClick={() => void newConversation()}>
                    เริ่มบทสนทนาแรก
                  </Button>
                }
              />
            </CardBody>
          ) : (
            <>
              <div
                ref={scrollRef}
                className="flex-1 space-y-3 overflow-y-auto p-5"
                aria-live="polite"
              >
                {detail.loading ? (
                  <Skeleton className="h-20 w-2/3" aria-busy="true" />
                ) : detail.error ? (
                  <ErrorState error={detail.error} onRetry={detail.refetch} />
                ) : detail.data?.messages.results.length === 0 ? (
                  <p className="py-8 text-center text-sm text-fg-muted">
                    พิมพ์คำถามแรกของคุณด้านล่างได้เลย 👇
                  </p>
                ) : (
                  detail.data?.messages.results.map((message) => (
                    <Bubble key={message.id} message={message} />
                  ))
                )}
              </div>
              <form
                className="flex items-end gap-2 border-t border-edge p-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  void send();
                }}
              >
                <Textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  rows={2}
                  placeholder="เช่น ทำไมเค้กถึงยุบตรงกลาง?"
                  aria-label="ข้อความถึงผู้ช่วย"
                  className="min-h-0 flex-1 resize-none"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void send();
                    }
                  }}
                />
                <Button type="submit" loading={sending} disabled={!draft.trim()}>
                  ส่ง
                </Button>
              </form>
            </>
          )}
        </Card>
      </div>
    </>
  );
}

export default function AssistantPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <AssistantContent />
      </RequireAuth>
    </PageContainer>
  );
}
