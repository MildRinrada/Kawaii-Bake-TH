"use client";

import Link from "next/link";

import { AdminPageHeader } from "@/components/admin/admin-shell";
import { RecipeForm } from "../recipe-form";

export default function AdminRecipeCreatePage() {
  return (
    <>
      <AdminPageHeader
        title="เพิ่มสูตรใหม่"
        description="POST /recipes/ สร้างเป็นฉบับร่างเสมอ  เผยแพร่เป็นขั้นตอนแยกหลังตรวจความครบถ้วน"
        actions={
          <Link
            href="/admin/recipes"
            className="text-sm text-accent hover:text-accent-hover"
          >
            ← กลับไปรายการสูตร
          </Link>
        }
      />
      <RecipeForm />
    </>
  );
}
