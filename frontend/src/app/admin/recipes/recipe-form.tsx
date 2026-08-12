"use client";

/**
 * The recipe editor, shared by create and edit.
 *
 * Mirrors the backend write contract exactly:
 * - `POST /recipes/` always creates a **draft** authored by the caller;
 *   publishing is a separate transition, so this form never pretends to
 *   publish.
 * - `PATCH /recipes/{slug}/` **replaces** the ingredient and step
 *   collections whenever they are supplied. The form always loads the
 *   existing rows and sends them back, so editing one line cannot wipe
 *   the rest.
 * - `cover_image` is a file field, and DRF cannot parse nested object
 *   lists out of a multipart body  so the image goes in its own small
 *   multipart PATCH after the JSON write, exactly like the avatar.
 * - `slug` is frozen once published, except for staff. The field is
 *   offered with that warning rather than hidden.
 *
 * The readiness checklist below mirrors `assert_publishable`; the server
 * still decides, and its refusal is rendered verbatim.
 */

import { useRouter } from "next/navigation";
import { useRef, useState, type ComponentType, type ReactNode } from "react";

import { api } from "@/lib/api/client";
import type { Category, RecipeDetail } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useFormSubmit } from "@/lib/forms/use-form";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ImageCropper } from "@/components/ui/image-cropper";
import { COVER_ASPECT } from "@/components/content/cover-frame";
import { AdminPanel, useConfirm } from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

const DIFFICULTIES = [
  { value: "easy", label: "ง่าย" },
  { value: "medium", label: "ปานกลาง" },
  { value: "hard", label: "ยาก" },
  { value: "expert", label: "ระดับเชี่ยวชาญ" },
];

const VISIBILITIES = [
  { value: "public", label: "สาธารณะ" },
  { value: "unlisted", label: "ไม่แสดงในรายการ (เข้าผ่านลิงก์)" },
  { value: "private", label: "ส่วนตัว" },
];

/** `UnitEnum` plus the blank choice the serializer accepts. */
const UNITS = [
  { value: "", label: " ไม่ระบุ " },
  { value: "g", label: "กรัม (g)" },
  { value: "kg", label: "กิโลกรัม (kg)" },
  { value: "ml", label: "มิลลิลิตร (ml)" },
  { value: "l", label: "ลิตร (l)" },
  { value: "tsp", label: "ช้อนชา (tsp)" },
  { value: "tbsp", label: "ช้อนโต๊ะ (tbsp)" },
  { value: "cup", label: "ถ้วย (cup)" },
  { value: "piece", label: "ชิ้น" },
  { value: "pinch", label: "หยิบมือ" },
  { value: "slice", label: "แผ่น" },
  { value: "to_taste", label: "ตามชอบ" },
];

const MAX_INGREDIENTS = 50;
const MAX_STEPS = 50;
const MAX_CATEGORIES = 5;

interface IngredientRow {
  name: string;
  quantity: string;
  unit: string;
  note: string;
  group: string;
  is_optional: boolean;
}

interface StepRow {
  body: string;
  duration: string;
}

const EMPTY_INGREDIENT: IngredientRow = {
  name: "",
  quantity: "",
  unit: "",
  note: "",
  group: "",
  is_optional: false,
};

/**
 * The section wrapper. Injected so the same form can wear the dense
 * admin chrome or the learner UI's soft cards without either copy of
 * the (considerable) write logic drifting from the other.
 */
export type FormPanel = ComponentType<{
  title?: string;
  description?: string;
  actions?: ReactNode;
  /** Marks the section's content as mandatory (red asterisk). */
  required?: boolean;
  children: ReactNode;
}>;

export function RecipeForm({
  initial,
  Panel = AdminPanel,
  /** Where to go after a successful save. */
  redirectTo = (slug) => `/admin/recipes/${encodeURIComponent(slug)}/edit`,
  /** Authors delete from the recipe page; admins delete from here. */
  showDelete = true,
  cancelHref = "/admin/recipes",
}: {
  initial?: RecipeDetail;
  Panel?: FormPanel;
  redirectTo?: (slug: string) => string;
  showDelete?: boolean;
  cancelHref?: string;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const form = useFormSubmit();
  const confirm = useConfirm();
  const editing = initial !== undefined;

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const [title, setTitle] = useState(initial?.title ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [summary, setSummary] = useState(initial?.summary ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [difficulty, setDifficulty] = useState(initial?.difficulty ?? "easy");
  const [visibility, setVisibility] = useState(initial?.visibility ?? "public");
  // Empty string = "not specified": the fields are optional, submit maps
  // blank to 0/1 and read surfaces render "-" instead of a fake zero.
  const [prep, setPrep] = useState(
    initial?.prep_minutes ? String(initial.prep_minutes) : "",
  );
  const [cook, setCook] = useState(
    initial?.cook_minutes ? String(initial.cook_minutes) : "",
  );
  const [servings, setServings] = useState(
    initial?.servings && initial.servings !== 1 ? String(initial.servings) : "",
  );
  const [picked, setPicked] = useState<string[]>(
    initial?.categories.map((item) => item.slug) ?? [],
  );
  const [cover, setCover] = useState<File | null>(null);
  /** The file waiting to be framed. `null` closes the crop dialog. */
  const [cropping, setCropping] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [coverProblem, setCoverProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // When creation succeeds but the cover upload fails, the recipe already
  // exists. Remembering its slug turns the retry into an update instead of
  // a second POST  otherwise every retry leaves another orphan draft.
  const [createdSlug, setCreatedSlug] = useState<string | null>(null);

  /**
   * Reject what the server will reject, at pick time.
   *
   * The server's Pillow build has no HEIF plugin, so an iPhone photo comes
   * back as a generic "not an image" error after a round trip. Catching it
   * here says the useful thing immediately.
   */
  function chooseCover(file: File | undefined | null) {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (/\.(heic|heif)$/.test(name)) {
      setCoverProblem(
        "ไฟล์ .HEIC/.HEIF จาก iPhone ยังอัปโหลดไม่ได้  ให้แปลงเป็น JPG หรือ PNG ก่อน (ในแอปรูปภาพ: แชร์ → บันทึกเป็น JPEG)",
      );
      return;
    }
    if (!file.type.startsWith("image/")) {
      setCoverProblem(`ไฟล์นี้ไม่ใช่รูปภาพ (${file.type || "ไม่ทราบชนิดไฟล์"})`);
      return;
    }
    setCoverProblem(null);
    // Frame it before it is uploaded. Covers are shown at 4:3 on the
    // card and on the recipe page, so the author decides what the crop
    // keeps - not `object-fit` on whatever shape the file happened to
    // be. This is the fix at the source; the layout only has to honour
    // the same ratio.
    setCropping(file);
  }

  /** Take the framed result as the cover, replacing whatever was there. */
  function acceptCrop(blob: Blob) {
    const source = cropping;
    setCropping(null);
    if (!source) return;
    const name = `${source.name.replace(/\.[^.]+$/, "")}.jpg`;
    const framed = new File([blob], name, { type: "image/jpeg" });
    setCover(framed);
    setCoverPreview(URL.createObjectURL(framed));
    if (fileInput.current) fileInput.current.value = "";
  }

  const [ingredients, setIngredients] = useState<IngredientRow[]>(
    initial?.ingredients.length
      ? initial.ingredients.map((row) => ({
          name: row.name,
          quantity: row.quantity ?? "",
          unit: row.unit ?? "",
          note: row.note ?? "",
          group: row.group ?? "",
          is_optional: row.is_optional,
        }))
      : [{ ...EMPTY_INGREDIENT }],
  );
  const [steps, setSteps] = useState<StepRow[]>(
    initial?.steps.length
      ? initial.steps.map((row) => ({
          body: row.body,
          duration: row.duration_minutes === null ? "" : String(row.duration_minutes),
        }))
      : [{ body: "", duration: "" }],
  );

  function patchIngredient(index: number, patch: Partial<IngredientRow>) {
    setIngredients((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  }
  function patchStep(index: number, patch: Partial<StepRow>) {
    setSteps((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }
  function moveStep(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= steps.length) return;
    setSteps((rows) => {
      const next = [...rows];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function toggleCategory(value: string) {
    setPicked((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : current.length >= MAX_CATEGORIES
          ? current
          : [...current, value],
    );
  }

  const cleanIngredients = ingredients
    .filter((row) => row.name.trim() !== "")
    .map((row) => ({
      name: row.name.trim(),
      quantity: row.quantity.trim() === "" ? null : row.quantity.trim(),
      unit: row.unit,
      note: row.note.trim(),
      group: row.group.trim(),
      is_optional: row.is_optional,
    }));

  const cleanSteps = steps
    .filter((row) => row.body.trim() !== "")
    .map((row) => ({
      body: row.body.trim(),
      duration_minutes: row.duration.trim() === "" ? null : Number(row.duration),
    }));

  // Mirrors `assert_publishable`; the backend remains the authority.
  const readiness = [
    { ok: title.trim().length >= 3, label: "ชื่อสูตรอย่างน้อย 3 ตัวอักษร" },
    { ok: cleanIngredients.length > 0, label: "มีวัตถุดิบอย่างน้อย 1 รายการ" },
    { ok: cleanSteps.length > 0, label: "มีขั้นตอนอย่างน้อย 1 ขั้น" },
    { ok: picked.length > 0, label: "เลือกหมวดหมู่อย่างน้อย 1 หมวด" },
    {
      // A file the server refused does not count as a cover.
      ok:
        (cover !== null && !form.fieldErrors.cover_image?.length) ||
        Boolean(initial?.cover_image_url),
      label: "มีรูปหน้าปก",
    },
  ];

  const [gateError, setGateError] = useState<string | null>(null);

  async function save(event: React.FormEvent) {
    event.preventDefault();

    // The friendly pre-flight: name everything missing in one message
    // instead of letting the server report the first failure it meets.
    const missing: string[] = [];
    if (title.trim().length < 3) missing.push("ชื่อสูตร (อย่างน้อย 3 ตัวอักษร)");
    if (!description.trim()) missing.push("รายละเอียด");
    if (cleanIngredients.length === 0) missing.push("วัตถุดิบอย่างน้อย 1 รายการ");
    if (cleanSteps.length === 0) missing.push("ขั้นตอนอย่างน้อย 1 ขั้น");
    if (cover === null && !initial?.cover_image_url) missing.push("รูปหน้าปก");
    if (missing.length > 0) {
      setGateError(
        `อีกนิดเดียว! ยังขาด ${missing.join(" · ")} - เติมให้ครบแล้วกดบันทึกอีกครั้งนะ`,
      );
      return;
    }
    setGateError(null);

    const body: Record<string, unknown> = {
      title: title.trim(),
      summary: summary.trim(),
      description: description.trim(),
      difficulty,
      visibility,
      prep_minutes: Number(prep) || 0,
      cook_minutes: Number(cook) || 0,
      servings: Number(servings) || 1,
      category_slugs: picked,
      ingredients: cleanIngredients,
      steps: cleanSteps,
    };

    // `useFormSubmit` already renders the form-level and per-field errors,
    // so there is no extra toast here  a generic "save failed" beside a
    // precise inline message is noise, and reading `form.fieldErrors`
    // right after `submit()` would see the previous render's state anyway.
    await form.submit(async () => {
      let targetSlug: string;
      if (editing) {
        // Only send a slug when it actually changed: the backend rejects
        // a slug change on a published recipe for non-staff, and there is
        // no reason to risk that when nothing was edited.
        if (slug.trim() && slug.trim() !== initial.slug) body.slug = slug.trim();
        const updated = await api.patch<RecipeDetail>(`/recipes/${initial.slug}/`, {
          body,
        });
        targetSlug = updated.slug;
      } else if (createdSlug) {
        // A previous attempt already created the record; finish it.
        const updated = await api.patch<RecipeDetail>(`/recipes/${createdSlug}/`, {
          body,
        });
        targetSlug = updated.slug;
      } else {
        const created = await api.post<RecipeDetail>("/recipes/", { body });
        targetSlug = created.slug;
        setCreatedSlug(created.slug);
      }

      if (cover) {
        const payload = new FormData();
        payload.append("cover_image", cover);
        // Anything thrown here leaves `createdSlug` set, so the retry
        // updates this recipe rather than creating another one.
        await api.patch(`/recipes/${targetSlug}/`, { formData: payload });
      }

      toast(
        editing || createdSlug
          ? "บันทึกการแก้ไขแล้ว"
          : "สร้างสูตรใหม่เป็นฉบับร่างแล้ว",
        "success",
      );
      router.push(redirectTo(targetSlug) as "/admin/recipes");
      router.refresh();
    });
  }

  async function removeRecipe() {
    if (!initial) return;
    try {
      await api.delete(`/recipes/${initial.slug}/`);
      toast(`ลบสูตร “${initial.title}” แล้ว`, "success");
      router.push(cancelHref as "/admin/recipes");
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  return (
    <form onSubmit={save} className="space-y-4" noValidate>
      {form.formError ? (
        <p
          role="alert"
          className="rounded-md bg-danger-subtle px-3 py-2 text-sm text-danger"
        >
          {form.formError}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {/* ---- Basics ---- */}
          <Panel title="ข้อมูลหลัก">
            <div className="space-y-4 px-4 py-4">
              <Field label="ชื่อสูตร" required errors={form.fieldErrors.title}>
                {(control) => (
                  <Input
                    {...control}
                    value={title}
                    maxLength={160}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                )}
              </Field>

              {editing ? (
                <Field
                  label="slug"
                  errors={form.fieldErrors.slug}
                  hint={
                    initial.status === "published"
                      ? "สูตรนี้เผยแพร่แล้ว  ปกติ slug จะแก้ไม่ได้ แต่สิทธิ์ staff แก้ได้ (ลิงก์เดิมจะเสีย)"
                      : "ใช้เป็น URL ของสูตร"
                  }
                >
                  {(control) => (
                    <Input
                      {...control}
                      value={slug}
                      className="font-mono"
                      onChange={(event) => setSlug(event.target.value)}
                    />
                  )}
                </Field>
              ) : null}

              <Field label="สรุปสั้น ๆ" errors={form.fieldErrors.summary}>
                {(control) => (
                  <Textarea
                    {...control}
                    rows={2}
                    value={summary}
                    maxLength={300}
                    onChange={(event) => setSummary(event.target.value)}
                  />
                )}
              </Field>

              <Field label="รายละเอียด" required errors={form.fieldErrors.description}>
                {(control) => (
                  <Textarea
                    {...control}
                    rows={5}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                  />
                )}
              </Field>
            </div>
          </Panel>

          {/* ---- Ingredients ---- */}
          <Panel
            title="วัตถุดิบ"
            description={`${cleanIngredients.length}/${MAX_INGREDIENTS} รายการ  การบันทึกจะแทนที่รายการเดิมทั้งชุด`}
            actions={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={ingredients.length >= MAX_INGREDIENTS}
                onClick={() =>
                  setIngredients((rows) => [...rows, { ...EMPTY_INGREDIENT }])
                }
              >
                + เพิ่มวัตถุดิบ
              </Button>
            }
          >
            <div className="space-y-2 px-4 py-4">
              {form.fieldErrors.ingredients?.length ? (
                <p role="alert" className="text-sm text-danger">
                  {form.fieldErrors.ingredients.join(" ")}
                </p>
              ) : null}
              {ingredients.map((row, index) => (
                <div
                  key={index}
                  className="grid grid-cols-2 gap-2 rounded-md border border-edge p-2 sm:grid-cols-12"
                >
                  <input
                    aria-label={`ชื่อวัตถุดิบรายการที่ ${index + 1}`}
                    value={row.name}
                    placeholder="ชื่อวัตถุดิบ"
                    onChange={(event) =>
                      patchIngredient(index, { name: event.target.value })
                    }
                    className="col-span-2 h-9 rounded border border-edge-strong/50 bg-surface px-2 text-sm sm:col-span-4"
                  />
                  <input
                    aria-label={`ปริมาณรายการที่ ${index + 1}`}
                    value={row.quantity}
                    placeholder="ปริมาณ"
                    inputMode="decimal"
                    onChange={(event) =>
                      patchIngredient(index, { quantity: event.target.value })
                    }
                    className="h-9 rounded border border-edge-strong/50 bg-surface px-2 text-sm sm:col-span-2"
                  />
                  <select
                    aria-label={`หน่วยรายการที่ ${index + 1}`}
                    value={row.unit}
                    onChange={(event) =>
                      patchIngredient(index, { unit: event.target.value })
                    }
                    className="h-9 rounded border border-edge-strong/50 bg-surface px-2 text-sm sm:col-span-2"
                  >
                    {UNITS.map((unit) => (
                      <option key={unit.value} value={unit.value}>
                        {unit.label}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label={`กลุ่มของรายการที่ ${index + 1}`}
                    value={row.group}
                    placeholder="กลุ่ม เช่น ตัวแป้ง"
                    onChange={(event) =>
                      patchIngredient(index, { group: event.target.value })
                    }
                    className="h-9 rounded border border-edge-strong/50 bg-surface px-2 text-sm sm:col-span-2"
                  />
                  <div className="flex items-center justify-between gap-2 sm:col-span-2">
                    <label className="flex items-center gap-1 text-xs text-fg-muted">
                      <input
                        type="checkbox"
                        checked={row.is_optional}
                        onChange={(event) =>
                          patchIngredient(index, {
                            is_optional: event.target.checked,
                          })
                        }
                        className="size-4"
                      />
                      ไม่บังคับ
                    </label>
                    <button
                      type="button"
                      aria-label={`ลบวัตถุดิบรายการที่ ${index + 1}`}
                      onClick={() =>
                        setIngredients((rows) =>
                          rows.filter((_, i) => i !== index),
                        )
                      }
                      className="rounded px-2 text-sm text-danger hover:bg-danger-subtle"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {/* ---- Steps ---- */}
          <Panel
            required
            title="ขั้นตอน"
            description={`${cleanSteps.length}/${MAX_STEPS} ขั้น  ลำดับตามที่แสดงด้านล่าง`}
            actions={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={steps.length >= MAX_STEPS}
                onClick={() =>
                  setSteps((rows) => [...rows, { body: "", duration: "" }])
                }
              >
                + เพิ่มขั้นตอน
              </Button>
            }
          >
            <div className="space-y-2 px-4 py-4">
              {form.fieldErrors.steps?.length ? (
                <p role="alert" className="text-sm text-danger">
                  {form.fieldErrors.steps.join(" ")}
                </p>
              ) : null}
              {steps.map((row, index) => (
                <div
                  key={index}
                  className="flex gap-2 rounded-md border border-edge p-2"
                >
                  <span className="mt-2 w-6 shrink-0 text-center font-mono text-sm text-fg-subtle">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1 space-y-2">
                    <textarea
                      aria-label={`เนื้อหาขั้นตอนที่ ${index + 1}`}
                      value={row.body}
                      rows={2}
                      placeholder="อธิบายขั้นตอนนี้"
                      onChange={(event) =>
                        patchStep(index, { body: event.target.value })
                      }
                      className="w-full rounded border border-edge-strong/50 bg-surface px-2 py-1.5 text-sm"
                    />
                    <label className="flex items-center gap-2 text-xs text-fg-muted">
                      ใช้เวลา (นาที)
                      <input
                        value={row.duration}
                        inputMode="numeric"
                        onChange={(event) =>
                          patchStep(index, { duration: event.target.value })
                        }
                        className="h-8 w-20 rounded border border-edge-strong/50 bg-surface px-2 text-sm"
                      />
                    </label>
                  </div>
                  <div className="flex shrink-0 flex-col gap-1">
                    <button
                      type="button"
                      aria-label={`เลื่อนขั้นตอนที่ ${index + 1} ขึ้น`}
                      disabled={index === 0}
                      onClick={() => moveStep(index, -1)}
                      className="rounded px-2 text-sm text-fg-muted hover:bg-surface-sunken disabled:opacity-40"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      aria-label={`เลื่อนขั้นตอนที่ ${index + 1} ลง`}
                      disabled={index === steps.length - 1}
                      onClick={() => moveStep(index, 1)}
                      className="rounded px-2 text-sm text-fg-muted hover:bg-surface-sunken disabled:opacity-40"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      aria-label={`ลบขั้นตอนที่ ${index + 1}`}
                      onClick={() =>
                        setSteps((rows) => rows.filter((_, i) => i !== index))
                      }
                      className="rounded px-2 text-sm text-danger hover:bg-danger-subtle"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* ---- Sidebar ---- */}
        <div className="space-y-4">
          <Panel title="การเผยแพร่">
            <div className="space-y-3 px-4 py-4 text-sm">
              {editing ? (
                <p className="text-fg-muted">
                  สถานะปัจจุบัน:{" "}
                  <span className="font-medium text-fg">{initial.status}</span> 
                  เปลี่ยนสถานะได้จากหน้ารายการสูตร
                </p>
              ) : (
                <p className="text-fg-muted">
                  สูตรใหม่จะถูกสร้างเป็น <strong>ฉบับร่าง</strong> เสมอ
                  และผู้เขียนคือบัญชีที่กำลังใช้งานอยู่  เผยแพร่ได้ในขั้นถัดไป
                </p>
              )}
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
                  ความพร้อมก่อนเผยแพร่
                </p>
                <ul className="mt-1.5 space-y-1">
                  {readiness.map((item) => (
                    <li
                      key={item.label}
                      className={`flex items-start gap-2 text-xs ${
                        item.ok ? "text-fg-muted" : "text-warning"
                      }`}
                    >
                      <span aria-hidden>{item.ok ? "✓" : "○"}</span>
                      {item.label}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>

          <Panel title="รูปหน้าปก" required>
            <div className="space-y-2 px-4 py-4">
              {coverPreview || initial?.cover_image_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- admin preview from the API origin or a local blob
                <img
                  src={coverPreview ?? initial?.cover_image_url ?? ""}
                  alt=""
                  className="aspect-4/3 w-full rounded border border-edge object-cover"
                />
              ) : null}

              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  chooseCover(event.dataTransfer.files?.[0]);
                }}
                className={`rounded border border-dashed px-3 py-4 text-center ${
                  dragging ? "border-accent bg-accent-subtle" : "border-edge"
                }`}
              >
                <p className="text-xs text-fg-muted">
                  ลากรูปมาวางที่นี่ หรือ
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="mt-1.5"
                  onClick={() => fileInput.current?.click()}
                >
                  เลือกรูปจากเครื่อง
                </Button>
                <input
                  ref={fileInput}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  aria-label="เลือกรูปหน้าปก"
                  className="sr-only"
                  onChange={(event) => chooseCover(event.target.files?.[0])}
                />
                <p className="mt-1.5 text-[11px] text-fg-subtle">
                  รองรับ JPG · PNG · WebP · GIF (ไม่รองรับ .HEIC จาก iPhone) ·
                  เลือกรูปแล้วจะให้ครอบเป็นสัดส่วน 4:3 ก่อนอัปโหลด
                </p>
              </div>

              {cover ? (
                <p className="flex items-center justify-between gap-2 rounded bg-surface-sunken px-2 py-1.5 text-xs">
                  <span className="min-w-0 truncate text-fg">
                    {cover.name}{" "}
                    <span className="text-fg-subtle">
                      (
                      {cover.size < 1024
                        ? `${cover.size} B`
                        : `${Math.round(cover.size / 1024)} KB`}
                      )
                    </span>
                  </span>
                  <button
                    type="button"
                    aria-label="เอารูปที่เลือกออก"
                    onClick={() => {
                      setCover(null);
                      setCoverPreview(null);
                      if (fileInput.current) fileInput.current.value = "";
                    }}
                    className="shrink-0 rounded px-1 text-danger hover:bg-danger-subtle"
                  >
                    ✕
                  </button>
                </p>
              ) : null}

              {cover ? (
                <button
                  type="button"
                  onClick={() => setCropping(cover)}
                  className="text-xs text-accent underline focus-visible:outline-2 focus-visible:outline-focus"
                >
                  ปรับกรอบรูปใหม่
                </button>
              ) : null}

              {coverProblem ? (
                <p role="alert" className="text-xs text-danger">
                  {coverProblem}
                </p>
              ) : null}
              {form.fieldErrors.cover_image?.length ? (
                <p role="alert" className="text-xs text-danger">
                  {form.fieldErrors.cover_image.join(" ")}
                </p>
              ) : null}
              {createdSlug && !editing ? (
                <p className="rounded bg-warning-subtle px-2 py-1.5 text-xs text-warning">
                  สร้างสูตรไว้แล้ว  การกดบันทึกอีกครั้งจะอัปเดตสูตรเดิม
                  ไม่สร้างซ้ำ
                </p>
              ) : null}
            </div>
          </Panel>

          <Panel title="รายละเอียดการทำ">
            <div className="space-y-3 px-4 py-4">
              <Field label="ระดับความยาก" errors={form.fieldErrors.difficulty}>
                {(control) => (
                  <Select
                    {...control}
                    value={difficulty}
                    onChange={(event) => setDifficulty(event.target.value)}
                  >
                    {DIFFICULTIES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="การมองเห็น" errors={form.fieldErrors.visibility}>
                {(control) => (
                  <Select
                    {...control}
                    value={visibility}
                    onChange={(event) => setVisibility(event.target.value)}
                  >
                    {VISIBILITIES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <div className="grid grid-cols-3 gap-2">
                <Field label="เตรียม (น.)" errors={form.fieldErrors.prep_minutes}>
                  {(control) => (
                    <Input
                      {...control}
                      inputMode="numeric"
                      placeholder="-"
                      value={prep}
                      onChange={(event) => setPrep(event.target.value)}
                    />
                  )}
                </Field>
                <Field label="อบ/ปรุง (น.)" errors={form.fieldErrors.cook_minutes}>
                  {(control) => (
                    <Input
                      {...control}
                      inputMode="numeric"
                      placeholder="-"
                      value={cook}
                      onChange={(event) => setCook(event.target.value)}
                    />
                  )}
                </Field>
                <Field label="เสิร์ฟ" errors={form.fieldErrors.servings}>
                  {(control) => (
                    <Input
                      {...control}
                      inputMode="numeric"
                      placeholder="-"
                      value={servings}
                      onChange={(event) => setServings(event.target.value)}
                    />
                  )}
                </Field>
              </div>
            </div>
          </Panel>

          <Panel title={`หมวดหมู่ (${picked.length}/${MAX_CATEGORIES})`}>
            <div className="px-4 py-4">
              <div className="flex flex-wrap gap-1.5">
                {(categories.data ?? []).map((category) => {
                  const active = picked.includes(category.slug);
                  return (
                    <button
                      key={category.slug}
                      type="button"
                      aria-pressed={active}
                      onClick={() => toggleCategory(category.slug)}
                      className={`rounded-full border px-2.5 py-1 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${
                        active
                          ? "border-accent bg-accent-subtle text-fg"
                          : "border-edge bg-surface text-fg-muted hover:border-edge-strong"
                      }`}
                    >
                      {active ? "✓ " : ""}
                      {category.name}
                    </button>
                  );
                })}
              </div>
              {form.fieldErrors.category_slugs?.length ? (
                <p role="alert" className="mt-2 text-xs text-danger">
                  {form.fieldErrors.category_slugs.join(" ")}
                </p>
              ) : null}
            </div>
          </Panel>
        </div>
      </div>

      {gateError ? (
        <p
          role="alert"
          className="rounded-control bg-danger-subtle px-3.5 py-2.5 text-sm text-danger"
        >
          {gateError}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-edge pt-4">
        {editing && showDelete ? (
          <Button
            type="button"
            variant="danger"
            size="sm"
            className="mr-auto"
            onClick={() =>
              confirm.ask({
                title: "ลบสูตรนี้ถาวร?",
                body: `“${initial.title}” จะถูกลบออกจากฐานข้อมูลพร้อมไฟล์รูปทั้งหมด กู้คืนไม่ได้  ถ้าต้องการแค่ซ่อน ให้ใช้ “เก็บเข้าคลัง” จากหน้ารายการแทน`,
                confirmLabel: "ลบถาวร",
                danger: true,
                action: removeRecipe,
              })
            }
          >
            ลบสูตรนี้ถาวร
          </Button>
        ) : null}
        <Button
          type="button"
          variant="secondary"
          onClick={() => router.push(cancelHref as "/admin/recipes")}
        >
          ยกเลิก
        </Button>
        <Button type="submit" loading={form.submitting}>
          {editing ? "บันทึกการแก้ไข" : "สร้างเป็นฉบับร่าง"}
        </Button>
      </div>

      {confirm.dialog}

      <ImageCropper
        file={cropping}
        aspect={COVER_ASPECT}
        title="ปรับกรอบรูปหน้าปก"
        confirmLabel="ใช้รูปนี้"
        helpText="กรอบนี้คือสิ่งที่จะเห็นทั้งในการ์ดและหน้าสูตร รูปจะถูกบันทึกเป็น JPG"
        onCancel={() => setCropping(null)}
        onConfirm={acceptCrop}
        onUndecodable={() => {
          setCropping(null);
          setCoverProblem(
            "เปิดไฟล์นี้เป็นรูปภาพไม่ได้  อาจเสียหายหรือเป็นไฟล์คนละชนิดกับนามสกุล ลองไฟล์อื่นนะ",
          );
        }}
      />
    </form>
  );
}
