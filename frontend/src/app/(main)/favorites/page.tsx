"use client";

/** Favorites: the caller's saved recipes and courses as one warm grid. */

import { api, type Paginated } from "@/lib/api/client";
import type { FavoriteItem } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { RecipeCard } from "@/components/content/recipe-card";
import { CourseCard } from "@/components/content/course-card";
import type { CourseListItem, RecipeListItem } from "@/lib/api/models";

function FavoritesContent() {
  const { data, loading, error, refetch } = useApiQuery(
    (signal) =>
      api.get<Paginated<FavoriteItem>>("/users/me/favorites/", { signal }),
    [],
  );

  return (
    <>
      <PageHeader
        title="รายการโปรด"
        description="สูตรและคอร์สที่คุณบันทึกไว้ — เห็นเฉพาะสิ่งที่ยังเปิดดูได้"
      />
      {loading ? (
        <div aria-busy="true" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-72 w-full rounded-surface" />
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          icon="♡"
          title="ยังไม่มีรายการโปรด"
          description="กดปุ่มหัวใจในหน้าสูตรหรือคอร์สเพื่อบันทึกไว้ที่นี่"
        />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {data.results.map((item, index) =>
            item.recipe ? (
              <RecipeCard
                key={`r-${index}`}
                recipe={item.recipe as unknown as RecipeListItem}
              />
            ) : item.course ? (
              <CourseCard
                key={`c-${index}`}
                course={item.course as unknown as CourseListItem}
              />
            ) : null,
          )}
        </div>
      )}
    </>
  );
}

export default function FavoritesPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <FavoritesContent />
      </RequireAuth>
    </PageContainer>
  );
}
