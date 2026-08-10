"use client";

/* eslint-disable @next/next/no-img-element -- the source is a local
   object URL for a file the user just picked; next/image cannot optimise
   a blob and would only add a loader round-trip */

/**
 * A fixed-aspect crop dialog: pick a file, frame it, get a Blob back.
 *
 * ## The geometry
 *
 * Everything is expressed in two resolution-independent numbers —
 * `zoom` (≥ 1) and `center` (the point of the *image*, normalised to
 * 0–1, that sits at the middle of the frame). From those the crop
 * rectangle is derived in the image's own pixels, and the preview is
 * positioned with **percentages of the frame**. That is the whole trick:
 * because nothing is stored in screen pixels, the component needs no
 * size state, no `ResizeObserver`, and renders identically at any width.
 * Screen pixels are read exactly once — from the live element, during a
 * drag — to convert a pointer delta into image pixels.
 *
 * `zoom = 1` means "the largest rectangle of the requested aspect that
 * fits inside the image", so the frame is always full: there is no zoom
 * level at which a letterbox gap can appear, and the crop is clamped to
 * stay inside the image on every interaction.
 *
 * ## What comes out
 *
 * A JPEG Blob no wider than `maxOutputWidth` **and never wider than the
 * pixels actually sampled** — zooming into a small photo cannot invent
 * detail, so it does not pretend to. The canvas is painted white first:
 * JPEG has no alpha, and a transparent PNG would otherwise composite
 * onto black.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";

const MAX_ZOOM = 5;
const ZOOM_STEP = 0.15;
/** Keyboard panning, as a fraction of the visible crop per key press. */
const PAN_STEP = 0.04;

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * The crop rectangle in the image's own pixels.
 *
 * `zoom` divides the base rectangle; `center` is clamped so the result
 * can never extend past an edge.
 */
function cropRect(
  natural: { width: number; height: number },
  aspect: number,
  zoom: number,
  center: { x: number; y: number },
): Rect {
  const base =
    natural.width / natural.height > aspect
      ? natural.height * aspect
      : natural.width;
  const width = base / zoom;
  const height = width / aspect;

  const halfX = width / 2 / natural.width;
  const halfY = height / 2 / natural.height;
  const cx = Math.min(Math.max(center.x, halfX), 1 - halfX);
  const cy = Math.min(Math.max(center.y, halfY), 1 - halfY);

  return {
    x: cx * natural.width - width / 2,
    y: cy * natural.height - height / 2,
    width,
    height,
  };
}

export function ImageCropper({
  file,
  aspect,
  title,
  confirmLabel = "บันทึก",
  helpText,
  maxOutputWidth = 1600,
  busy = false,
  onCancel,
  onConfirm,
}: {
  /** The picked file. `null` closes the dialog. */
  file: File | null;
  /** Width ÷ height of the output. */
  aspect: number;
  title: string;
  confirmLabel?: string;
  helpText?: string;
  maxOutputWidth?: number;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: (blob: Blob) => void;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);

  const [loaded, setLoaded] = useState<{
    src: string;
    width: number;
    height: number;
  } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [center, setCenter] = useState({ x: 0.5, y: 0.5 });

  // One object URL per file. Derived rather than stored, so no effect has
  // to write state; the effect below exists only to revoke — a leaked blob
  // URL pins the entire decoded image in memory for the tab's lifetime.
  const source = useMemo(
    () => (file ? URL.createObjectURL(file) : null),
    [file],
  );
  useEffect(() => {
    if (!source) return;
    return () => URL.revokeObjectURL(source);
  }, [source]);

  // Tied to the source it was measured from, so picking a second file
  // cannot briefly crop the new picture using the old one's dimensions.
  const natural = loaded && loaded.src === source ? loaded : null;
  const rect = natural ? cropRect(natural, aspect, zoom, center) : null;

  function panBy(dxImage: number, dyImage: number) {
    if (!natural) return;
    setCenter((current) => ({
      x: current.x + dxImage / natural.width,
      y: current.y + dyImage / natural.height,
    }));
  }

  function onPointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (!natural) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };
  }

  function onPointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId || !rect) return;
    const frame = frameRef.current;
    if (!frame) return;

    // The only place screen pixels enter the model: convert the pointer
    // delta into image pixels using the frame's live width.
    const scale = rect.width / frame.getBoundingClientRect().width;
    panBy(
      -(event.clientX - drag.x) * scale,
      -(event.clientY - drag.y) * scale,
    );
    dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
  }

  function endDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!rect) return;
    const step = { x: rect.width * PAN_STEP, y: rect.height * PAN_STEP };
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-step.x, 0],
      ArrowRight: [step.x, 0],
      ArrowUp: [0, -step.y],
      ArrowDown: [0, step.y],
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    panBy(move[0], move[1]);
  }

  function confirm() {
    const image = imageRef.current;
    if (!image || !rect) return;

    // Never upscale: the output stops at the number of pixels sampled.
    const width = Math.max(1, Math.round(Math.min(maxOutputWidth, rect.width)));
    const height = Math.max(1, Math.round(width / aspect));

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return;

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, width, height);
    context.drawImage(
      image,
      rect.x,
      rect.y,
      rect.width,
      rect.height,
      0,
      0,
      width,
      height,
    );
    canvas.toBlob(
      (blob) => {
        if (blob) onConfirm(blob);
      },
      "image/jpeg",
      0.9,
    );
  }

  return (
    <Modal
      open={file !== null}
      onClose={onCancel}
      title={title}
      className="max-w-2xl"
    >
      <div
        ref={frameRef}
        role="application"
        aria-label="ปรับตำแหน่งภาพ ใช้ปุ่มลูกศรเพื่อเลื่อน"
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        style={{ aspectRatio: String(aspect) }}
        className="relative w-full touch-none select-none overflow-hidden rounded-surface bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        {source ? (
          <img
            ref={imageRef}
            src={source}
            alt=""
            aria-hidden
            draggable={false}
            onLoad={(event) => {
              // A newly loaded file starts centred at zoom 1 — inheriting
              // the previous picture's framing would be nonsense. Doing it
              // here rather than in an effect keeps this a plain event.
              setLoaded({
                src: event.currentTarget.src,
                width: event.currentTarget.naturalWidth,
                height: event.currentTarget.naturalHeight,
              });
              setZoom(1);
              setCenter({ x: 0.5, y: 0.5 });
            }}
            className="absolute max-w-none cursor-grab active:cursor-grabbing"
            style={
              natural && rect
                ? {
                    // Percentages of the frame — see the file docstring.
                    width: `${(natural.width / rect.width) * 100}%`,
                    height: `${(natural.height / rect.height) * 100}%`,
                    left: `${(-rect.x / rect.width) * 100}%`,
                    top: `${(-rect.y / rect.height) * 100}%`,
                  }
                : { opacity: 0 }
            }
          />
        ) : null}
      </div>

      <label className="mt-4 flex items-center gap-3">
        <Icon name="ui/search" className="size-4 shrink-0 text-fg-muted" />
        <span className="sr-only">ย่อ–ขยายภาพ</span>
        <input
          type="range"
          min={1}
          max={MAX_ZOOM}
          step={ZOOM_STEP}
          value={zoom}
          disabled={!natural}
          onChange={(event) => setZoom(Number(event.target.value))}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-surface-sunken accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        />
      </label>

      <p className="mt-2 text-xs text-fg-subtle">
        {helpText ?? "ลากภาพเพื่อจัดตำแหน่ง แล้วเลื่อนแถบด้านบนเพื่อย่อ–ขยาย"}
      </p>

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          ยกเลิก
        </Button>
        <Button onClick={confirm} loading={busy} disabled={!natural}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
