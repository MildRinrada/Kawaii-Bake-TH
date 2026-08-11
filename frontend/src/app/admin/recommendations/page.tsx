"use client";

/**
 * Recommendations - the staff debug lens on the live engine.
 *
 * `GET /admin/recommendations/preview/` runs the real scorer for any
 * username and returns the ranked rows *with their scores and reason
 * codes still attached* (staff-only by construction - the public feed
 * never carries a score). `GET /admin/recommendations/config/` reports
 * the weights exactly as deployed; they are code constants, not
 * settings, so this page renders them read-only.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { EngineConfig, RecommendationPreview } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  FilterSelect,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

const KINDS = [
  { value: "recipes", label: "สูตร" },
  { value: "courses", label: "คอร์ส" },
];

/** The engine's reason codes, translated for the operator. */
const REASON_LABELS: Record<string, string> = {
  matches_your_favorite_categories: "ตรงหมวดโปรด",
  similar_to_your_favorites: "คล้ายที่กดโปรด",
  similar_to_content_you_reviewed: "คล้ายที่เคยรีวิว",
  based_on_your_courses: "จากคอร์สที่เรียน",
  from_a_creator_you_like: "จากครีเอเตอร์ที่ชอบ",
  highly_rated: "คะแนนรีวิวสูง",
  popular: "ยอดนิยม",
  recently_published: "มาใหม่",
};

/** Every EngineConfig key with a short operator-facing label. */
const CONFIG_LABELS: { key: keyof EngineConfig; label: string }[] = [
  { key: "candidate_pool_size", label: "ขนาดกลุ่มตัวเลือก" },
  { key: "positive_review_min_rating", label: "คะแนนรีวิวขั้นต่ำที่นับเป็นชอบ" },
  { key: "w_category_match", label: "น้ำหนักหมวดที่สนใจ" },
  { key: "category_score_cap", label: "เพดานคะแนนจากหมวด" },
  { key: "w_author_affinity", label: "น้ำหนักครีเอเตอร์ที่ชอบ" },
  { key: "w_rating_average", label: "น้ำหนักคะแนนรีวิวเฉลี่ย" },
  { key: "w_rating_count", label: "น้ำหนักจำนวนรีวิว" },
  { key: "rating_count_cap", label: "เพดานจำนวนรีวิวที่นับ" },
  { key: "w_favorite_count", label: "น้ำหนักจำนวนกดโปรด" },
  { key: "favorite_count_cap", label: "เพดานจำนวนกดโปรดที่นับ" },
  { key: "w_recency", label: "น้ำหนักความใหม่" },
  { key: "recency_window_days", label: "ช่วงนับความใหม่ (วัน)" },
  { key: "w_difficulty_fit", label: "น้ำหนักความยากที่พอดี" },
  { key: "diversity_penalty", label: "ค่าปรับความซ้ำหมวด" },
  { key: "highly_rated_min_average", label: "เกณฑ์เฉลี่ยของ “คะแนนรีวิวสูง”" },
  { key: "highly_rated_min_count", label: "เกณฑ์จำนวนรีวิวของ “คะแนนรีวิวสูง”" },
  { key: "popular_min_favorites", label: "เกณฑ์กดโปรดของ “ยอดนิยม”" },
];

export default function AdminRecommendationsPage() {
  const [username, setUsername] = useState("");
  const [kind, setKind] = useState("recipes");
  const [preview, setPreview] = useState<RecommendationPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const config = useApiQuery(
    (signal) =>
      api.get<EngineConfig>("/admin/recommendations/config/", { signal }),
    [],
  );

  // Not usePagedList: the preview envelope is a one-shot result, not a
  // paginated list, and it should only run when the operator asks.
  async function runPreview(event: React.FormEvent) {
    event.preventDefault();
    const handle = username.trim();
    if (!handle) {
      setPreviewError("กรุณากรอกชื่อผู้ใช้ก่อนรันตัวอย่าง");
      return;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      setPreview(
        await api.get<RecommendationPreview>(
          "/admin/recommendations/preview/",
          { query: { username: handle, kind } },
        ),
      );
    } catch (error) {
      setPreview(null);
      setPreviewError(
        error instanceof ApiError && error.status === 404
          ? "ไม่พบผู้ใช้ชื่อนี้"
          : describeAdminError(error),
      );
    } finally {
      setPreviewLoading(false);
    }
  }

  // Links follow the kind of the *rendered* result, not the form state,
  // which may have changed since the run.
  const linkBase = preview?.kind === "courses" ? "/courses" : "/recipes";

  return (
    <>
      <AdminPageHeader
        title="การแนะนำ"
        description="เลนส์ดีบักของ engine แนะนำ - รันตัวจริงในนามผู้ใช้คนใดก็ได้ พร้อมคะแนนและเหตุผลที่ engine ให้เอง"
      />

      <div className="space-y-4">
        <AdminPanel
          title="ทดสอบ engine ในนามผู้ใช้"
          description="GET /admin/recommendations/preview/ - ผลลัพธ์คือฟีดจริงของผู้ใช้คนนั้น พร้อมคะแนนดิบ"
        >
          <div className="px-4 py-4">
            <form
              onSubmit={runPreview}
              noValidate
              className="flex flex-wrap items-end gap-2"
            >
              <Field
                label="ชื่อผู้ใช้"
                className="min-w-48 flex-1 sm:max-w-xs"
                errors={previewError ? [previewError] : undefined}
              >
                {(control) => (
                  <Input
                    {...control}
                    value={username}
                    placeholder="เช่น somchai"
                    onChange={(event) => {
                      setUsername(event.target.value);
                      if (previewError) setPreviewError(null);
                    }}
                  />
                )}
              </Field>
              <FilterSelect
                label="ชนิด"
                value={kind}
                options={KINDS}
                onChange={setKind}
              />
              <Button type="submit" size="sm" loading={previewLoading}>
                รันตัวอย่าง
              </Button>
            </form>

            {preview ? (
              <p className="mt-3 text-xs text-fg-muted">
                ผลของ{" "}
                <span className="font-mono">@{preview.username}</span> ชนิด{" "}
                {preview.kind === "courses" ? "คอร์ส" : "สูตร"} ทั้งหมด{" "}
                <span className="font-mono tabular-nums">{preview.count}</span>{" "}
                รายการ
              </p>
            ) : null}
          </div>

          {preview ? (
            <DataTable
              caption={`ผลการแนะนำของ @${preview.username}`}
              loading={previewLoading}
              rows={preview.items}
              rowKey={(row) => row.rank}
              empty={
                <AdminEmpty
                  title="engine ไม่มีรายการแนะนำให้ผู้ใช้คนนี้"
                  description="ผู้ใช้อาจยังมีข้อมูลความชอบไม่พอ หรือเนื้อหาที่เข้าเกณฑ์ถูกกรองออกหมด"
                />
              }
              columns={[
                {
                  key: "rank",
                  header: "อันดับ",
                  numeric: true,
                  className: "w-14",
                  render: (row) => row.rank,
                },
                {
                  key: "item",
                  header: "รายการ",
                  render: (row) =>
                    row.slug ? (
                      <div className="min-w-0">
                        <Link
                          href={`${linkBase}/${encodeURIComponent(row.slug)}`}
                          target="_blank"
                          className="line-clamp-1 font-medium hover:text-accent-hover hover:underline"
                        >
                          {row.title ?? row.slug}
                        </Link>
                        <p className="font-mono text-xs text-fg-subtle">
                          {row.slug}
                        </p>
                      </div>
                    ) : (
                      <span className="text-fg-subtle">มองไม่เห็นแล้ว</span>
                    ),
                },
                {
                  key: "score",
                  header: "คะแนน",
                  numeric: true,
                  render: (row) => row.score.toFixed(2),
                },
                {
                  key: "category",
                  header: "หมวดหลัก",
                  render: (row) => (
                    <span className="text-fg-muted">
                      {row.primary_category || "-"}
                    </span>
                  ),
                },
                {
                  key: "reasons",
                  header: "เหตุผล",
                  render: (row) => (
                    <span className="flex flex-wrap gap-1">
                      {row.reasons.map((reason) => (
                        <Badge key={reason} tone="lavender">
                          {REASON_LABELS[reason] ?? reason}
                        </Badge>
                      ))}
                    </span>
                  ),
                },
              ]}
            />
          ) : null}

          <p className="border-t border-edge px-4 py-3 text-xs text-fg-muted">
            คะแนนแสดงเฉพาะหน้านี้ (สำหรับผู้ดูแล) - ฟีดสาธารณะไม่มีคะแนนโดยตั้งใจ
            และหน้านี้ไม่เปิดเผยประวัติดิบของผู้ใช้
          </p>
        </AdminPanel>

        <AdminPanel
          title="น้ำหนักคะแนนของ engine (ตามที่ deploy จริง)"
          description="GET /admin/recommendations/config/ - ค่าคงที่ในโค้ด อ่านอย่างเดียว"
        >
          {config.error ? (
            <div className="p-4">
              <ErrorState error={config.error} onRetry={config.refetch} />
            </div>
          ) : (
            <dl className="grid gap-x-6 px-4 py-3 sm:grid-cols-2 xl:grid-cols-3">
              {CONFIG_LABELS.map(({ key, label }) => (
                <div
                  key={key}
                  className="flex items-baseline justify-between gap-3 border-b border-edge/60 py-1.5"
                >
                  <dt className="text-xs text-fg-muted">{label}</dt>
                  <dd className="font-mono text-sm tabular-nums text-fg">
                    {config.loading ? "…" : (config.data?.[key] ?? "")}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <p className="px-4 pb-3 pt-1 text-xs text-fg-muted">
            การแก้น้ำหนักคือการ deploy โค้ดพร้อมเทสต์ ไม่ใช่การตั้งค่า -
            หน้านี้จึงไม่มีปุ่มแก้ไข
          </p>
        </AdminPanel>
      </div>

      {/* The one honest gap: no impression/click logging exists, so no
          click-through numbers can be shown truthfully. */}
      <p className="mt-3 text-xs text-fg-muted">
        ยังไม่มีสถิติ click-through หรือ “เนื้อหาที่ถูกแนะนำบ่อย”
        เพราะระบบไม่เก็บ log การแสดงผลและการคลิกของฟีดแนะนำ
      </p>
    </>
  );
}
