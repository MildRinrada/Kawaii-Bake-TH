"use client";

/* eslint-disable @next/next/no-img-element -- a user-uploaded banner from
   the media origin; next/image would need that host allow-listed and buys
   nothing for a single above-the-fold image */

/**
 * The profile banner and the way its owner changes it.
 *
 * The whole surface is one control: hovering (or focusing) it reveals a
 * camera affordance, choosing a file opens the crop dialog, and only the
 * cropped result is uploaded. The backend stores exactly what was
 * framed — there is no original to re-crop from and no server-side image
 * pipeline, which is why the crop happens before the request rather than
 * after it.
 *
 * `COVER_ASPECT` is the single source of truth for the shape: the crop
 * dialog and the banner below both read it, so the picture the owner
 * framed is the picture that renders. It is deliberately wide — this is
 * a letterbox strip behind an avatar, not a photo.
 */

import { useRef, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ImageCropper } from "@/components/ui/image-cropper";
import { useToast } from "@/components/ui/toast";

/** Width ÷ height of the banner, shared by the crop dialog and the render. */
export const COVER_ASPECT = 6;

/** What the file picker will accept, matching the server's allow-list. */
const ACCEPT = "image/jpeg,image/png,image/webp";

export function CoverEditor({
  coverUrl,
  onChanged,
}: {
  coverUrl: string | null;
  /** Called after a successful upload or removal, to refetch the profile. */
  onChanged: () => void;
}) {
  const { toast } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(blob: Blob) {
    setBusy(true);
    try {
      const payload = new FormData();
      // A filename is required for the server to read an extension; the
      // cropper always produces JPEG.
      payload.append("cover", blob, "cover.jpg");
      await api.patch("/users/profile/update/", { formData: payload });
      toast("เปลี่ยนภาพหน้าปกแล้ว", "success");
      setPicked(null);
      onChanged();
    } catch (error) {
      toast(
        error instanceof ApiError ? error.message : "อัปโหลดภาพไม่สำเร็จ",
        "danger",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.patch("/users/profile/update/", { body: { cover: null } });
      toast("นำภาพหน้าปกออกแล้ว", "success");
      onChanged();
    } catch (error) {
      toast(
        error instanceof ApiError ? error.message : "นำภาพออกไม่สำเร็จ",
        "danger",
      );
    } finally {
      setBusy(false);
    }
  }

  function choose(file: File | undefined) {
    if (file) setPicked(file);
    // Clear the input so re-picking the *same* file still fires `change`.
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <>
      <div className="group relative">
        {/* `min-h` is the mobile floor: at a phone's width a true 6:1 strip
            would be ~55px, so the box stops shrinking and `object-cover`
            trims the sides instead — the normal way a banner degrades.
            `max-h` is the other end: on a wide screen a true 6:1 strip grows
            past 200px and starts crowding the avatar that sits over it. */}
        {coverUrl ? (
          <img
            src={coverUrl}
            alt=""
            aria-hidden
            style={{ aspectRatio: String(COVER_ASPECT) }}
            className="max-h-44 min-h-28 w-full object-cover"
          />
        ) : (
          <div
            aria-hidden
            style={{ aspectRatio: String(COVER_ASPECT) }}
            className="kb-hero max-h-44 min-h-28 w-full"
          />
        )}

        {/* The scrim only exists while the control is engaged, so the
            banner is never dimmed for someone just reading the page. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-black/0 transition-colors duration-200 group-hover:bg-black/30 group-focus-within:bg-black/30"
        />

        {/* Top-right, out of the way of the avatar and name that overlap the
            banner's bottom edge. Hidden until the banner is hovered or
            something inside it takes keyboard focus. */}
        <div className="absolute right-3 top-3 flex items-center gap-2 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100">
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            onClick={() => fileInput.current?.click()}
          >
            <Icon name="ui/camera" className="size-4" />
            {coverUrl ? "เปลี่ยนภาพหน้าปก" : "เพิ่มภาพหน้าปก"}
          </Button>
          {coverUrl ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={remove}
              aria-label="นำภาพหน้าปกออก"
            >
              <Icon name="ui/trash" className="size-4" />
            </Button>
          ) : null}
        </div>

        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          aria-label="เลือกภาพหน้าปก"
          onChange={(event) => choose(event.target.files?.[0])}
        />
      </div>

      <ImageCropper
        file={picked}
        aspect={COVER_ASPECT}
        title="ปรับภาพหน้าปก"
        confirmLabel="ใช้ภาพนี้"
        busy={busy}
        onCancel={() => setPicked(null)}
        onConfirm={(blob) => void upload(blob)}
      />
    </>
  );
}
