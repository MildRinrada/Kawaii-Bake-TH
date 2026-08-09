"use client";

/* eslint-disable @next/next/no-img-element -- gallery media comes from the
   Django origin at arbitrary sizes; next/image would need remote-pattern
   config per deploy and buys little for local dev media */

/**
 * Post image gallery.
 *
 * One image fills the card; several become a tidy grid where the first
 * photo leads. Tapping any photo opens a lightbox — a native `<dialog>`,
 * so Escape, focus trapping and the top layer come from the platform.
 */

import { useEffect, useRef, useState } from "react";

import type { Schemas } from "@/lib/api/models";

type GalleryImage = Schemas["GalleryImage"];

export function CommunityImageGallery({
  images,
  alt = "",
}: {
  images: readonly GalleryImage[];
  alt?: string;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open !== null && !element.open) element.showModal();
    if (open === null && element.open) element.close();
  }, [open]);

  if (images.length === 0) return null;

  const caption = alt.slice(0, 80);
  const label = caption ? `รูปจากโพสต์: ${caption}` : "รูปจากโพสต์";

  return (
    <>
      <ul
        className={
          images.length === 1
            ? "grid grid-cols-1"
            : images.length === 2
              ? "grid grid-cols-2 gap-0.5"
              : "grid grid-cols-2 gap-0.5"
        }
      >
        {images.slice(0, 4).map((image, index) => {
          const extra = index === 3 ? images.length - 4 : 0;
          return (
            <li
              key={image.id}
              className={
                images.length === 3 && index === 0 ? "col-span-2" : undefined
              }
            >
              <button
                type="button"
                onClick={() => setOpen(index)}
                aria-label={`ขยายรูปที่ ${index + 1} จาก ${images.length}`}
                className="relative block w-full focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
              >
                {/* A fixed frame per tile keeps the feed's rhythm and
                    stops a stray tall/1-pixel image from setting the card
                    height. The lightbox shows the photo uncropped. */}
                <img
                  src={image.url}
                  alt={index === 0 ? label : ""}
                  loading="lazy"
                  className={`w-full object-cover ${
                    images.length === 1 ? "aspect-4/3" : "aspect-square"
                  }`}
                />
                {extra > 0 ? (
                  <span className="absolute inset-0 flex items-center justify-center bg-black/45 text-lg font-medium text-white">
                    +{extra}
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>

      <dialog
        ref={dialog}
        onClose={() => setOpen(null)}
        onClick={(event) => {
          if (event.target === dialog.current) setOpen(null);
        }}
        aria-label={label}
        className="m-auto bg-transparent p-0 backdrop:bg-black/80"
      >
        {open !== null ? (
          <div className="flex flex-col items-center gap-3 p-4">
            <img
              src={images[open].url}
              alt={label}
              className="max-h-[80dvh] max-w-full rounded-surface object-contain"
            />
            <div className="flex items-center gap-3 text-sm text-white">
              <button
                type="button"
                onClick={() =>
                  setOpen((index) =>
                    index === null
                      ? null
                      : (index - 1 + images.length) % images.length,
                  )
                }
                aria-label="รูปก่อนหน้า"
                className="rounded-full bg-white/15 px-3 py-1.5 hover:bg-white/25 focus-visible:outline-2 focus-visible:outline-white"
              >
                ‹
              </button>
              <span aria-live="polite">
                {open + 1} / {images.length}
              </span>
              <button
                type="button"
                onClick={() =>
                  setOpen((index) =>
                    index === null ? null : (index + 1) % images.length,
                  )
                }
                aria-label="รูปถัดไป"
                className="rounded-full bg-white/15 px-3 py-1.5 hover:bg-white/25 focus-visible:outline-2 focus-visible:outline-white"
              >
                ›
              </button>
              <button
                type="button"
                onClick={() => setOpen(null)}
                className="rounded-full bg-white/15 px-3 py-1.5 hover:bg-white/25 focus-visible:outline-2 focus-visible:outline-white"
              >
                ปิด
              </button>
            </div>
          </div>
        ) : null}
      </dialog>
    </>
  );
}
