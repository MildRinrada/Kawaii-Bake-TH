"""Domain validation for preparation steps."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.core.exceptions import ValidationError

from apps.recipes.constants import MAX_STEPS_PER_RECIPE


def validate_steps(steps: Sequence[dict[str, Any]]) -> None:
    """Validate a full set of steps.

    An empty list is permitted: drafts must be saveable while incomplete. The
    "at least one step" rule belongs to ``publish_validator``.

    Args:
        steps: Submitted steps, in display order.

    Raises:
        ValidationError: If the set is too large, a body is blank, or a duration
            is negative.
    """
    if len(steps) > MAX_STEPS_PER_RECIPE:
        raise ValidationError(
            {"steps": [f"A recipe can have at most {MAX_STEPS_PER_RECIPE} steps."]}
        )

    for index, step in enumerate(steps):
        body = (step.get("body") or "").strip()
        if not body:
            raise ValidationError({"steps": [f"Step {index + 1} cannot be empty."]})

        duration = step.get("duration_minutes")
        if duration is not None and duration < 0:
            raise ValidationError(
                {"steps": [f"Step {index + 1} cannot have a negative duration."]}
            )
