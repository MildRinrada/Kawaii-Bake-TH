"""Test data builders for the review domain."""

from __future__ import annotations

from typing import Any

from apps.reviews.constants import ReviewStatus
from apps.reviews.models import Review

THAI_COMMENT = "สูตรนี้ทำตามแล้วอร่อยมาก ขนมปังนุ่มเหมือนซื้อจากร้าน"


def create_review(
    *,
    user: Any,
    recipe: Any = None,
    course: Any = None,
    rating: int = 4,
    status: str = ReviewStatus.ACTIVE,
    **extra: Any,
) -> Review:
    """Create a review directly at the model layer."""
    return Review.objects.create(
        user=user,
        recipe=recipe,
        course=course,
        rating=rating,
        comment=extra.pop("comment", THAI_COMMENT),
        status=status,
        **extra,
    )
