"use client";

/**
 * One community post  photo-first.
 *
 * The photo leads, the story follows, and the attached recipe sits under
 * both as a clearly-marked reference so a showcase can never be mistaken
 * for a recipe.
 *
 * The action row carries only what the backend can actually do. The
 * gallery app has no likes, comments or bookmarks (its model docstring
 * calls interactions a future phase), so this renders a share/copy-link
 * action  which needs no backend  and nothing that would 404 on click.
 *
 * The author additionally gets hide/delete right on the card (with the
 * full editor one click away on the post page), so managing your own
 * posts never requires hunting through the feed one detail page at a
 * time. Ownership is decided by comparing handles from `useAuth`  a
 * cosmetic gate only; the backend re-authorises every mutation.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type { GalleryPost, RecipeListItem } from "@/lib/api/models";
import { relativeThai } from "@/lib/datetime";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { Card } from "@/components/ui/card";
import { CommunityImageGallery } from "@/components/community/image-gallery";
import { RecipeAttachmentCard } from "@/components/community/recipe-attachment-card";

/**
 * The only "post type" the data supports: whether a recipe is attached.
 * Question / tip / showcase would need a field the backend does not have,
 * so no badge claims one.
 */
function kindBadge(post: GalleryPost) {
  if (post.recipe) {
    return { label: "แชร์สูตร", icon: "ui/book-open" as const, tone: "bg-lavender-soft text-lavender-ink" };
  }
  if (post.images.length > 0) {
    return { label: "ผลงานของฉัน", icon: "ui/star" as const, tone: "bg-berry-soft text-berry-ink" };
  }
  return null;
}

export function CommunityPostCard({
  post,
  recipeDetails,
  headingLevel = "h3",
  onMutated,
}: {
  post: GalleryPost;
  /** Public recipe row matching the attachment, when the feed found one. */
  recipeDetails?: RecipeListItem | null;
  headingLevel?: "h2" | "h3";
  /** Called after the owner hides, shows or deletes the post, so the
   *  hosting feed can refetch. Owner actions render only when set. */
  onMutated?: () => void;
}) {
  const Heading = headingLevel;
  const { toast } = useToast();
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [armedDelete, setArmedDelete] = useState(false);
  const badge = kindBadge(post);
  const isOwner =
    Boolean(onMutated) && user !== null && user.username === post.author_handle;

  async function toggleHidden() {
    setBusy(true);
    try {
      await api.patch(`/gallery/${post.id}/`, {
        body: {
          status: post.status === "unpublished" ? "published" : "unpublished",
        },
      });
      toast(
        post.status === "unpublished"
          ? "แสดงโพสต์อีกครั้งแล้ว"
          : "ซ่อนโพสต์แล้ว มีเพียงคุณที่เห็น",
        "success",
      );
      onMutated?.();
    } catch {
      toast("บันทึกไม่สำเร็จ ลองอีกครั้งนะ", "danger");
    } finally {
      setBusy(false);
    }
  }

  async function removePost() {
    // Two-step arm-then-confirm on the button itself: a modal would be
    // heavier than the action deserves inside a feed card.
    if (!armedDelete) {
      setArmedDelete(true);
      setTimeout(() => setArmedDelete(false), 4000);
      return;
    }
    setBusy(true);
    try {
      await api.delete(`/gallery/${post.id}/`);
      toast("ลบโพสต์แล้ว", "success");
      onMutated?.();
    } catch {
      toast("ลบไม่สำเร็จ ลองอีกครั้งนะ", "danger");
      setBusy(false);
    }
  }

  async function copyLink() {
    const url = `${window.location.origin}/community/posts/${post.id}`;
    try {
      if (navigator.share) {
        await navigator.share({ url, title: `โพสต์ของ ${post.author_handle}` });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast("คัดลอกลิงก์โพสต์แล้ว", "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Share sheet dismissed, or the clipboard was refused.
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-3 px-4 pt-4">
        <Avatar src={post.author_avatar_url} name={post.author_display_name} />
        <div className="min-w-0 flex-1">
          <Heading className="font-display truncate text-sm font-medium text-fg">
            {post.author_display_name}
          </Heading>
          <p className="flex items-center gap-1.5 text-xs text-fg-subtle">
            {post.author_display_name !== post.author_handle ? (
              <>
                <span aria-hidden>@{post.author_handle}</span>
                <span aria-hidden>·</span>
              </>
            ) : null}
            <time dateTime={post.created_at}>{relativeThai(post.created_at)}</time>
            {post.status === "unpublished" ? (
              <span className="rounded bg-surface-sunken px-1.5 py-0.5 text-fg-muted">
                ซ่อนอยู่
              </span>
            ) : null}
          </p>
        </div>
        {badge ? (
          <span
            className={`flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${badge.tone}`}
          >
            <Icon name={badge.icon} className="size-3.5" />
            {badge.label}
          </span>
        ) : null}
      </div>

      {post.caption ? (
        <p className="whitespace-pre-wrap px-4 pt-3 text-sm text-fg">
          {post.caption}
        </p>
      ) : null}

      {post.images.length > 0 ? (
        <div className="mt-3">
          <CommunityImageGallery images={post.images} alt={post.caption} />
        </div>
      ) : null}

      {post.recipe || post.course ? (
        <div className="px-4 pt-3">
          <RecipeAttachmentCard
            recipe={post.recipe}
            course={post.course}
            details={recipeDetails}
          />
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-1 border-t border-edge px-2 py-1.5">
        <Link
          href={`/community/posts/${post.id}`}
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/chat" className="size-4" />
          เปิดโพสต์
        </Link>
        <button
          type="button"
          onClick={copyLink}
          aria-label={`คัดลอกลิงก์โพสต์ของ ${post.author_handle}`}
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name={copied ? "ui/check" : "ui/link"} className="size-4" />
          {copied ? "คัดลอกแล้ว" : "แชร์"}
        </button>
        {post.images.length > 1 ? (
          <span className="ml-auto pr-2 text-xs text-fg-subtle">
            {post.images.length} รูป
          </span>
        ) : null}
        {isOwner ? (
          <span
            className={`flex items-center gap-1 ${post.images.length > 1 ? "" : "ml-auto"}`}
          >
            <Link
              href={`/community/posts/${post.id}`}
              className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
            >
              <Icon name="ui/edit" className="size-4" tint />
              แก้ไข
            </Link>
            <button
              type="button"
              disabled={busy}
              onClick={toggleHidden}
              className="rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-50"
            >
              {post.status === "unpublished" ? "แสดงโพสต์" : "ซ่อน"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={removePost}
              className={`rounded-full px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-50 ${
                armedDelete
                  ? "bg-danger/10 font-medium text-danger"
                  : "text-fg-muted hover:bg-surface-sunken hover:text-danger"
              }`}
            >
              {armedDelete ? "ยืนยันลบ?" : "ลบ"}
            </button>
          </span>
        ) : null}
      </div>
    </Card>
  );
}
