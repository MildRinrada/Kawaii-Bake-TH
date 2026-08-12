"use client";

/**
 * Likes and comments on one post (ADR 0032).
 *
 * Counts come from the post payload, which the API aggregates live -
 * nothing here keeps its own tally beyond the optimistic flip a tap
 * needs to feel instant, and a failed request puts the old state back.
 * Anonymous visitors see the real counts and are sent to sign in;
 * nothing is disabled with a vague "coming soon".
 */

import Link from "next/link";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type { GalleryPost, Schemas } from "@/lib/api/models";
import { relativeThai } from "@/lib/datetime";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";

type GalleryComment = Schemas["GalleryComment"];

const COMMENT_PAGE = 50;

export function PostInteractions({
  post,
  /** Open the comment list from the start (the post's own page). */
  defaultOpen = false,
}: {
  post: GalleryPost;
  defaultOpen?: boolean;
}) {
  const { status, user } = useAuth();
  const { toast } = useToast();

  const [liked, setLiked] = useState(Boolean(post.viewer_has_liked));
  const [likes, setLikes] = useState(post.like_count ?? 0);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(defaultOpen);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);

  const comments = useApiQuery(
    (signal) =>
      open
        ? api.get<Paginated<GalleryComment>>(`/gallery/${post.id}/comments/`, {
            query: { page_size: COMMENT_PAGE },
            signal,
          })
        : Promise.resolve(null),
    [open, post.id],
  );
  const commentCount = comments.data?.count ?? post.comment_count ?? 0;
  const authenticated = status === "authenticated";

  async function toggleLike() {
    if (!authenticated || busy) return;
    const next = !liked;
    // Optimistic: the tap must land immediately; the server's count
    // replaces the guess a moment later.
    setLiked(next);
    setLikes((count) => count + (next ? 1 : -1));
    setBusy(true);
    try {
      const result = await (next
        ? api.post<{ liked: boolean; like_count: number }>(
            `/gallery/${post.id}/like/`,
          )
        : api.delete<{ liked: boolean; like_count: number }>(
            `/gallery/${post.id}/like/`,
          ));
      if (result && typeof result.like_count === "number") {
        setLikes(result.like_count);
        setLiked(result.liked);
      }
    } catch {
      setLiked(!next);
      setLikes((count) => count + (next ? -1 : 1));
      toast("ทำรายการไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setBusy(false);
    }
  }

  async function submitComment() {
    const body = draft.trim();
    if (!body) return;
    setPosting(true);
    try {
      await api.post(`/gallery/${post.id}/comments/`, { body: { body } });
      setDraft("");
      comments.refetch();
    } catch {
      toast("ส่งคอมเมนต์ไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setPosting(false);
    }
  }

  async function removeComment(comment: GalleryComment) {
    try {
      await api.delete(`/gallery/comments/${comment.id}/`);
      toast("ลบคอมเมนต์แล้ว", "neutral");
      comments.refetch();
    } catch {
      toast("ลบไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    }
  }

  return (
    <div>
      <div className="flex items-center gap-1 border-t border-edge px-2 py-1.5">
        <button
          type="button"
          disabled={busy || !authenticated}
          onClick={() => void toggleLike()}
          aria-pressed={liked}
          aria-label={liked ? "เลิกถูกใจโพสต์นี้" : "ถูกใจโพสต์นี้"}
          title={authenticated ? undefined : "เข้าสู่ระบบเพื่อกดถูกใจ"}
          className={cn(
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus",
            liked
              ? "text-accent"
              : "text-fg-muted hover:bg-surface-sunken hover:text-fg",
            !authenticated && "cursor-default",
          )}
        >
          <Icon
            tint
            name={liked ? "ui/heart-filled-2" : "ui/heart"}
            className="size-4"
          />
          {likes > 0 ? likes : "ถูกใจ"}
        </button>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/chat" className="size-4" />
          {commentCount > 0 ? `${commentCount} คอมเมนต์` : "คอมเมนต์"}
        </button>
      </div>

      {open ? (
        <div className="space-y-3 border-t border-edge px-4 py-3">
          {comments.loading ? (
            <p className="text-sm text-fg-subtle">กำลังโหลดคอมเมนต์…</p>
          ) : (comments.data?.results.length ?? 0) === 0 ? (
            <p className="text-sm text-fg-subtle">
              ยังไม่มีคอมเมนต์ — เป็นคนแรกที่ชมผลงานนี้ได้เลย
            </p>
          ) : (
            <ul className="space-y-3">
              {comments.data?.results.map((comment) => {
                const mine =
                  authenticated &&
                  (user?.username === comment.author_handle ||
                    user?.username === post.author_handle);
                return (
                  <li key={comment.id} className="flex gap-2.5">
                    <Avatar
                      src={comment.author_avatar_url}
                      name={comment.author_display_name}
                      size="sm"
                    />
                    <div className="min-w-0 flex-1 rounded-surface bg-surface-sunken px-3 py-2">
                      <p className="flex flex-wrap items-baseline gap-x-2 text-xs text-fg-subtle">
                        <span className="font-medium text-fg">
                          {comment.author_display_name}
                        </span>
                        <time dateTime={comment.created_at}>
                          {relativeThai(comment.created_at)}
                        </time>
                        {mine ? (
                          <button
                            type="button"
                            onClick={() => void removeComment(comment)}
                            className="ml-auto text-danger hover:underline focus-visible:outline-2 focus-visible:outline-focus"
                          >
                            ลบ
                          </button>
                        ) : null}
                      </p>
                      <p className="mt-0.5 whitespace-pre-wrap text-sm text-fg">
                        {comment.body}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {authenticated ? (
            <div className="flex items-end gap-2">
              <Textarea
                rows={1}
                value={draft}
                maxLength={1000}
                placeholder="เขียนคอมเมนต์…"
                aria-label="คอมเมนต์ของคุณ"
                className="max-h-28 min-h-0 flex-1 resize-none"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submitComment();
                  }
                }}
              />
              <Button
                size="sm"
                loading={posting}
                disabled={!draft.trim()}
                onClick={() => void submitComment()}
              >
                ส่ง
              </Button>
            </div>
          ) : (
            <p className="text-sm text-fg-muted">
              <Link href="/login" className="underline hover:text-fg">
                เข้าสู่ระบบ
              </Link>{" "}
              เพื่อกดถูกใจและคอมเมนต์
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
