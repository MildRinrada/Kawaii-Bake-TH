"use client";

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/cn";

export interface DropdownItem {
  key: string;
  label: ReactNode;
  onSelect: () => void;
  /** Draw a dividing rule above this item - starts a new group. */
  separator?: boolean;
}

/** Minimal structural menu: outside-click + Escape close, ARIA wiring. */
export function Dropdown({
  trigger,
  items,
  align = "end",
}: {
  trigger: ReactNode;
  items: DropdownItem[];
  align?: "start" | "end";
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="rounded-control focus-visible:outline-2 focus-visible:outline-focus"
      >
        {trigger}
      </button>
      {open ? (
        <div
          role="menu"
          className={cn(
            "absolute z-20 mt-1 min-w-40 rounded-surface border border-edge bg-surface-raised py-1 shadow-overlay",
            align === "end" ? "right-0" : "left-0",
          )}
        >
          {items.map((item) => (
            <div key={item.key}>
              {item.separator ? (
                <hr role="separator" className="my-1 border-edge" />
              ) : null}
              <button
                role="menuitem"
                type="button"
                onClick={() => {
                  setOpen(false);
                  item.onSelect();
                }}
                className="block w-full px-3 py-2 text-left text-sm text-fg hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
              >
                {item.label}
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
