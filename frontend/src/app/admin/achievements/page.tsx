"use client";

/**
 * Achievement management (ADR 0027).
 *
 * Two staff surfaces behind `/admin/achievements/`:
 *
 * - **Badge catalogue**  full CRUD on badge definitions. DELETE is
 *   refused with 409 `badge_in_use` once a badge has ever been awarded;
 *   the correct move then is deactivation, and the UI says so.
 * - **Award ledger**  a paginated, cross-user read of who earned what.
 *   The ledger is append-only *by design*: awards are granted by the
 *   certificates app's own rules (and its `recalculate` path), never by
 *   hand, so there is no grant/revoke control to offer here.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { AdminAward, AdminBadge } from "@/lib/api/models";
import { badgeArt } from "@/lib/assets";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { ApiError } from "@/lib/api/errors";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Tabs } from "@/components/ui/tabs";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  DetailPanel,
  FilterSelect,
  Pagination,
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

/* ------------------------------------------------------------------ */
/* Shared vocabulary                                                   */
/* ------------------------------------------------------------------ */

/** Thai labels for the backend's `achievement_type` choices. */
const ACHIEVEMENT_TYPE_LABELS: Record<string, string> = {
  course_completed: "จบคอร์ส",
  first_course: "คอร์สแรก",
  ten_courses: "ครบ 10 คอร์ส",
  quiz_master: "เซียนแบบทดสอบ",
  recipe_author: "ผู้เขียนสูตร",
};

const ACHIEVEMENT_TYPE_OPTIONS = [
  { value: "", label: "ทุกประเภท" },
  ...Object.entries(ACHIEVEMENT_TYPE_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
];

/**
 * The asset keys under `public/achievements/` (file names minus `.svg`).
 * The picker previews these; a free-text input beside it still accepts
 * any key so a badge shipped before its artwork never blocks the form.
 */
const ICON_KEYS = [
  "course_completed",
  "first_course",
  "ten_courses",
  "quiz_master",
  "recipe_author",
  "default",
  "locked",
];

/**
 * Literal file path for a picker preview. `badgeArt` would remap keys
 * outside its known-slug set (e.g. `locked`) to the default artwork,
 * which is right for learner display but wrong for a picker that must
 * show exactly the file each key names.
 */
function iconPreview(key: string): string {
  return `/achievements/${key}.svg`;
}

/* ------------------------------------------------------------------ */
/* Badge editor (create + edit share one panel)                        */
/* ------------------------------------------------------------------ */

function BadgeEditor({
  badge,
  onClose,
  onSaved,
  onDeleted,
}: {
  /** `null` means "create". */
  badge: AdminBadge | null;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [slug, setSlug] = useState(badge?.slug ?? "");
  const [titleTh, setTitleTh] = useState(badge?.title_th ?? "");
  const [titleEn, setTitleEn] = useState(badge?.title_en ?? "");
  const [descriptionTh, setDescriptionTh] = useState(badge?.description_th ?? "");
  const [descriptionEn, setDescriptionEn] = useState(badge?.description_en ?? "");
  const [icon, setIcon] = useState(badge?.icon ?? "");
  const [isActive, setIsActive] = useState(badge?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  async function save() {
    setSaving(true);
    setFieldErrors({});
    // Same field set both ways: POST creates, PATCH by slug edits.
    // Empty strings are meaningful on PATCH (they clear a description).
    const body = {
      title_th: titleTh,
      title_en: titleEn,
      description_th: descriptionTh,
      description_en: descriptionEn,
      icon,
      is_active: isActive,
    };
    try {
      if (badge) {
        await api.patch(`/admin/achievements/${badge.slug}/`, { body });
      } else {
        await api.post("/admin/achievements/", { body: { slug, ...body } });
      }
      toast(badge ? "บันทึกการแก้ไขเหรียญแล้ว" : "สร้างเหรียญใหม่แล้ว", "success");
      onSaved();
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors());
        if (error.code === "duplicate_badge_slug") {
          // 409: the slug already names another badge  point at the field.
          setFieldErrors((current) => ({
            ...current,
            slug: ["slug นี้ถูกใช้กับเหรียญอื่นแล้ว กรุณาตั้งชื่อใหม่"],
          }));
        }
      }
      toast(describeAdminError(error), "danger");
    } finally {
      setSaving(false);
    }
  }

  async function destroy() {
    if (!badge) return;
    try {
      await api.delete(`/admin/achievements/${badge.slug}/`);
      toast(`ลบเหรียญ “${badge.title_th}” แล้ว`, "success");
      onDeleted();
    } catch (error) {
      if (error instanceof ApiError && error.code === "badge_in_use") {
        // The ledger already references this badge, so hard delete is
        // refused  deactivation hides it without rewriting history.
        toast(
          "ลบไม่ได้  มีผู้ใช้ได้รับเหรียญนี้ไปแล้ว ให้ปิดใช้งานแทนเพื่อซ่อนจากแคตตาล็อก",
          "danger",
        );
      } else {
        toast(describeAdminError(error), "danger");
      }
    }
  }

  return (
    <DetailPanel
      open
      title={badge ? `แก้ไขเหรียญ ${badge.title_th}` : "เพิ่มเหรียญใหม่"}
      onClose={onClose}
      footer={
        <>
          {badge ? (
            <Button
              size="sm"
              variant="danger"
              className="mr-auto"
              onClick={() =>
                confirm.ask({
                  title: "ลบเหรียญนี้ถาวร?",
                  body: `“${badge.title_th}” จะถูกลบออกจากแคตตาล็อก  ถ้ามีผู้ใช้ได้รับไปแล้วระบบจะไม่ยอมลบ และควรใช้ “ปิดใช้” แทน`,
                  confirmLabel: "ลบเหรียญ",
                  danger: true,
                  action: destroy,
                })
              }
            >
              ลบเหรียญ
            </Button>
          ) : null}
          <Button size="sm" variant="secondary" onClick={onClose}>
            ยกเลิก
          </Button>
          <Button size="sm" loading={saving} onClick={save}>
            {badge ? "บันทึกการแก้ไข" : "สร้างเหรียญ"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field
          label="slug"
          required
          errors={fieldErrors.slug}
          hint={
            badge
              ? "slug คือรหัสประจำเหรียญ เปลี่ยนไม่ได้หลังสร้าง"
              : "รหัสประจำเหรียญ เช่น first_course"
          }
        >
          {(control) => (
            <Input
              {...control}
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              // The slug is the PATCH identifier; renaming it would orphan
              // the award ledger's reference, so editing locks the field.
              disabled={badge !== null}
              className="font-mono"
            />
          )}
        </Field>

        <Field label="ชื่อ (ไทย)" required errors={fieldErrors.title_th}>
          {(control) => (
            <Input
              {...control}
              value={titleTh}
              onChange={(event) => setTitleTh(event.target.value)}
            />
          )}
        </Field>

        <Field label="ชื่อ (อังกฤษ)" required errors={fieldErrors.title_en}>
          {(control) => (
            <Input
              {...control}
              value={titleEn}
              onChange={(event) => setTitleEn(event.target.value)}
            />
          )}
        </Field>

        <Field label="คำอธิบาย (ไทย)" errors={fieldErrors.description_th}>
          {(control) => (
            <Textarea
              {...control}
              rows={2}
              value={descriptionTh}
              onChange={(event) => setDescriptionTh(event.target.value)}
            />
          )}
        </Field>

        <Field label="คำอธิบาย (อังกฤษ)" errors={fieldErrors.description_en}>
          {(control) => (
            <Textarea
              {...control}
              rows={2}
              value={descriptionEn}
              onChange={(event) => setDescriptionEn(event.target.value)}
            />
          )}
        </Field>

        <div className="space-y-1.5">
          <p className="text-sm font-medium text-fg">ไอคอน</p>
          <p className="text-xs text-fg-muted">
            เลือกจากงานศิลป์ที่มีอยู่ หรือพิมพ์รหัสไอคอนเอง (เว้นว่างเพื่อใช้ slug
            ของเหรียญเลือกภาพ)
          </p>
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
            {ICON_KEYS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setIcon(icon === key ? "" : key)}
                aria-pressed={icon === key}
                title={key}
                className={`flex flex-col items-center gap-1 rounded-md border p-2 focus-visible:outline-2 focus-visible:outline-focus ${
                  icon === key
                    ? "border-accent bg-accent-subtle"
                    : "border-edge hover:bg-surface-sunken"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size local SVG preview from public/ */}
                <img
                  src={iconPreview(key)}
                  alt=""
                  className="size-8 select-none"
                  draggable={false}
                />
                <span className="w-full truncate font-mono text-[10px] text-fg-subtle">
                  {key}
                </span>
              </button>
            ))}
          </div>
          <Field label="รหัสไอคอน" errors={fieldErrors.icon}>
            {(control) => (
              <Input
                {...control}
                value={icon}
                onChange={(event) => setIcon(event.target.value)}
                placeholder="เช่น first_course"
                className="font-mono"
              />
            )}
          </Field>
        </div>

        <Switch
          checked={isActive}
          onChange={setIsActive}
          label="เปิดใช้งานเหรียญนี้"
          description="เหรียญที่ปิดใช้จะหายจากแคตตาล็อกฝั่งผู้เรียน แต่ประวัติการได้รับเดิมยังอยู่ครบ"
        />
      </div>

      {confirm.dialog}
    </DetailPanel>
  );
}

/* ------------------------------------------------------------------ */
/* Tab 1: badge catalogue                                              */
/* ------------------------------------------------------------------ */

type EditorState = { mode: "create" } | { mode: "edit"; badge: AdminBadge };

function BadgeCatalog() {
  const [editor, setEditor] = useState<EditorState | null>(null);

  // Unpaginated by design: the catalogue is a handful of definitions.
  const list = useApiQuery(
    (signal) => api.get<AdminBadge[]>("/admin/achievements/", { signal }),
    [],
  );

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  const rows = list.data ?? [];

  return (
    <>
      <AdminPanel>
        <DataTableToolbar
          actions={
            <>
              <span className="self-center text-xs text-fg-muted">
                ทั้งหมด{" "}
                <span className="font-mono tabular-nums">{rows.length}</span>{" "}
                เหรียญ
              </span>
              <Button size="sm" onClick={() => setEditor({ mode: "create" })}>
                + เพิ่มเหรียญ
              </Button>
            </>
          }
        >
          <span className="text-xs text-fg-muted">
            แคตตาล็อกเหรียญทั้งหมด  คลิกแถวเพื่อแก้ไข
          </span>
        </DataTableToolbar>

        <DataTable
          caption="เหรียญรางวัลทั้งหมดในแคตตาล็อก"
          loading={list.loading}
          rows={rows}
          rowKey={(row) => row.slug}
          onRowClick={(row) => setEditor({ mode: "edit", badge: row })}
          empty={
            <AdminEmpty
              title="ยังไม่มีเหรียญในแคตตาล็อก"
              description="กด “+ เพิ่มเหรียญ” เพื่อสร้างเหรียญแรก"
            />
          }
          columns={[
            {
              key: "art",
              header: "เหรียญ",
              className: "w-px",
              render: (row) => (
                // eslint-disable-next-line @next/next/no-img-element -- fixed-size local badge art from public/
                <img
                  src={badgeArt(row.icon || row.slug, row.is_active)}
                  alt=""
                  className="size-9 select-none"
                  draggable={false}
                />
              ),
            },
            {
              key: "title",
              header: "ชื่อ",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">{row.title_th}</p>
                  <p className="line-clamp-1 text-xs text-fg-subtle">
                    {row.title_en}
                  </p>
                </div>
              ),
            },
            {
              key: "description",
              header: "คำอธิบาย",
              render: (row) => (
                <span className="line-clamp-2 text-xs text-fg-muted">
                  {row.description_th || ""}
                </span>
              ),
            },
            {
              key: "awarded",
              header: "จำนวนคนได้รับ",
              numeric: true,
              render: (row) => row.awarded_count,
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => (
                <StatusBadge status={row.is_active ? "active" : "hidden"} />
              ),
            },
          ]}
        />
      </AdminPanel>

      {editor !== null ? (
        <BadgeEditor
          // Remount per target so the form state re-seeds from the row.
          key={editor.mode === "edit" ? editor.badge.slug : "create"}
          badge={editor.mode === "edit" ? editor.badge : null}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            list.refetch();
          }}
          onDeleted={() => {
            setEditor(null);
            list.refetch();
          }}
        />
      ) : null}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Tab 2: award ledger                                                 */
/* ------------------------------------------------------------------ */

function AwardLedger() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [type, setType] = useState("");

  // Empty filters are omitted: the endpoint 400s on unknown/blank keys.
  const list = usePagedList<AdminAward>("/admin/achievements/awards/", {
    search: search || undefined,
    achievement_type: type || undefined,
  });

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;

  return (
    <AdminPanel>
      <DataTableToolbar
        actions={
          <span className="self-center text-xs text-fg-muted">
            ทั้งหมด{" "}
            <span className="font-mono tabular-nums">{list.count}</span> รายการ
          </span>
        }
      >
        <SearchInput
          value={searchInput}
          onChange={setSearchInput}
          placeholder="ค้นหาผู้ได้รับ…"
          label="ค้นหาประวัติการได้รับ"
        />
        <FilterSelect
          label="ประเภท"
          value={type}
          options={ACHIEVEMENT_TYPE_OPTIONS}
          onChange={setType}
        />
      </DataTableToolbar>

      {/* The ledger is append-only by design: awards come from the
          certificates app's own rules, never granted or revoked by hand,
          so this table deliberately offers no write actions. */}
      <p className="border-b border-edge bg-surface-sunken/60 px-3 py-2 text-xs text-fg-muted">
        ประวัติการได้รับเป็นบันทึกแบบเพิ่มอย่างเดียว  ระบบมอบเหรียญอัตโนมัติตามกติกาฝั่งเซิร์ฟเวอร์
        ไม่มีการมอบหรือถอนด้วยมือ
      </p>

      <DataTable
        caption="ประวัติการได้รับเหรียญข้ามผู้ใช้"
        loading={list.loading}
        rows={list.rows}
        rowKey={(row) => row.id}
        empty={
          <AdminEmpty
            title="ไม่พบประวัติการได้รับที่ตรงกับเงื่อนไข"
            description="ลองล้างคำค้นหรือเปลี่ยนตัวกรองประเภท"
          />
        }
        columns={[
          {
            key: "user",
            header: "ผู้ได้รับ",
            render: (row) => (
              <div className="min-w-0">
                <p className="line-clamp-1 font-medium">{row.display_name}</p>
                <p className="font-mono text-xs text-fg-subtle">
                  @{row.username}
                </p>
              </div>
            ),
          },
          {
            key: "badge",
            header: "เหรียญ",
            render: (row) => (
              <span className="flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size local badge art from public/ */}
                <img
                  src={badgeArt(
                    row.badge?.icon || row.achievement_type,
                    true,
                  )}
                  alt=""
                  className="size-6 select-none"
                  draggable={false}
                />
                <span className="line-clamp-1">
                  {row.badge?.title_th || row.achievement_type}
                </span>
              </span>
            ),
          },
          {
            key: "type",
            header: "ประเภท",
            render: (row) => (
              <span className="text-xs text-fg-muted">
                {ACHIEVEMENT_TYPE_LABELS[row.achievement_type] ??
                  row.achievement_type}
              </span>
            ),
          },
          {
            key: "awarded",
            header: "ได้รับเมื่อ",
            render: (row) => (
              <span className="whitespace-nowrap text-xs text-fg-muted">
                {relativeThai(row.awarded_at)}
              </span>
            ),
          },
        ]}
      />

      <Pagination
        page={list.page}
        pageSize={list.pageSize}
        count={list.count}
        onPage={list.setPage}
      />
    </AdminPanel>
  );
}

/* ------------------------------------------------------------------ */

export default function AdminAchievementsPage() {
  return (
    <>
      <AdminPageHeader
        title="ความสำเร็จ"
        description="จัดการแคตตาล็อกเหรียญรางวัล และดูประวัติการได้รับของผู้ใช้ทุกคน"
      />
      <Tabs
        items={[
          { key: "badges", label: "เหรียญรางวัล", content: <BadgeCatalog /> },
          { key: "awards", label: "ประวัติการได้รับ", content: <AwardLedger /> },
        ]}
      />
    </>
  );
}
