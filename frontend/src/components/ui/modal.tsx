"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * Structural modal on the native `<dialog>` element — focus trapping,
 * Escape handling and the top-layer come from the platform, not from
 * library code the design phase might replace.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        // Backdrop click: the dialog element itself is the target.
        if (event.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto w-full max-w-md rounded-surface border border-edge bg-surface-raised p-0 shadow-overlay",
        "backdrop:bg-black/40",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-edge px-4 py-3">
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="ปิด"
          className="rounded-control px-2 text-fg-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
        >
          ✕
        </button>
      </div>
      <div className="p-4">{children}</div>
    </dialog>
  );
}
