"use client";

/**
 * Floating AI-assistant chat widget - UI over the existing assistant
 * API only, no new AI backend.
 *
 * Lifecycle (deliberate): opening the widget never touches the
 * database. The conversation is created (`POST
 * /assistant/conversations/`) lazily, right before the first message is
 * sent, so empty conversations are never persisted. The id then lives
 * in component state only - the widget mounts once in the app shell, so
 * it survives in-app navigation and is discarded on refresh, exactly
 * the "new chat per browser session" contract. Full history stays on
 * `/assistant` (the kebab menu links there); this panel shows only the
 * messages exchanged in the current session.
 *
 * A 503 `assistant_unavailable` is special-cased per the API contract:
 * the user's message IS saved server-side, so the bubble stays and a
 * notice invites a retry - re-sending the same text would duplicate it.
 */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Conversation, Message } from "@/lib/api/models";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { Icon } from "@/components/ui/icon";
import { LottieLoop } from "@/components/ui/lottie-asset";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";

const BOT_LOTTIE = "/lottie/Chatbot.lottie";
const GREETING =
  "สวัสดีค่ะ 🍰 มีอะไรให้ช่วยเรื่องการอบขนมไหม? ถามเรื่องแป้ง เนย เตาอบ หรือเทคนิคได้เลย";

type LocalMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  /** Unpersisted status bubble (e.g. the 503 retry notice). */
  notice?: boolean;
};

function Bubble({ message }: { message: LocalMessage }) {
  const mine = message.role === "user";
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-surface px-3.5 py-2 text-sm leading-relaxed",
          mine
            ? "rounded-br-md bg-accent text-fg-inverted"
            : "rounded-bl-md bg-surface-sunken text-fg",
          message.notice && "bg-butter-soft text-fg-muted",
        )}
      >
        {message.content}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        className="flex items-center gap-1 rounded-surface rounded-bl-md bg-surface-sunken px-3.5 py-3"
        aria-label="ผู้ช่วยกำลังพิมพ์"
      >
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="size-1.5 animate-bounce rounded-full bg-fg-subtle"
            style={{ animationDelay: `${dot * 150}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

export function AssistantChatWidget() {
  const { status } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [open, setOpen] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const nextIdRef = useRef(1);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, sending, open]);

  // Anonymous visitors never see the widget - and none of the state
  // above outlives a login change badly (a logout unmounts it).
  if (status !== "authenticated") return null;

  function pushMessage(message: Omit<LocalMessage, "id">): number {
    const id = nextIdRef.current++;
    setMessages((prev) => [...prev, { ...message, id }]);
    return id;
  }

  async function send() {
    const content = draft.trim();
    if (!content || sending) return;
    setSending(true);
    setDraft("");
    const userMessageId = pushMessage({ role: "user", content });
    try {
      // Lazy persistence: the conversation row is created only now,
      // with the first message already in hand. A previously created id
      // is reused so retries never mint empty conversations.
      let id = conversationId;
      if (id === null) {
        const conversation = await api.post<Conversation>(
          "/assistant/conversations/",
          { body: { language: "th" } },
        );
        id = conversation.id;
        setConversationId(id);
      }
      const reply = await api.post<Message>(
        `/assistant/conversations/${id}/messages/`,
        { body: { content } },
      );
      pushMessage({ role: "assistant", content: reply.content });
    } catch (error) {
      if (error instanceof ApiError && error.code === "assistant_unavailable") {
        // The user's message was saved server-side - keep its bubble.
        pushMessage({
          role: "assistant",
          notice: true,
          content:
            "ผู้ช่วยไม่พร้อมใช้งานชั่วคราว ข้อความของคุณถูกบันทึกไว้แล้ว ลองถามใหม่อีกครั้งในอีกสักครู่นะคะ",
        });
      } else {
        // Not saved (rate limit, network, …): withdraw the bubble and
        // hand the text back so nothing silently disappears.
        setMessages((prev) =>
          prev.filter((message) => message.id !== userMessageId),
        );
        setDraft(content);
        toast(
          error instanceof ApiError ? error.message : "ส่งข้อความไม่สำเร็จ",
          "danger",
        );
      }
    } finally {
      setSending(false);
    }
  }

  // The launcher is ALWAYS mounted and always on top: the panel opens
  // above it rather than over it, so the same button that opened the
  // chat closes it. Hunting for a small × after an accidental tap is
  // exactly the frustration this avoids.
  const launcher = (
    <button
      type="button"
      onClick={() => setOpen((value) => !value)}
      aria-expanded={open}
      aria-label={open ? "ปิดผู้ช่วย AI" : "เปิดผู้ช่วย AI"}
      className="fixed bottom-4 right-4 z-60 flex size-16 items-center justify-center rounded-full bg-accent text-fg-inverted shadow-overlay transition-transform hover:-translate-y-0.5 hover:scale-105 hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus sm:bottom-5 sm:right-5"
    >
      <Icon name={open ? "ui/chevron-down" : "ui/chat"} className="size-8" />
    </button>
  );

  if (!open) return launcher;

  return (
    <>
      {launcher}
      <section
        role="dialog"
        aria-label="ผู้ช่วย AI"
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
        // `bottom-24`: clears the launcher's 4rem disc plus its offset,
        // so the button underneath stays fully clickable.
        className="fixed bottom-24 right-4 z-50 flex h-[min(32rem,calc(100dvh-9rem))] w-[min(24rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-surface border border-edge bg-surface shadow-overlay sm:bottom-26 sm:right-5"
      >
      <header className="flex items-center gap-2.5 border-b border-edge bg-canvas/60 px-3 py-2">
        <LottieLoop src={BOT_LOTTIE} className="size-9" />
        <div className="min-w-0 flex-1">
          <p className="font-display text-sm font-medium text-fg">ผู้ช่วย AI</p>
          <p className="truncate text-xs text-fg-subtle">
            พร้อมช่วยเรื่องการอบขนมตลอดเวลา
          </p>
        </div>
        <Dropdown
          align="end"
          trigger={
            <span
              aria-label="เมนูผู้ช่วย"
              className="flex size-8 items-center justify-center rounded-full text-lg leading-none text-fg-muted hover:bg-surface-sunken"
            >
              ⋮
            </span>
          }
          items={[
            {
              key: "history",
              label: "ดูประวัติการสนทนา",
              onSelect: () => {
                setOpen(false);
                router.push("/assistant");
              },
            },
          ]}
        />
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="ปิดผู้ช่วย AI"
          className="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/close" className="size-4" />
        </button>
      </header>

      <div
        ref={scrollRef}
        aria-live="polite"
        className="flex-1 space-y-2.5 overflow-y-auto p-3.5"
      >
        <Bubble
          message={{ id: 0, role: "assistant", content: GREETING }}
        />
        {messages.map((message) => (
          <Bubble key={message.id} message={message} />
        ))}
        {sending ? <TypingIndicator /> : null}
      </div>

      <form
        className="flex items-end gap-2 border-t border-edge p-2.5"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={1}
          autoFocus
          placeholder="เช่น ทำไมเค้กถึงยุบตรงกลาง?"
          aria-label="ข้อความถึงผู้ช่วย"
          className="max-h-28 min-h-0 flex-1 resize-none"
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <Button type="submit" size="sm" loading={sending} disabled={!draft.trim()}>
          ส่ง
        </Button>
        </form>
      </section>
    </>
  );
}
