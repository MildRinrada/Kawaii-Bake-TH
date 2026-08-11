"use client";

/**
 * The full-page post composer.
 *
 * Shares `PostComposerForm` with the inline composer on the feed, so the
 * two-step write (create post, then one multipart request per photo) has
 * exactly one implementation.
 *
 * `?recipe=<id>` pre-attaches a recipe  the contextual shortcut from a
 * recipe page. `?recipe_slug=` is an optional companion that lets the
 * preview card name the recipe without a lookup (the API has no
 * fetch-recipe-by-id endpoint).
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { api } from "@/lib/api/client";
import type { RecipeDetail } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { Card, CardBody } from "@/components/ui/card";
import { PageContainer } from "@/components/ui/page-container";
import { Skeleton } from "@/components/ui/skeleton";
import { PostComposerForm } from "@/components/community/post-composer-form";

function Composer() {
  const router = useRouter();
  const params = useSearchParams();

  const prefillId = Number(params.get("recipe")) || null;
  const prefillSlug = params.get("recipe_slug");

  const prefill = useApiQuery(
    (signal) =>
      prefillSlug
        ? api.get<RecipeDetail>(`/recipes/${prefillSlug}/`, { signal })
        : Promise.resolve(null),
    [prefillSlug],
  );

  // Wait for the prefill lookup before mounting the form: the attachment
  // is form state, seeded once at mount.
  if (prefillSlug && prefill.loading) {
    return <Skeleton className="h-96 w-full rounded-surface" />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-medium text-fg">สร้างโพสต์</h1>
          <p className="mt-1 text-sm text-fg-muted">
            เล่าเรื่องขนมที่คุณทำ แชร์รูป หรือถามเทคนิคจากเพื่อน ๆ
          </p>
        </div>
        <Link
          href="/community"
          className="shrink-0 text-sm text-accent hover:text-accent-hover"
        >
          ← กลับไปชุมชน
        </Link>
      </div>

      <Card>
        <CardBody>
          <PostComposerForm
            autoFocus
            initialAttachment={
              prefillId
                ? {
                    id: prefillId,
                    slug: prefill.data?.slug ?? "",
                    title: prefill.data?.title ?? "สูตรที่เลือกไว้",
                  }
                : null
            }
            onPublished={(post) => {
              router.push(`/community/posts/${post.id}`);
              router.refresh();
            }}
            onCancel={() => router.push("/community")}
          />
        </CardBody>
      </Card>
    </div>
  );
}

export default function CreateCommunityPostPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <Suspense fallback={<Skeleton className="h-96 w-full rounded-surface" />}>
          <Composer />
        </Suspense>
      </RequireAuth>
    </PageContainer>
  );
}
