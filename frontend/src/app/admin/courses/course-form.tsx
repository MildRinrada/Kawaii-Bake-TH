"use client";

/**
 * Create / edit a course from the back office.
 *
 * Mirrors the recipe form's write contract: the JSON body first (create
 * or PATCH), then the thumbnail as its own multipart PATCH - DRF cannot
 * parse a repeated-key list field beside a file in one multipart body.
 * When creation succeeds but the thumbnail upload fails, `createdSlug`
 * keeps the retry pointed at the same course instead of minting drafts.
 *
 * The thumbnail is **required at this form's gate** (a course card
 * without art renders as a placeholder and looks broken); the backend
 * treats it as optional, so the rule lives here with a friendly,
 * everything-at-once error message.
 */

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api/client";
import type { Category, CourseDetail } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useFormSubmit } from "@/lib/forms/use-form";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { AdminPanel } from "@/components/admin/primitives";
import { describeImageProblem } from "@/lib/community";
import { ImageCropper } from "@/components/ui/image-cropper";
import { COVER_ASPECT } from "@/components/content/cover-frame";

const DIFFICULTIES = [
  { value: "beginner", label: "เริ่มต้น" },
  { value: "intermediate", label: "ปานกลาง" },
  { value: "advanced", label: "ขั้นสูง" },
];

const VISIBILITIES = [
  { value: "public", label: "สาธารณะ" },
  { value: "unlisted", label: "เฉพาะผู้มีลิงก์ (unlisted)" },
  { value: "private", label: "ส่วนตัว" },
];

const MAX_CATEGORIES = 3;

export function CourseForm({ initial }: { initial?: CourseDetail }) {
  const router = useRouter();
  const { toast } = useToast();
  const form = useFormSubmit();
  const editing = Boolean(initial);

  const [title, setTitle] = useState(initial?.title ?? "");
  const [summary, setSummary] = useState(initial?.summary ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [difficulty, setDifficulty] = useState(initial?.difficulty ?? "beginner");
  const [visibility, setVisibility] = useState(initial?.visibility ?? "public");
  const [picked, setPicked] = useState<string[]>(
    initial?.categories.map((item) => item.slug) ?? [],
  );

  const [thumbnail, setThumbnail] = useState<File | null>(null);
  /** The file waiting to be framed. `null` closes the crop dialog. */
  const [cropping, setCropping] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [thumbnailProblem, setThumbnailProblem] = useState<string | null>(null);
  const [gateError, setGateError] = useState<string | null>(null);
  const [createdSlug, setCreatedSlug] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  function chooseThumbnail(file: File | undefined) {
    if (!file) return;
    const problem = describeImageProblem(file);
    setThumbnailProblem(problem);
    if (problem) return;
    // Framed before upload, at the same 4:3 the course card draws, so the
    // author decides what a crop keeps (see `CoverFrame`).
    setCropping(file);
  }

  /** Take the framed result as the thumbnail. */
  function acceptCrop(blob: Blob) {
    const source = cropping;
    setCropping(null);
    if (!source) return;
    const framed = new File([blob], `${source.name.replace(/\.[^.]+$/, "")}.jpg`, {
      type: "image/jpeg",
    });
    setThumbnail(framed);
    setPreview(URL.createObjectURL(framed));
    if (fileInput.current) fileInput.current.value = "";
  }

  function toggleCategory(slug: string) {
    setPicked((current) =>
      current.includes(slug)
        ? current.filter((item) => item !== slug)
        : current.length < MAX_CATEGORIES
          ? [...current, slug]
          : current,
    );
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();

    const missing: string[] = [];
    if (title.trim().length < 3) missing.push("ชื่อคอร์ส (อย่างน้อย 3 ตัวอักษร)");
    if (!description.trim()) missing.push("รายละเอียดคอร์ส");
    if (thumbnail === null && !initial?.thumbnail_url) missing.push("รูปหน้าปกคอร์ส");
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
      category_slugs: picked,
    };

    await form.submit(async () => {
      let targetSlug: string;
      if (editing) {
        const updated = await api.patch<CourseDetail>(
          `/courses/${initial!.slug}/`,
          { body },
        );
        targetSlug = updated.slug;
      } else if (createdSlug) {
        const updated = await api.patch<CourseDetail>(`/courses/${createdSlug}/`, {
          body,
        });
        targetSlug = updated.slug;
      } else {
        const created = await api.post<CourseDetail>("/courses/", { body });
        targetSlug = created.slug;
        setCreatedSlug(created.slug);
      }

      if (thumbnail) {
        const payload = new FormData();
        payload.append("thumbnail", thumbnail);
        await api.patch(`/courses/${targetSlug}/`, { formData: payload });
      }

      toast(
        editing || createdSlug
          ? "บันทึกคอร์สแล้ว"
          : "สร้างคอร์สใหม่เป็นฉบับร่างแล้ว - เพิ่มบทเรียนแล้วค่อยเผยแพร่",
        "success",
      );
      router.push("/admin/courses");
      router.refresh();
    });
  }

  return (
    <form onSubmit={save} noValidate className="space-y-4">
      {form.formError ? (
        <p
          role="alert"
          className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
        >
          {form.formError}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr] lg:items-start">
        <div className="space-y-4">
          <AdminPanel title="ข้อมูลคอร์ส">
            <div className="space-y-4 px-4 py-4">
              <Field label="ชื่อคอร์ส" required errors={form.fieldErrors.title}>
                {(control) => (
                  <Input
                    {...control}
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                )}
              </Field>
              <Field
                label="สรุปสั้น ๆ"
                hint="หนึ่งประโยคบนการ์ดคอร์ส"
                errors={form.fieldErrors.summary}
              >
                {(control) => (
                  <Input
                    {...control}
                    value={summary}
                    onChange={(event) => setSummary(event.target.value)}
                  />
                )}
              </Field>
              <Field
                label="รายละเอียดคอร์ส"
                required
                errors={form.fieldErrors.description}
              >
                {(control) => (
                  <Textarea
                    {...control}
                    rows={6}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                  />
                )}
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="ระดับ" errors={form.fieldErrors.difficulty}>
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
              </div>
            </div>
          </AdminPanel>

          <AdminPanel title={`หมวดหมู่ (${picked.length}/${MAX_CATEGORIES})`}>
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
          </AdminPanel>
        </div>

        <AdminPanel title="รูปหน้าปกคอร์ส" required>
          <div className="space-y-2 px-4 py-4">
            {preview || initial?.thumbnail_url ? (
              // eslint-disable-next-line @next/next/no-img-element -- admin preview from the API origin or a local blob
              <img
                src={preview ?? initial?.thumbnail_url ?? ""}
                alt=""
                className="aspect-4/3 w-full rounded border border-edge object-cover"
              />
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => fileInput.current?.click()}
            >
              เลือกรูปจากเครื่อง
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              aria-label="เลือกรูปหน้าปกคอร์ส"
              className="sr-only"
              onChange={(event) => chooseThumbnail(event.target.files?.[0])}
            />
            {thumbnail ? (
              <button
                type="button"
                onClick={() => setCropping(thumbnail)}
                className="text-xs text-accent underline focus-visible:outline-2 focus-visible:outline-focus"
              >
                ปรับกรอบรูปใหม่
              </button>
            ) : null}
            <p className="text-[11px] text-fg-subtle">
              รองรับ JPG · PNG · WebP · ครอบเป็นสัดส่วน 4:3 ก่อนอัปโหลด - การ์ดคอร์สที่ไม่มีรูปจะดูเหมือนระบบพัง
              จึงบังคับให้ใส่ก่อนบันทึก
            </p>
            {thumbnailProblem ? (
              <p role="alert" className="text-xs text-danger">
                {thumbnailProblem}
              </p>
            ) : null}
            {form.fieldErrors.thumbnail?.length ? (
              <p role="alert" className="text-xs text-danger">
                {form.fieldErrors.thumbnail.join(" ")}
              </p>
            ) : null}
          </div>
        </AdminPanel>
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
        <Button
          type="button"
          variant="secondary"
          onClick={() => router.push("/admin/courses")}
        >
          ยกเลิก
        </Button>
        <Button type="submit" loading={form.submitting}>
          {editing ? "บันทึกการแก้ไข" : "สร้างเป็นฉบับร่าง"}
        </Button>
      </div>

      <ImageCropper
        file={cropping}
        aspect={COVER_ASPECT}
        title="ปรับกรอบรูปหน้าปกคอร์ส"
        confirmLabel="ใช้รูปนี้"
        helpText="กรอบนี้คือสิ่งที่จะเห็นทั้งในการ์ดและหน้าคอร์ส รูปจะถูกบันทึกเป็น JPG"
        onCancel={() => setCropping(null)}
        onConfirm={acceptCrop}
        onUndecodable={() => {
          setCropping(null);
          setThumbnailProblem(
            "เปิดไฟล์นี้เป็นรูปภาพไม่ได้  อาจเสียหายหรือเป็นไฟล์คนละชนิดกับนามสกุล ลองไฟล์อื่นนะ",
          );
        }}
      />
    </form>
  );
}
