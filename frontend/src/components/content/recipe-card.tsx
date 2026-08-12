import Link from "next/link";

import type { RecipeListItem } from "@/lib/api/models";
import { Badge, DifficultyBadge, flavorFor } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { MediaFrame } from "@/components/content/media-frame";
import { Icon } from "@/components/ui/icon";

/**
 * Recipe discovery card: photo-led, clear hierarchy (title → meta →
 * author), flavor-toned category chips. One tactile hover lift, nothing
 * busier.
 *
 * Every card in a row is the same height by construction: the body is a
 * flex column, the summary reserves two lines even when the field is
 * blank, and the author/time meta is pushed to the bottom with
 * `mt-auto`. A recipe missing optional text must never change the card's
 * skeleton — and must never *say* it is missing either: the blank line
 * holds its space silently, because "ยังไม่มีคำอธิบาย" is a note to the
 * author, not information for the reader.
 */
export function RecipeCard({ recipe }: { recipe: RecipeListItem }) {
  const author =
    recipe.author.display_name || recipe.author.username || "ไม่ระบุผู้เขียน";
  const summary = recipe.summary?.trim();

  return (
    <Link
      href={`/recipes/${recipe.slug}`}
      className="group block h-full rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Card className="flex h-full flex-col overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay">
        <div className="aspect-4/3 w-full overflow-hidden">
          <MediaFrame src={recipe.cover_image_url} seed={recipe.slug} />
        </div>
        <div className="flex flex-1 flex-col gap-2 p-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <DifficultyBadge level={recipe.difficulty} />
            {recipe.categories.slice(0, 2).map((category) => (
              <Badge key={category.slug} tone={flavorFor(category.slug)}>
                {category.name}
              </Badge>
            ))}
          </div>
          <h3 className="font-display line-clamp-2 font-medium text-fg group-hover:underline">
            {recipe.title}
          </h3>
          <p className="line-clamp-2 min-h-10 text-sm text-fg-muted">
            {summary}
          </p>
          <p className="mt-auto flex items-center justify-between pt-1 text-xs text-fg-subtle">
            <span className="truncate">โดย {author}</span>
            <span className="flex shrink-0 items-center gap-1">
              <Icon name="ui/clock" className="size-3.5" /> {recipe.total_minutes} นาที
            </span>
          </p>
        </div>
      </Card>
    </Link>
  );
}
