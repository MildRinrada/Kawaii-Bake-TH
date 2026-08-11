"use client";

/**
 * Searchable recipe picker for post attachments.
 *
 * Users never type an id. The list is the real `GET /recipes/?search=`
 * public feed  which matters for correctness, not just convenience: the
 * backend only accepts a reference to a **publicly visible** recipe at
 * creation time, and the public feed is exactly that set. Offering the
 * staff-wide `scope=all` list here would let an admin pick a draft and
 * get a 400 back.
 */

import { useEffect, useRef, useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type { RecipeListItem } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useDebounced } from "@/lib/admin/use-paged-list";
import { Button } from "@/components/ui/button";
import { MediaFrame } from "@/components/content/media-frame";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";

export function RecipeSelectorDialog({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (recipe: RecipeListItem) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [term, setTerm] = useState("");
  const search = useDebounced(term, 300);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  const results = useApiQuery(
    (signal) =>
      open
        ? api.get<Paginated<RecipeListItem>>("/recipes/", {
            query: { search: search || undefined, page_size: 12 },
            signal,
          })
        : Promise.resolve(null),
    [open, search],
  );

  const rows = results.data?.results ?? [];

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) onClose();
      }}
      aria-label="เลือกสูตรที่จะแนบ"
      className="m-auto w-full max-w-lg rounded-surface border border-edge bg-surface-raised p-0 shadow-overlay backdrop:bg-black/40"
    >
      <div className="flex items-center justify-between gap-3 border-b border-edge px-4 py-3">
        <h2 className="font-display text-sm font-medium text-fg">
          เลือกสูตรที่จะแนบ
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="ปิด"
          className="rounded-control px-2 text-fg-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/close" className="size-4" />
        </button>
      </div>

      <div className="border-b border-edge px-4 py-3">
        <input
          type="search"
          autoFocus
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="ค้นหาชื่อสูตร…"
          aria-label="ค้นหาสูตร"
          className="block w-full rounded-control border border-edge-strong/50 bg-surface px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
        />
      </div>

      <div className="max-h-96 overflow-y-auto p-2">
        {results.loading ? (
          <div className="space-y-2 p-2" aria-busy="true">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-16 w-full rounded-control" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-fg-muted">
            {search
              ? `ไม่พบสูตรที่ตรงกับ “${search}”`
              : "ยังไม่มีสูตรให้เลือก"}
          </p>
        ) : (
          <ul className="space-y-1">
            {rows.map((recipe) => (
              <li key={recipe.slug}>
                <button
                  type="button"
                  onClick={() => {
                    onSelect(recipe);
                    onClose();
                  }}
                  className="flex w-full items-center gap-3 rounded-control px-2 py-2 text-left hover:bg-accent-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                >
                  <span className="size-12 shrink-0 overflow-hidden rounded-control">
                    <MediaFrame
                      src={recipe.cover_image_url}
                      seed={recipe.slug}
                      className="text-lg"
                    />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-fg">
                      {recipe.title}
                    </span>
                    <span className="block truncate text-xs text-fg-subtle">
                      โดย{" "}
                      {recipe.author.display_name || recipe.author.username} ·{" "}
                      <Icon name="ui/clock" className="inline-block size-3 align-[-2px]" />{" "}
                      {recipe.total_minutes} นาที
                    </span>
                  </span>
                  <span aria-hidden className="shrink-0 text-xs text-accent">
                    เลือก
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex justify-end border-t border-edge px-4 py-3">
        <Button type="button" size="sm" variant="secondary" onClick={onClose}>
          ยกเลิก
        </Button>
      </div>
    </dialog>
  );
}
