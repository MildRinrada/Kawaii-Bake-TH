"use client";

/**
 * The category editor, shared by create and edit.
 *
 * One slide-over serves both modes because the fields are identical; the
 * page keys this by category id so switching rows resets the state.
 *
 * The write contract has one quirk worth mirroring exactly: `image` is a
 * file field, so a save that carries a new photo goes out as multipart
 * while a photo-less save stays JSON. A PATCH sends only the fields that
 * actually changed  the backend treats absence as "keep"  and removing
 * the photo is the JSON-only `image: null`, which multipart cannot say.
 */

import { useId, useRef, useState, type FormEvent } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AdminCategory } from "@/lib/api/models";
import { translateFieldErrors } from "@/lib/forms/friendly-errors";
import { categoryArt, categoryIcon } from "@/lib/assets";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { DetailPanel, useConfirm } from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

/**
 * The slugs `categoryIcon` has real artwork for (the keys of its map in
 * `src/lib/assets.ts`, backed by files in `public/icons/category/`). Any
 * other `icon` value is a free-form string  usually an emoji  and is
 * rendered as text.
 */
export const CATEGORY_ICON_KEYS = [
  "bread",
  "cake",
  "cookies",
  "pastry",
  "pie",
  "macaron",
  "chocolate",
] as const;

const ICON_KEY_SET = new Set<string>(CATEGORY_ICON_KEYS);

export function isKnownIconKey(icon: string): boolean {
  return ICON_KEY_SET.has(icon);
}

/** What the file picker accepts, matching the server's allow-list. */
const ACCEPT = "image/jpeg,image/png,image/webp";

/** Scalar writes the endpoint accepts  the multipart/JSON payload shape. */
type CategoryWrite = Record<string, string | number | boolean>;

function buildFormData(fields: CategoryWrite): FormData {
  const payload = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    // DRF's BooleanField parses the literal strings "true"/"false".
    payload.append(key, String(value));
  }
  return payload;
}

export function CategoryForm({
  open,
  initial,
  onClose,
  onSaved,
}: {
  open: boolean;
  /** `null` = create mode. */
  initial: AdminCategory | null;
  onClose: () => void;
  /** Called after any successful write, to refetch the list. */
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const formId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const editing = initial !== null;

  const [name, setName] = useState(initial?.name ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [icon, setIcon] = useState(initial?.icon ?? "");
  const [order, setOrder] = useState(
    initial ? String(initial.display_order) : "",
  );
  const [active, setActive] = useState(initial?.is_active ?? true);
  // The stored photo can be removed independently of a save, so it lives
  // in state rather than being read off `initial` every render.
  const [imageUrl, setImageUrl] = useState(initial?.image_url ?? null);
  const [picked, setPicked] = useState<File | null>(null);
  const [pickedPreview, setPickedPreview] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  function choosePhoto(file: File | undefined | null) {
    if (!file) return;
    setPicked(file);
    setPickedPreview(URL.createObjectURL(file));
    // Clear the input so re-picking the *same* file still fires `change`.
    if (fileInput.current) fileInput.current.value = "";
  }

  /**
   * The fields to send. Create sends everything the admin provided; edit
   * diffs against `initial` so a PATCH cannot clobber a field that was
   * never touched (and an all-unchanged save becomes a no-op).
   */
  function changedFields(): CategoryWrite {
    const out: CategoryWrite = {};
    const trimmedName = name.trim();
    const trimmedSlug = slug.trim();
    const trimmedDescription = description.trim();
    const trimmedIcon = icon.trim();
    const orderNumber = Number(order) || 0;

    if (!initial) {
      out.name = trimmedName;
      // Blank slug is a real choice here: the backend derives a Thai-safe
      // slug from the name when the key is absent.
      if (trimmedSlug) out.slug = trimmedSlug;
      if (trimmedDescription) out.description = trimmedDescription;
      if (trimmedIcon) out.icon = trimmedIcon;
      if (order.trim()) out.display_order = orderNumber;
      out.is_active = active;
      return out;
    }

    if (trimmedName !== initial.name) out.name = trimmedName;
    // On edit a blank slug means "keep"  sending "" would wipe the URL.
    if (trimmedSlug && trimmedSlug !== initial.slug) out.slug = trimmedSlug;
    if (trimmedDescription !== initial.description)
      out.description = trimmedDescription;
    if (trimmedIcon !== initial.icon) out.icon = trimmedIcon;
    if (orderNumber !== initial.display_order) out.display_order = orderNumber;
    if (active !== initial.is_active) out.is_active = active;
    return out;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setFieldErrors({ name: ["กรุณากรอกชื่อหมวด"] });
      return;
    }

    setBusy(true);
    setFieldErrors({});
    try {
      const fields = changedFields();
      if (editing) {
        if (picked) {
          // A new photo forces multipart; the changed scalars ride along.
          const payload = buildFormData(fields);
          payload.append("image", picked);
          await api.patch<AdminCategory>(
            `/admin/recipe-categories/${initial.id}/`,
            { formData: payload },
          );
        } else if (Object.keys(fields).length === 0) {
          toast("ไม่มีการเปลี่ยนแปลงให้บันทึก", "neutral");
          onClose();
          return;
        } else {
          await api.patch<AdminCategory>(
            `/admin/recipe-categories/${initial.id}/`,
            { body: fields },
          );
        }
        toast(`บันทึกหมวด “${name.trim()}” แล้ว`, "success");
      } else {
        const payload = buildFormData(fields);
        if (picked) payload.append("image", picked);
        await api.post<AdminCategory>("/admin/recipe-categories/", {
          formData: payload,
        });
        toast(`สร้างหมวด “${name.trim()}” แล้ว`, "success");
      }
      onSaved();
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.code === "duplicate_category_slug") {
        // The one conflict this endpoint raises  worth a friendlier line
        // than the generic 409 text.
        toast(
          "slug นี้ชนกับหมวดที่มีอยู่แล้ว  เปลี่ยนชื่อ หรือกำหนด slug เองให้ไม่ซ้ำ",
          "danger",
        );
        setFieldErrors({ slug: ["slug นี้ถูกใช้แล้ว"] });
      } else if (error instanceof ApiError && Object.keys(error.details).length) {
        setFieldErrors(translateFieldErrors(error.fieldErrors()));
      } else {
        toast(describeAdminError(error), "danger");
      }
    } finally {
      setBusy(false);
    }
  }

  /** JSON `image: null` is the remove contract  multipart cannot carry it. */
  async function removePhoto() {
    if (!initial) return;
    setBusy(true);
    try {
      await api.patch<AdminCategory>(`/admin/recipe-categories/${initial.id}/`, {
        body: { image: null },
      });
      setImageUrl(null);
      toast("ลบภาพประจำหมวดแล้ว", "success");
      onSaved();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  function askDelete() {
    if (!initial) return;
    confirm.ask({
      title: `ลบหมวด “${initial.name}”?`,
      body: `สูตรที่อยู่ในหมวดนี้จะไม่ถูกลบ เพียงแต่หลุดจากหมวด (มี ${initial.recipe_count} สูตร)`,
      confirmLabel: "ลบหมวดหมู่",
      danger: true,
      action: async () => {
        try {
          await api.delete(`/admin/recipe-categories/${initial.id}/`);
          toast(`ลบหมวด “${initial.name}” แล้ว`, "success");
          onSaved();
          onClose();
        } catch (error) {
          toast(describeAdminError(error), "danger");
        }
      },
    });
  }

  // What the tile will actually show: the picked file wins, then the
  // stored photo, then the built-in art keyed by slug.
  const preview = pickedPreview ?? imageUrl;
  const usingBuiltIn = preview === null;

  return (
    <>
      <DetailPanel
        open={open}
        title={editing ? `แก้ไขหมวด: ${initial.name}` : "เพิ่มหมวดหมู่"}
        onClose={onClose}
        footer={
          <>
            {editing ? (
              <Button
                size="sm"
                variant="danger"
                className="mr-auto"
                disabled={busy}
                onClick={askDelete}
              >
                ลบหมวดหมู่
              </Button>
            ) : null}
            <Button size="sm" variant="secondary" disabled={busy} onClick={onClose}>
              ยกเลิก
            </Button>
            {/* Lives outside the <form>, so `form=` carries the submit. */}
            <Button size="sm" type="submit" form={formId} loading={busy}>
              {editing ? "บันทึกการแก้ไข" : "สร้างหมวดหมู่"}
            </Button>
          </>
        }
      >
        <form id={formId} onSubmit={save} className="space-y-4" noValidate>
          <Field label="ชื่อหมวด" required errors={fieldErrors.name}>
            {(control) => (
              <Input
                {...control}
                value={name}
                maxLength={100}
                onChange={(event) => setName(event.target.value)}
              />
            )}
          </Field>

          <Field
            label="slug"
            errors={fieldErrors.slug}
            hint={
              editing
                ? "ใช้เป็น URL ของหมวด  เว้นว่างเพื่อคงค่าเดิม (แก้แล้วลิงก์เดิมจะเสีย)"
                : "เว้นว่างเพื่อสร้างจากชื่ออัตโนมัติ"
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

          <Field label="คำอธิบาย" errors={fieldErrors.description}>
            {(control) => (
              <Textarea
                {...control}
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            )}
          </Field>

          {/* ---- Icon picker: known artwork keys + free text ---- */}
          <Field
            label="ไอคอน"
            errors={fieldErrors.icon}
            hint="เลือกจากชุดไอคอนของระบบ หรือพิมพ์อีโมจิ/คีย์เองในช่องด้านล่าง"
          >
            {(control) => (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  {CATEGORY_ICON_KEYS.map((key) => {
                    const selected = icon.trim() === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        title={key}
                        aria-label={`ไอคอน ${key}`}
                        aria-pressed={selected}
                        onClick={() => setIcon(key)}
                        className={`flex size-11 items-center justify-center rounded-md border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${
                          selected
                            ? "border-accent bg-accent-subtle"
                            : "border-edge bg-surface hover:border-edge-strong"
                        }`}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin */}
                        <img src={categoryIcon(key)} alt="" className="size-7" />
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    {...control}
                    value={icon}
                    placeholder="เช่น 🍰 หรือ cake"
                    onChange={(event) => setIcon(event.target.value)}
                  />
                  {/* Live readout of what the list will render for this value. */}
                  {icon.trim() ? (
                    isKnownIconKey(icon.trim()) ? (
                      // eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin
                      <img
                        src={categoryIcon(icon.trim())}
                        alt=""
                        className="size-7 shrink-0"
                      />
                    ) : (
                      <span aria-hidden className="shrink-0 text-xl">
                        {icon.trim()}
                      </span>
                    )
                  ) : null}
                </div>
              </div>
            )}
          </Field>

          <Field
            label="ลำดับการแสดง"
            errors={fieldErrors.display_order}
            hint="เลขน้อยขึ้นก่อน"
          >
            {(control) => (
              <Input
                {...control}
                inputMode="numeric"
                placeholder="0"
                value={order}
                className="max-w-32"
                onChange={(event) => setOrder(event.target.value)}
              />
            )}
          </Field>

          <Switch
            checked={active}
            onChange={setActive}
            label="เปิดใช้งานหมวดนี้"
            description="หมวดที่ปิดไว้จะไม่ปรากฏบนหน้าเว็บสาธารณะ แต่ข้อมูลยังอยู่ครบ"
            disabled={busy}
          />

          {/* ---- Tile photo ---- */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-fg">ภาพประจำหมวด</p>
            {/* eslint-disable-next-line @next/next/no-img-element -- admin thumbnail from the API origin */}
            <img
              src={preview ?? categoryArt(initial?.slug ?? "")}
              alt=""
              title={usingBuiltIn ? "ใช้ภาพมาตรฐาน" : undefined}
              className={`aspect-video w-full rounded-md border border-edge object-cover ${
                usingBuiltIn ? "opacity-60" : ""
              }`}
            />
            {usingBuiltIn ? (
              <p className="text-xs text-fg-subtle">
                ยังไม่มีภาพอัปโหลด  ระบบใช้ภาพมาตรฐานตาม slug ไปก่อน
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => fileInput.current?.click()}
              >
                {preview ? "เปลี่ยนภาพ" : "เลือกภาพ"}
              </Button>
              {picked ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => {
                    setPicked(null);
                    setPickedPreview(null);
                  }}
                >
                  เอาภาพที่เลือกออก
                </Button>
              ) : imageUrl && editing ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={busy}
                  onClick={removePhoto}
                >
                  ลบภาพ
                </Button>
              ) : null}
            </div>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              aria-label="เลือกภาพประจำหมวด"
              onChange={(event) => choosePhoto(event.target.files?.[0])}
            />
            {fieldErrors.image?.length ? (
              <p role="alert" className="text-sm text-danger">
                {fieldErrors.image.join(" ")}
              </p>
            ) : null}
          </div>
        </form>
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}
