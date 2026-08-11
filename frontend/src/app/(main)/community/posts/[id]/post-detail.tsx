"use client";

/**
 * One community post.
 *
 * Reads `GET /gallery/{id}/`, which serves the same public shape to
 * everyone  visibility is enforced server-side, so an unpublished post
 * simply 404s for anyone but its author and staff.
 *
 * Owner controls (edit caption/visibility, delete, remove a photo) are
 * shown when the post's public handle matches the signed-in user's. That
 * is a rendering decision only: `PATCH`/`DELETE /gallery/{id}/` refuse
 * anyone else regardless, and staff moderation lives in the admin area.
 *
 * There is no comment thread or bookmark button here because the gallery
 * app has neither  its model docstring states interactions are a future
 * phase. Inventing them would mean inventing a backend.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { GalleryPost } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { CommunityImageGallery } from "@/components/community/image-gallery";
import { CommunityPostCard } from "@/components/community/post-card";
import { RecipeAttachmentCard } from "@/components/community/recipe-attachment-card";
import { describeAdminError } from "@/components/admin/lifecycle";

export function PostDetailScreen({ id }: { id: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const post = useApiQuery(
    (signal) => api.get<GalleryPost>(`/gallery/${id}/`, { signal }),
    [id],
  );

  const data = post.data;
  const recipeId = data?.recipe?.id ?? null;

  const related = useApiQuery(
    (signal) =>
      recipeId
        ? api.get<Paginated<GalleryPost>>("/gallery/", {
            query: { recipe_id: recipeId, page_size: 4 },
            signal,
          })
        : Promise.resolve(null),
    [recipeId],
  );

  if (post.loading) {
    return (
      <PageContainer>
        <div className="mx-auto max-w-2xl space-y-4" aria-busy="true">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-96 w-full rounded-surface" />
        </div>
      </PageContainer>
    );
  }

  if (post.error || !data) {
    const notFound = post.error instanceof ApiError && post.error.status === 404;
    return (
      <PageContainer>
        <div className="mx-auto max-w-md py-12 text-center">
          {notFound ? (
            <>
              <h1 className="font-display mt-3 text-xl font-medium text-fg">
                ไม่พบโพสต์นี้
              </h1>
              <p className="mt-2 text-sm text-fg-muted">
                โพสต์อาจถูกลบไปแล้ว หรือเจ้าของตั้งเป็นซ่อนอยู่
              </p>
              <Link href="/community" className="mt-5 inline-block">
                <Button variant="secondary">ไปที่ชุมชน</Button>
              </Link>
            </>
          ) : (
            <ErrorState error={post.error} onRetry={post.refetch} />
          )}
        </div>
      </PageContainer>
    );
  }

  const isOwner = Boolean(user && user.username === data.author_handle);
  const relatedPosts = (related.data?.results ?? []).filter(
    (item) => item.id !== data.id,
  );

  async function saveCaption() {
    setBusy(true);
    try {
      await api.patch(`/gallery/${id}/`, { body: { caption: draft.trim() } });
      toast("แก้ไขโพสต์แล้ว", "success");
      setEditing(false);
      post.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  async function toggleVisibility() {
    // Read through the hook rather than the narrowed alias: a hoisted
    // function declaration does not carry the outer narrowing.
    const wasPublished = post.data?.status === "published";
    setBusy(true);
    try {
      await api.patch(`/gallery/${id}/`, {
        body: { status: wasPublished ? "unpublished" : "published" },
      });
      toast(
        wasPublished ? "ซ่อนโพสต์แล้ว" : "แสดงโพสต์อีกครั้งแล้ว",
        "success",
      );
      post.refetch();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  async function removePost() {
    setBusy(true);
    try {
      await api.delete(`/gallery/${id}/`);
      toast("ลบโพสต์แล้ว", "success");
      router.push("/community");
      router.refresh();
    } catch (error) {
      toast(describeAdminError(error), "danger");
      setBusy(false);
    }
  }

  return (
    <PageContainer>
      <div className="mx-auto max-w-2xl">
        <Link
          href="/community"
          className="text-sm text-accent hover:text-accent-hover"
        >
          ← กลับไปชุมชน
        </Link>

        <Card className="mt-3 overflow-hidden">
          <div className="flex items-center gap-3 px-5 pt-5">
            <Avatar
              src={data.author_avatar_url}
              name={data.author_display_name}
              size="lg"
              className="size-11 text-base"
            />
            <div className="min-w-0">
              <h1 className="font-display truncate text-base font-medium text-fg">
                {data.author_display_name}
              </h1>
              <p className="text-xs text-fg-subtle">
                <time dateTime={data.created_at}>
                  {relativeThai(data.created_at)}
                </time>
                {data.status === "unpublished" ? (
                  <span className="ml-2 rounded bg-surface-sunken px-1.5 py-0.5 text-fg-muted">
                    ซ่อนอยู่  เห็นเฉพาะคุณ
                  </span>
                ) : null}
              </p>
            </div>
          </div>

          {editing ? (
            <div className="px-5 pt-4">
              <label htmlFor="edit-caption" className="sr-only">
                แก้ไขเนื้อหาโพสต์
              </label>
              <textarea
                id="edit-caption"
                value={draft}
                rows={5}
                maxLength={500}
                onChange={(event) => setDraft(event.target.value)}
                className="block w-full resize-y rounded-control border border-edge-strong/50 bg-surface px-3.5 py-2.5 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
              />
              <div className="mt-2 flex gap-2">
                <Button size="sm" loading={busy} onClick={saveCaption}>
                  บันทึก
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setEditing(false)}
                >
                  ยกเลิก
                </Button>
              </div>
            </div>
          ) : data.caption ? (
            <p className="whitespace-pre-wrap px-5 pt-4 text-sm text-fg">
              {data.caption}
            </p>
          ) : null}

          {data.images.length > 0 ? (
            <div className="mt-4">
              <CommunityImageGallery images={data.images} alt={data.caption} />
            </div>
          ) : null}

          {data.recipe || data.course ? (
            <div className="px-5 pb-5 pt-4">
              <RecipeAttachmentCard recipe={data.recipe} course={data.course} />
            </div>
          ) : (
            <div className="pb-5" />
          )}

          {isOwner ? (
            <CardBody className="flex flex-wrap gap-2 border-t border-edge">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setDraft(data.caption);
                  setEditing(true);
                }}
              >
                <Icon name="ui/edit" className="size-4" /> แก้ไขข้อความ
              </Button>
              <Button
                size="sm"
                variant="secondary"
                loading={busy}
                onClick={toggleVisibility}
              >
                {data.status === "published" ? "ซ่อนโพสต์" : "แสดงโพสต์"}
              </Button>
              <Button
                size="sm"
                variant="danger"
                className="ml-auto"
                onClick={() => setConfirmingDelete(true)}
              >
                ลบโพสต์
              </Button>
            </CardBody>
          ) : null}
        </Card>

        {/* Interactions the backend does not have yet  stated, not faked. */}
        <p className="mt-3 text-center text-xs text-fg-subtle">
          ระบบคอมเมนต์และบันทึกโพสต์ยังไม่เปิดใช้งานในเวอร์ชันนี้
        </p>

        {relatedPosts.length > 0 ? (
          <section className="mt-8">
            <div className="mb-3 flex items-baseline justify-between gap-2">
              <h2 className="font-display text-lg font-medium text-fg">
                โพสต์อื่นเกี่ยวกับสูตรนี้
              </h2>
              <Link
                href={`/community?recipe=${recipeId}`}
                className="text-sm text-accent hover:text-accent-hover"
              >
                ดูทั้งหมด →
              </Link>
            </div>
            <ul className="space-y-4">
              {relatedPosts.slice(0, 3).map((item) => (
                <li key={item.id}>
                  <CommunityPostCard post={item} />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      {confirmingDelete ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="ยืนยันการลบโพสต์"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
        >
          <Card className="w-full max-w-sm">
            <CardBody>
              <h2 className="font-display text-base font-medium text-fg">
                ลบโพสต์นี้?
              </h2>
              <p className="mt-2 text-sm text-fg-muted">
                โพสต์และรูปทั้งหมดจะถูกลบถาวร {" "}
                <strong>สูตรที่แนบไว้จะไม่ถูกลบ</strong> ยังอยู่ครบเหมือนเดิม
              </p>
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setConfirmingDelete(false)}
                >
                  ยกเลิก
                </Button>
                <Button size="sm" variant="danger" loading={busy} onClick={removePost}>
                  ลบโพสต์
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      ) : null}
    </PageContainer>
  );
}
