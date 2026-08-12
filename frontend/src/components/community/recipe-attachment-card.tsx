"use client";

/**
 * The recipe (or course) a post points at.
 *
 * The feed payload's `_RecipeRef` carries only `{id, slug, title}`, so the
 * rich card  cover, difficulty, category, author  needs the recipe's own
 * list row. The feed page fetches the public recipe list **once** and
 * passes matches down through `details`; this component renders the rich
 * card when it has one and a compact link chip when it does not.
 *
 * That fallback is also the correctness story: a recipe that has become
 * private, unlisted or archived is absent from the public list, so the
 * attachment degrades to a plain reference instead of leaking a card for
 * content the viewer may not open. The post's own FK is `SET_NULL`, so a
 * deleted recipe simply leaves no attachment at all.
 *
 * Either way it stays visibly a *reference*, never the body of the post.
 */

import Link from "next/link";

import type { RecipeListItem, Schemas } from "@/lib/api/models";
import { Badge, DifficultyBadge, flavorFor } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { MediaFrame } from "@/components/content/media-frame";

type Ref = Schemas["_RecipeRef"] | Schemas["_CourseRef"] | null;

export function RecipeAttachmentCard({
  recipe,
  course,
  details,
}: {
  recipe?: Ref;
  course?: Ref;
  /** The matching public recipe row, when the feed found one. */
  details?: RecipeListItem | null;
}) {
  const target = recipe
    ? { href: `/recipes/${recipe.slug}`, kind: "สูตร", title: recipe.title }
    : course
      ? { href: `/courses/${course.slug}`, kind: "คอร์ส", title: course.title }
      : null;

  if (!target) return null;

  // Rich card  only when the recipe is genuinely public right now.
  if (recipe && details) {
    return (
      <Link
        href={target.href as "/recipes/[slug]"}
        aria-label={`ดูสูตร ${details.title}`}
        className="group flex gap-3 rounded-control border border-edge bg-surface-sunken/50 p-2.5 transition-colors hover:border-accent/50 hover:bg-accent-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        <span className="size-20 shrink-0 overflow-hidden rounded-control">
          <MediaFrame src={details.cover_image_url} seed={details.slug} className="text-2xl" />
        </span>
        <span className="min-w-0 flex-1 py-0.5">
          <span className="flex items-center gap-1.5 text-xs text-fg-subtle">
            <Icon name="ui/paperclip" className="size-4" />
            โพสต์นี้แนบสูตร
          </span>
          <span className="font-display mt-0.5 block truncate font-medium text-fg group-hover:underline">
            {details.title}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-1.5">
            <DifficultyBadge level={details.difficulty} />
            {details.categories.slice(0, 1).map((category) => (
              <Badge key={category.slug} tone={flavorFor(category.slug)}>
                {category.name}
              </Badge>
            ))}
            <span className="text-xs text-fg-subtle">
              โดย {details.author.display_name || details.author.username}
            </span>
          </span>
        </span>
        <span aria-hidden className="self-center pr-1 text-sm text-accent">
          ดูสูตร →
        </span>
      </Link>
    );
  }

  // Compact chip: a course, or a recipe the public list no longer carries.
  return (
    <Link
      href={target.href as "/recipes/[slug]"}
      className="flex items-center gap-2.5 rounded-control border border-edge bg-surface-sunken/60 px-3 py-2 transition-colors hover:border-accent/50 hover:bg-accent-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      <Icon name="ui/paperclip" className="size-4 text-fg-subtle" />
      <span className="min-w-0 flex-1">
        <span className="block text-xs text-fg-subtle">
          โพสต์นี้แนบ{target.kind}
        </span>
        <span className="block truncate text-sm font-medium text-fg">
          {target.title}
        </span>
      </span>
      <span aria-hidden className="shrink-0 text-xs text-accent">
        ดู →
      </span>
    </Link>
  );
}
