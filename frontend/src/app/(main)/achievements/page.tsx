"use client";

/** Achievements: bilingual badge grid from the earned facts. */

import { api, type Paginated } from "@/lib/api/client";
import type { Achievement } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { Card, CardBody } from "@/components/ui/card";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";

function AchievementsContent() {
  const { data, loading, error, refetch } = useApiQuery(
    (signal) => api.get<Paginated<Achievement>>("/me/achievements/", { signal }),
    [],
  );

  return (
    <>
      <PageHeader
        title="ความสำเร็จ"
        description="เหรียญที่คุณปลดล็อกระหว่างการเดินทางสายเบเกอรี่"
      />
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
          <Skeleton className="h-32 w-full rounded-surface" />
          <Skeleton className="h-32 w-full rounded-surface" />
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          icon="🏅"
          title="ยังไม่มีเหรียญความสำเร็จ"
          description="เรียนจบคอร์สแรกเพื่อปลดล็อกเหรียญแรกของคุณ"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.results.map((achievement) => (
            <Card key={achievement.id}>
              <CardBody className="flex items-start gap-3.5">
                <span
                  aria-hidden
                  className="flex size-12 shrink-0 items-center justify-center rounded-full bg-butter-soft text-2xl"
                >
                  {achievement.badge?.icon || "🏅"}
                </span>
                <div className="min-w-0">
                  <h2 className="font-display font-medium text-fg">
                    {achievement.badge?.title_th ?? achievement.achievement_type}
                  </h2>
                  {achievement.badge?.title_en ? (
                    <p className="text-xs text-fg-subtle">
                      {achievement.badge.title_en}
                    </p>
                  ) : null}
                  <p className="mt-1 text-xs text-fg-muted">
                    ได้รับเมื่อ{" "}
                    {new Date(achievement.awarded_at).toLocaleDateString("th-TH", {
                      dateStyle: "medium",
                    })}
                  </p>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

export default function AchievementsPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <AchievementsContent />
      </RequireAuth>
    </PageContainer>
  );
}
