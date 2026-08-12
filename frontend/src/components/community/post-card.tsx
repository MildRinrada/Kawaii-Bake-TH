"use client";

/**
 * One community post  photo-first.
 *
 * The photo leads, the story follows, and the attached recipe sits under
 * both as a clearly-marked reference so a showcase can never be mistaken
 * for a recipe.
 *
 * The action row carries only what the backend can actually do: likes
 * and comments are real endpoints now (ADR 0032), share copies a link,
 * and nothing renders that would 404 on click.
 *
 * Owner actions (edit / hide / delete) live in a `⋯` menu in the card's
 * corner rather than beside the social actions - "share" and "delete"
 * are not the same kind of button, and delete is styled as the danger
 * it is. Ownership is decided by comparing handles from `useAuth`  a
 * cosmetic gate only; the backend re-authorises every mutation.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import type { GalleryPost, RecipeListItem } from "@/lib/api/models";
import { relativeThai } from "@/lib/datetime";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { Card } from "@/components/ui/card";
import { Dropdown } from "@/components/ui/dropdown";
import { CommunityImageGallery } from "@/components/community/image-gallery";
import { PostInteractions } from "@/components/community/post-interactions";
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
  const router = useRouter();
  const [copied, setCopied] = useState(false);
  const badge = kindBadge(post);
  const isOwner =
    Boolean(onMutated) && user !== null && user.username === post.author_handle;

  async function toggleHidden() {
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
    }
  }

  async function removePost() {
    // The menu already hides this behind a deliberate open-and-pick, so
    // one confirm is the right amount of friction for an irreversible
    // delete.
    if (!window.confirm("ลบโพสต์นี้ถาวร? รูปและคอมเมนต์ทั้งหมดจะหายไปด้วย")) {
      return;
    }
    try {
      await api.delete(`/gallery/${post.id}/`);
      toast("ลบโพสต์แล้ว", "success");
      onMutated?.();
    } catch {
      toast("ลบไม่สำเร็จ ลองอีกครั้งนะ", "danger");
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
        {isOwner ? (
          <Dropdown
            align="end"
            trigger={
              <span
                aria-label="จัดการโพสต์ของฉัน"
                className="flex size-8 shrink-0 items-center justify-center rounded-full text-lg leading-none text-fg-muted hover:bg-surface-sunken"
              >
                ⋯
              </span>
            }
            items={[
              {
                key: "edit",
                label: "แก้ไขโพสต์",
                onSelect: () => router.push(`/community/posts/${post.id}`),
              },
              {
                key: "hide",
                label:
                  post.status === "unpublished" ? "แสดงโพสต์อีกครั้ง" : "ซ่อนโพสต์",
                onSelect: () => void toggleHidden(),
              },
              {
                key: "delete",
                label: "ลบโพสต์",
                danger: true,
                separator: true,
                onSelect: () => void removePost(),
              },
            ]}
          />
        ) : null}
      </div>

      {/* The post's own words are the content, so they outrank the
          card's metadata; an empty caption falls back to the recipe it
          was baked from rather than leaving a gap. */}
      {post.caption?.trim() ? (
        <p className="whitespace-pre-wrap px-4 pt-3 text-base leading-relaxed text-fg">
          {post.caption}
        </p>
      ) : post.recipe || post.course ? (
        <p className="px-4 pt-3 text-base text-fg-muted">
          ผลงานจาก{post.recipe ? "สูตร" : "คอร์ส"}{" "}
          <span className="text-fg">
            {post.recipe?.title ?? post.course?.title}
          </span>
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

      <div className="mt-3">
        <PostInteractions post={post} />
      </div>

      <div className="flex items-center gap-1 border-t border-edge px-2 py-1.5">
        <Link
          href={`/community/posts/${post.id}`}
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/eye" className="size-4" />
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
      </div>
    </Card>
  );
}
