"use client";

/**
 * The one post composer, used inline on the feed and on `/community/create`.
 *
 * Two real endpoints, in order:
 *   1. `POST /gallery/` — caption, status and the optional `recipe_id`.
 *   2. `POST /gallery/{id}/images/` — one multipart request per photo,
 *      which is the only image shape the backend offers.
 *
 * Step 1 already created the post, so a failure in step 2 must not create
 * a second one on retry: the new id is kept and the retry uploads only
 * the photos that have not landed yet.
 */

import { useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type { GalleryPost, RecipeListItem } from "@/lib/api/models";
import { useFormSubmit } from "@/lib/forms/use-form";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth/auth-context";
import {
  ALLOWED_IMAGE_LABEL,
  MAX_IMAGES_PER_POST,
  describeImageProblem,
} from "@/lib/community";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { RecipeAttachmentCard } from "@/components/community/recipe-attachment-card";
import { RecipeSelectorDialog } from "@/components/community/recipe-selector";

export interface Attachment {
  id: number;
  slug: string;
  title: string;
}

interface PickedImage {
  file: File;
  preview: string;
  uploaded: boolean;
}

export function PostComposerForm({
  initialAttachment = null,
  onPublished,
  onCancel,
  autoFocus = false,
}: {
  initialAttachment?: Attachment | null;
  /** Receives the created post so the caller can prepend or navigate. */
  onPublished: (post: GalleryPost) => void;
  onCancel?: () => void;
  autoFocus?: boolean;
}) {
  const { user } = useAuth();
  const { toast } = useToast();
  const form = useFormSubmit();

  const [caption, setCaption] = useState("");
  const [images, setImages] = useState<PickedImage[]>([]);
  const [imageProblem, setImageProblem] = useState<string | null>(null);
  const [attachment, setAttachment] = useState<Attachment | null>(
    initialAttachment,
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const accepted: PickedImage[] = [];
    for (const file of Array.from(list)) {
      if (images.length + accepted.length >= MAX_IMAGES_PER_POST) {
        setImageProblem(`แนบรูปได้สูงสุด ${MAX_IMAGES_PER_POST} รูปต่อโพสต์`);
        break;
      }
      const problem = describeImageProblem(file);
      if (problem) {
        setImageProblem(problem);
        continue;
      }
      accepted.push({ file, preview: URL.createObjectURL(file), uploaded: false });
    }
    if (accepted.length) {
      setImageProblem(null);
      setImages((current) => [...current, ...accepted]);
    }
    if (fileInput.current) fileInput.current.value = "";
  }

  const canPublish = caption.trim().length > 0 || images.length > 0;
  const displayName = user?.display_name || user?.username || "คุณ";

  async function publish(event: React.FormEvent) {
    event.preventDefault();
    if (!canPublish) return;

    await form.submit(async () => {
      let postId = createdId;
      if (postId === null) {
        const created = await api.post<GalleryPost>("/gallery/", {
          body: {
            caption: caption.trim(),
            status: "published",
            ...(attachment ? { recipe_id: attachment.id } : {}),
          },
        });
        postId = created.id;
        setCreatedId(created.id);
      }

      for (const [index, image] of images.entries()) {
        if (image.uploaded) continue;
        const payload = new FormData();
        payload.append("image", image.file);
        await api.post(`/gallery/${postId}/images/`, { formData: payload });
        setImages((current) =>
          current.map((item, i) =>
            i === index ? { ...item, uploaded: true } : item,
          ),
        );
      }

      // Re-read so the caller renders exactly what the server stored,
      // images and all, instead of a locally assembled guess.
      const saved = await api.get<GalleryPost>(`/gallery/${postId}/`);
      toast("เผยแพร่โพสต์แล้ว 🎉", "success");
      setCaption("");
      setImages([]);
      setAttachment(null);
      setCreatedId(null);
      onPublished(saved);
    });
  }

  return (
    <form onSubmit={publish} noValidate className="space-y-4">
      {form.formError ? (
        <p
          role="alert"
          className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
        >
          {form.formError}
        </p>
      ) : null}

      <div className="flex items-start gap-3">
        <Avatar src={user?.avatar_url} name={displayName} />
        <div className="min-w-0 flex-1">
          <label htmlFor="post-caption" className="sr-only">
            เนื้อหาโพสต์
          </label>
          <textarea
            id="post-caption"
            autoFocus={autoFocus}
            value={caption}
            onChange={(event) => setCaption(event.target.value)}
            rows={4}
            maxLength={500}
            placeholder="วันนี้ลองทำอะไรมา เล่าให้ฟังหน่อย…"
            aria-describedby="caption-count"
            className="block w-full resize-y rounded-control border border-edge-strong/50 bg-surface px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
          />
          <p id="caption-count" className="mt-1 text-right text-xs text-fg-subtle">
            {caption.length}/500
          </p>
          {form.fieldErrors.caption?.length ? (
            <p role="alert" className="text-sm text-danger">
              {form.fieldErrors.caption.join(" ")}
            </p>
          ) : null}
        </div>
      </div>

      {/* ---- Attachments toolbar ---- */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => fileInput.current?.click()}
          disabled={images.length >= MAX_IMAGES_PER_POST}
        >
          📷 รูปภาพ
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setPickerOpen(true)}
        >
          🍰 แนบสูตร
        </Button>
        <span className="text-xs text-fg-subtle">
          {images.length}/{MAX_IMAGES_PER_POST} · {ALLOWED_IMAGE_LABEL}
        </span>
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          aria-label="เลือกรูปภาพ"
          className="sr-only"
          onChange={(event) => addFiles(event.target.files)}
        />
      </div>

      {imageProblem ? (
        <p role="alert" className="text-sm text-danger">
          {imageProblem}
        </p>
      ) : null}
      {form.fieldErrors.image?.length ? (
        <p role="alert" className="text-sm text-danger">
          {form.fieldErrors.image.join(" ")}
        </p>
      ) : null}

      {images.length > 0 ? (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {images.map((image, index) => (
            <li key={image.preview} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
              <img
                src={image.preview}
                alt=""
                className="aspect-square w-full rounded-control border border-edge object-cover"
              />
              {image.uploaded ? (
                <span className="absolute bottom-1 left-1 rounded bg-success-subtle px-1 text-[10px] text-success">
                  อัปโหลดแล้ว
                </span>
              ) : null}
              <button
                type="button"
                aria-label={`เอารูปที่ ${index + 1} ออก`}
                onClick={() =>
                  setImages((current) => current.filter((_, i) => i !== index))
                }
                className="absolute right-1 top-1 flex size-6 items-center justify-center rounded-full bg-black/55 text-xs text-white hover:bg-black/75 focus-visible:outline-2 focus-visible:outline-white"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {attachment ? (
        <div className="space-y-2">
          <RecipeAttachmentCard recipe={attachment} />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setPickerOpen(true)}
            >
              เปลี่ยนสูตร
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setAttachment(null)}
            >
              เอาสูตรออก
            </Button>
          </div>
        </div>
      ) : null}
      {form.fieldErrors.recipe_id?.length ? (
        <p role="alert" className="text-sm text-danger">
          {form.fieldErrors.recipe_id.join(" ")}
        </p>
      ) : null}

      {createdId !== null ? (
        <p className="rounded-control bg-warning-subtle px-3 py-2 text-xs text-warning">
          โพสต์ถูกสร้างแล้ว — การกดเผยแพร่อีกครั้งจะอัปโหลดเฉพาะรูปที่ยังไม่ขึ้น
          ไม่สร้างโพสต์ซ้ำ
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-3 border-t border-edge pt-3">
        <p className="text-xs text-fg-subtle">โพสต์จะแสดงต่อสาธารณะในหน้าชุมชน</p>
        <div className="flex gap-2">
          {onCancel ? (
            <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
              ยกเลิก
            </Button>
          ) : null}
          <Button type="submit" loading={form.submitting} disabled={!canPublish}>
            เผยแพร่โพสต์
          </Button>
        </div>
      </div>

      <RecipeSelectorDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(recipe: RecipeListItem) =>
          setAttachment({
            id: recipe.id,
            slug: recipe.slug,
            title: recipe.title,
          })
        }
      />
    </form>
  );
}
