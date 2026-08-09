"use client";

/**
 * Edit one recipe.
 *
 * The form is keyed on the loaded slug so that navigating between
 * recipes rebuilds its state from the new record instead of keeping the
 * previous recipe's ingredient rows.
 */

import Link from "next/link";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { RecipeDetail } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import { StatusBadge } from "@/components/admin/primitives";
import { RecipeForm } from "../../recipe-form";

export function EditRecipeScreen({ slug }: { slug: string }) {
  const recipe = useApiQuery(
    (signal) => api.get<RecipeDetail>(`/recipes/${slug}/`, { signal }),
    [slug],
  );

  if (recipe.loading) {
    return (
      <div aria-busy="true" className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full rounded-md" />
      </div>
    );
  }

  if (recipe.error || !recipe.data) {
    const notFound = recipe.error instanceof ApiError && recipe.error.status === 404;
    return (
      <div className="mx-auto max-w-md py-10 text-center">
        {notFound ? (
          <>
            <p className="font-mono text-sm font-semibold text-warning">404</p>
            <h1 className="mt-2 text-lg font-semibold text-fg">
              ไม่พบสูตรนี้
            </h1>
            <p className="mt-2 text-sm text-fg-muted">
              slug{" "}
              <code className="font-mono">{slug}</code>{" "}
              ไม่มีอยู่ในระบบ หรือถูกลบไปแล้ว
            </p>
            <Link href="/admin/recipes" className="mt-4 inline-block">
              <Button size="sm" variant="secondary">
                กลับไปรายการสูตร
              </Button>
            </Link>
          </>
        ) : (
          <ErrorState error={recipe.error} onRetry={recipe.refetch} />
        )}
      </div>
    );
  }

  return (
    <>
      <AdminPageHeader
        title={recipe.data.title}
        description={`แก้ไขสูตร · ผู้เขียน ${recipe.data.author.username}`}
        actions={
          <div className="flex items-center gap-3">
            <StatusBadge status={recipe.data.status} />
            <Link
              href={`/recipes/${recipe.data.slug}`}
              className="text-sm text-accent hover:text-accent-hover"
            >
              ดูหน้าจริง ↗
            </Link>
            <Link
              href="/admin/recipes"
              className="text-sm text-accent hover:text-accent-hover"
            >
              ← รายการสูตร
            </Link>
          </div>
        }
      />
      <RecipeForm key={recipe.data.slug} initial={recipe.data} />
    </>
  );
}
