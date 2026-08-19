"""Load the bundled recipe content into the database.

Writes through the recipes repositories rather than the ORM directly, so seeded
rows carry the same normalised ingredient names, step positions and derived
``total_minutes`` an API-created recipe would.

The one rule it steps around is ``publish_validator``'s "add a cover image":
seeded recipes ship without artwork on purpose, and refusing to publish them
would leave the whole catalogue invisible until every photo is in place. Every
other publish requirement  title, ingredients, steps, a category  is satisfied
by the data itself and asserted before the row is written.

Idempotent: a seed whose slug already exists is skipped, or refreshed with
``--replace``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.recipe_categories.selectors import category_selector
from apps.recipes.constants import RecipeStatus, RecipeVisibility
from apps.recipes.models import Recipe
from apps.recipes.repositories import (
    ingredient_repository,
    recipe_repository,
    step_repository,
)
from apps.recipes.seeds import SEEDS_BY_CATEGORY, build_payload
from apps.recipes.services import nutrition_service
from apps.recipes.validators import (
    ingredient_validator,
    recipe_validator,
    step_validator,
)

DEFAULT_AUTHOR_EMAIL = "admin@kawaiibake.local"

# Spacing between the publication timestamps of consecutive seeds. Without it
# every recipe shares one timestamp and "newest first" degenerates to id order,
# which makes the listing look like it was pasted in  because it was.
PUBLISH_INTERVAL = timedelta(hours=6)


class Command(BaseCommand):
    """Seed recipes, twenty per category."""

    help = (
        "Load the bundled recipe content (20 per active category). "
        "Existing slugs are skipped unless --replace is given."
    )

    def add_arguments(self, parser: Any) -> None:
        """Declare the command line options."""
        parser.add_argument(
            "--author",
            default=DEFAULT_AUTHOR_EMAIL,
            help=f"Email of the user who owns the seeded recipes (default {DEFAULT_AUTHOR_EMAIL}).",
        )
        parser.add_argument(
            "--categories",
            default="",
            help="Comma-separated category slugs to seed. Default: all bundled categories.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Seed at most this many recipes per category. 0 means all of them.",
        )
        parser.add_argument(
            "--status",
            choices=[RecipeStatus.PUBLISHED, RecipeStatus.DRAFT],
            default=RecipeStatus.PUBLISHED,
            help="Status to give the seeded recipes (default published).",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Refresh recipes whose slug already exists instead of skipping them.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the seed data and report what would happen, writing nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Validate every seed, then create or refresh the recipes."""
        author = self._require_author(email=options["author"])
        selected = self._select_categories(raw=options["categories"])
        limit: int = options["limit"]
        dry_run: bool = options["dry_run"]
        replace: bool = options["replace"]
        status: str = options["status"]

        created = skipped = replaced = 0
        published_at = timezone.now()

        for category_slug in selected:
            seeds = SEEDS_BY_CATEGORY[category_slug]
            if limit > 0:
                seeds = seeds[:limit]

            for seed in seeds:
                payload = build_payload(seed=seed, category_slug=category_slug)
                self._validate(payload=payload, category_slug=category_slug)

                existing = Recipe.objects.filter(slug=payload["slug"]).first()
                if existing is not None and not replace:
                    skipped += 1
                    continue

                # Newest seed first in the listing, then one interval older per
                # recipe, so the catalogue reads as if it grew over time.
                published_at -= PUBLISH_INTERVAL

                if dry_run:
                    created += existing is None
                    replaced += existing is not None
                    continue

                if existing is not None:
                    self._write(
                        payload=payload,
                        author_id=author.pk,
                        status=status,
                        published_at=published_at,
                        recipe=existing,
                    )
                    replaced += 1
                else:
                    self._write(
                        payload=payload,
                        author_id=author.pk,
                        status=status,
                        published_at=published_at,
                    )
                    created += 1

            self.stdout.write(f"  {category_slug}: {len(seeds)} seed(s) processed")

        prefix = "[dry run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{created} created, {replaced} replaced, {skipped} skipped "
                f"(author: {author.email}, status: {status})."
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _require_author(self, *, email: str) -> Any:
        """Fetch the seeding author or fail with a usable message."""
        author = get_user_model().objects.filter(email__iexact=email.strip()).first()
        if author is None:
            raise CommandError(
                f"No user with email {email!r}. Create one first, or pass --author."
            )
        return author

    def _select_categories(self, *, raw: str) -> list[str]:
        """Resolve the requested category slugs against the taxonomy."""
        requested = [slug.strip() for slug in raw.split(",") if slug.strip()]
        unknown = [slug for slug in requested if slug not in SEEDS_BY_CATEGORY]
        if unknown:
            raise CommandError(
                f"No seed data for: {', '.join(sorted(unknown))}. "
                f"Available: {', '.join(SEEDS_BY_CATEGORY)}."
            )

        selected = requested or list(SEEDS_BY_CATEGORY)

        # A category row that is missing or inactive would make every recipe in
        # that batch publish with no category at all, so refuse up front.
        resolved = category_selector.resolve_slugs(slugs=selected)
        missing = [slug for slug in selected if slug not in resolved]
        if missing:
            raise CommandError(
                f"These categories are absent or inactive: {', '.join(missing)}. "
                "Run migrations, or activate them first."
            )
        return selected

    def _validate(self, *, payload: dict[str, Any], category_slug: str) -> None:
        """Run the domain rules the API would run, before writing anything."""
        try:
            recipe_validator.validate_core(payload)
            ingredient_validator.validate_lines(payload["ingredients"])
            step_validator.validate_steps(payload["steps"])
        except ValidationError as error:
            raise CommandError(
                f"Seed {category_slug}/{payload['slug']} is invalid: {error.message_dict}"
            ) from error

        # Publish completeness, minus the cover image this command deliberately
        # allows to be missing.
        if not payload["ingredients"] or not payload["steps"]:
            raise CommandError(
                f"Seed {category_slug}/{payload['slug']} has no ingredients or no steps."
            )

    def _write(
        self,
        *,
        payload: dict[str, Any],
        author_id: int,
        status: str,
        published_at: Any,
        recipe: Recipe | None = None,
    ) -> Recipe:
        """Create or refresh one recipe and all of its children."""
        category_ids = list(
            category_selector.resolve_slugs(slugs=payload["category_slugs"]).values()
        )
        fields = {
            "title": payload["title"],
            "summary": payload["summary"],
            "description": payload["description"],
            "difficulty": payload["difficulty"],
            "prep_minutes": payload["prep_minutes"],
            "cook_minutes": payload["cook_minutes"],
            "total_minutes": payload["prep_minutes"] + payload["cook_minutes"],
            "servings": payload["servings"],
            "visibility": RecipeVisibility.PUBLIC,
            "status": status,
            "published_at": published_at if status == RecipeStatus.PUBLISHED else None,
        }

        with transaction.atomic():
            if recipe is None:
                recipe = recipe_repository.create_recipe(
                    author_id=author_id, slug_base=payload["slug"], **fields
                )
            else:
                recipe_repository.update_recipe(recipe=recipe, changes=fields)

            recipe_repository.set_categories(recipe=recipe, category_ids=category_ids)
            ingredient_repository.replace_ingredients(
                recipe=recipe, lines=payload["ingredients"]
            )
            step_repository.replace_steps(recipe=recipe, steps=payload["steps"])
            if payload["nutrition"]:
                nutrition_service.set_nutrition(
                    recipe=recipe, values=payload["nutrition"]
                )

        return recipe
