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
 */
export function RecipeCard({ recipe }: { recipe: RecipeListItem }) {
  return (
    <Link
      href={`/recipes/${recipe.slug}`}
      className="group block rounded-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Card className="overflow-hidden transition-[transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-overlay">
        <div className="aspect-[4/3] w-full overflow-hidden">
          <MediaFrame src={recipe.cover_image_url} seed={recipe.slug} />
        </div>
        <div className="space-y-2 p-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <DifficultyBadge level={recipe.difficulty} />
            {recipe.categories.slice(0, 2).map((category) => (
              <Badge key={category.slug} tone={flavorFor(category.slug)}>
                {category.name}
              </Badge>
            ))}
          </div>
          <h3 className="font-display line-clamp-2 font-medium text-fg group-hover:text-accent-hover">
            {recipe.title}
          </h3>
          <p className="line-clamp-2 text-sm text-fg-muted">{recipe.summary}</p>
          <p className="flex items-center justify-between text-xs text-fg-subtle">
            <span>โดย {recipe.author.display_name || recipe.author.username}</span>
            <span className="flex items-center gap-1">
              <Icon name="ui/clock" className="size-3.5" /> {recipe.total_minutes} นาที
            </span>
          </p>
        </div>
      </Card>
    </Link>
  );
}
