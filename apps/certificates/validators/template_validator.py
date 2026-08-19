"""Validation for certificate template design documents.

The document is staff-authored JSON, but "staff-only" is not a licence
to store arbitrary blobs: bounds keep the scene renderable, the element
cap keeps payloads sane, and the signature cap is a product rule (three
signers is the ceiling a certificate can carry with dignity).

Everything here checks *shape*, not taste - numbers are clamped-checked,
enums are closed, strings are length-capped. Values are rendered by the
frontend through typed React styles only, never as markup.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

MAX_ELEMENTS = 60
MAX_SIGNATURES = 3
MAX_TEXT_LENGTH = 500
MAX_NAME_LENGTH = 80
MAX_SRC_LENGTH = 500
CANVAS_LIMIT = 4000

ELEMENT_KINDS = frozenset({"field", "text", "image", "signature", "box"})

FIELD_KEYS = frozenset(
    {
        "recipient_first_name",
        "recipient_last_name",
        "recipient_full_name",
        "course_name",
        "course_description",
        "completion_date",
        "certificate_id",
        "instructor_name",
        "instructor_title",
        "course_duration",
        "achievement_text",
    }
)

_NUMERIC_BOUNDS = {
    "x": (-CANVAS_LIMIT, CANVAS_LIMIT),
    "y": (-CANVAS_LIMIT, CANVAS_LIMIT),
    "w": (1, CANVAS_LIMIT),
    "h": (1, CANVAS_LIMIT),
    "rotation": (-360, 360),
    "opacity": (0, 1),
    "z": (0, 1000),
}


def _require_number(
    value: Any, *, key: str, low: float, high: float
) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"Element {key} must be a number.")
    if not low <= value <= high:
        raise ValidationError(f"Element {key} must be between {low} and {high}.")


def _require_short_text(value: Any, *, key: str, limit: int) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"Element {key} must be a string.")
    if len(value) > limit:
        raise ValidationError(f"Element {key} exceeds {limit} characters.")


def validate_design(document: Any) -> None:
    """Validate one design document.

    Args:
        document: The submitted design JSON.

    Raises:
        django.core.exceptions.ValidationError: If the document is not a
            renderable scene within the caps above.
    """
    if not isinstance(document, dict):
        raise ValidationError("Design must be an object.")

    size = document.get("size")
    if not isinstance(size, dict):
        raise ValidationError("Design needs a size object.")
    _require_number(size.get("width"), key="size.width", low=100, high=CANVAS_LIMIT)
    _require_number(size.get("height"), key="size.height", low=100, high=CANVAS_LIMIT)

    background = document.get("background", "")
    _require_short_text(background, key="background", limit=64)

    elements = document.get("elements")
    if not isinstance(elements, list):
        raise ValidationError("Design needs an elements list.")
    if len(elements) > MAX_ELEMENTS:
        raise ValidationError(f"A design holds at most {MAX_ELEMENTS} elements.")

    signatures = 0
    seen_ids: set[str] = set()
    for element in elements:
        if not isinstance(element, dict):
            raise ValidationError("Each element must be an object.")

        element_id = element.get("id")
        _require_short_text(element_id, key="id", limit=40)
        if element_id in seen_ids:
            raise ValidationError("Element ids must be unique.")
        seen_ids.add(element_id)

        kind = element.get("kind")
        if kind not in ELEMENT_KINDS:
            raise ValidationError(f"Unknown element kind: {kind!r}.")
        if kind == "signature":
            signatures += 1

        _require_short_text(element.get("name", ""), key="name", limit=MAX_NAME_LENGTH)

        for key, (low, high) in _NUMERIC_BOUNDS.items():
            _require_number(element.get(key, 0), key=key, low=low, high=high)

        for flag in ("locked", "hidden"):
            if not isinstance(element.get(flag, False), bool):
                raise ValidationError(f"Element {flag} must be a boolean.")

        if kind == "field" and element.get("field") not in FIELD_KEYS:
            raise ValidationError(f"Unknown field key: {element.get('field')!r}.")
        if kind in ("text", "field"):
            # On a field element, a non-blank ``text`` is the staff
            # override ("มอบโดย …") that replaces the automatic value on
            # every certificate - same length cap as free text.
            _require_short_text(
                element.get("text", ""), key="text", limit=MAX_TEXT_LENGTH
            )
        if kind == "image":
            _require_short_text(element.get("src", ""), key="src", limit=MAX_SRC_LENGTH)
        if kind == "signature":
            signature = element.get("signature")
            if not isinstance(signature, dict):
                raise ValidationError("Signature elements need a signature object.")
            for key in ("name", "title", "organization", "image"):
                _require_short_text(
                    signature.get(key, ""), key=f"signature.{key}", limit=200
                )

        style = element.get("style", {})
        if not isinstance(style, dict):
            raise ValidationError("Element style must be an object.")
        if len(style) > 20:
            raise ValidationError("Element style holds too many keys.")
        for key, value in style.items():
            _require_short_text(key, key="style key", limit=40)
            if isinstance(value, str):
                _require_short_text(value, key=f"style.{key}", limit=120)
            elif isinstance(value, bool):
                continue
            elif isinstance(value, (int, float)):
                _require_number(value, key=f"style.{key}", low=-2000, high=2000)
            else:
                raise ValidationError(f"style.{key} has an unsupported type.")

    if signatures > MAX_SIGNATURES:
        raise ValidationError(
            f"A certificate carries at most {MAX_SIGNATURES} signatures."
        )
