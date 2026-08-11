"use client";

/** Create a course - the form owns all the rules. */

import { AdminPageHeader } from "@/components/admin/admin-shell";
import { CourseForm } from "../course-form";

export default function AdminCourseNewPage() {
  return (
    <>
      <AdminPageHeader
        title="เพิ่มคอร์สเรียน"
        description="คอร์สใหม่เริ่มเป็นฉบับร่างเสมอ - เพิ่มบทเรียนให้ครบก่อนแล้วค่อยเผยแพร่จากหน้ารายการ"
      />
      <CourseForm />
    </>
  );
}
