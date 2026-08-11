"use client";

/** Edit a course: load the detail, hand it to the shared form. */

import { api } from "@/lib/api/client";
import type { CourseDetail } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import { CourseForm } from "../../course-form";

export function EditCourseScreen({ slug }: { slug: string }) {
  const course = useApiQuery(
    (signal) => api.get<CourseDetail>(`/courses/${slug}/`, { signal }),
    [slug],
  );

  if (course.loading) {
    return (
      <div aria-busy="true" className="space-y-3">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (course.error || !course.data) {
    return <ErrorState error={course.error} onRetry={course.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title={`แก้ไข: ${course.data.title}`}
        description="การแก้ไขมีผลทันทีที่บันทึก สถานะเผยแพร่จัดการจากหน้ารายการ"
      />
      <CourseForm initial={course.data} />
    </>
  );
}
