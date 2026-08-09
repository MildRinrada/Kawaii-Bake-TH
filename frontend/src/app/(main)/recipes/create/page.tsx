"use client";

/**
 * Publish your own recipe.
 *
 * This is KawaiiBake's recipe *authoring tool*, not a social composer —
 * a structured form over `POST /recipes/`, which creates a draft owned by
 * the author. It reuses the same `RecipeForm` the admin area uses (one
 * implementation of a fiddly write contract, ADR-style: nested ingredient
 * and step collections, replace-on-PATCH, separate multipart cover) and
 * only swaps the chrome for the learner design system and the redirect
 * for the public recipe page.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { RequireAuth } from "@/lib/auth/require-auth";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageContainer } from "@/components/ui/page-container";
import { RecipeForm } from "@/app/admin/recipes/recipe-form";

/** The learner-side section wrapper: soft card instead of admin panel. */
function SoftPanel({
  title,
  description,
  actions,
  children,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      {title ? (
        <CardHeader
          title={
            <span>
              {title}
              {description ? (
                <span className="block text-xs font-normal text-fg-muted">
                  {description}
                </span>
              ) : null}
            </span>
          }
          actions={actions}
        />
      ) : null}
      <CardBody className="p-0">{children}</CardBody>
    </Card>
  );
}

export default function CreateRecipePage() {
  return (
    <PageContainer>
      <RequireAuth>
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-medium text-fg">
              เพิ่มสูตรอาหาร
            </h1>
            <p className="mt-1 text-sm text-fg-muted">
              เขียนสูตรของคุณให้ครบทั้งวัตถุดิบและขั้นตอน —
              ระบบจะบันทึกเป็นฉบับร่างไว้ก่อน คุณค่อยกดเผยแพร่เมื่อพร้อม
            </p>
          </div>
          <Link
            href="/recipes"
            className="shrink-0 text-sm text-accent hover:text-accent-hover"
          >
            ← กลับไปดูสูตรทั้งหมด
          </Link>
        </div>

        <Card className="mb-5 border-berry-soft bg-berry-soft/40">
          <CardBody className="text-sm text-fg">
            <p>
              <strong>อยากเล่าเรื่องขนมที่เพิ่งอบเฉย ๆ?</strong>{" "}
              นั่นคือโพสต์ในชุมชน ไม่ใช่สูตร —{" "}
              <Link href="/community/create" className="text-accent underline">
                ไปสร้างโพสต์แทน
              </Link>
            </p>
          </CardBody>
        </Card>

        <RecipeForm
          Panel={SoftPanel}
          showDelete={false}
          cancelHref="/recipes"
          redirectTo={(slug) => `/recipes/${encodeURIComponent(slug)}`}
        />
      </RequireAuth>
    </PageContainer>
  );
}
