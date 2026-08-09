"use client";

import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface TabItem {
  key: string;
  label: string;
  content: ReactNode;
}

/** Accessible structural tabs (roving tab pattern kept minimal). */
export function Tabs({
  items,
  initialKey,
}: {
  items: TabItem[];
  initialKey?: string;
}) {
  const [active, setActive] = useState(initialKey ?? items[0]?.key);
  const baseId = useId();

  return (
    <div>
      <div role="tablist" className="flex gap-1 border-b border-edge">
        {items.map((item) => (
          <button
            key={item.key}
            role="tab"
            id={`${baseId}-tab-${item.key}`}
            aria-selected={active === item.key}
            aria-controls={`${baseId}-panel-${item.key}`}
            onClick={() => setActive(item.key)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-focus",
              active === item.key
                ? "border-accent font-medium text-fg"
                : "border-transparent text-fg-muted hover:text-fg",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      {items.map((item) => (
        <div
          key={item.key}
          role="tabpanel"
          id={`${baseId}-panel-${item.key}`}
          aria-labelledby={`${baseId}-tab-${item.key}`}
          hidden={active !== item.key}
          className="py-4"
        >
          {item.content}
        </div>
      ))}
    </div>
  );
}
