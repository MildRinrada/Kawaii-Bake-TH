"""Shared serializer behaviour."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


class CommaSeparatedCharField(serializers.CharField):
    """A comma-separated list of short values in a query parameter.

    Comma-separation is the one supported multi-value form: repeated parameters
    (``?a=x&a=y``) arrive in a ``QueryDict`` where ``.get()`` silently returns
    only the last value.
    """

    def __init__(self, *args: Any, max_items: int = 10, **kwargs: Any) -> None:
        """Store the item cap and defer to ``CharField``."""
        self.max_items = max_items
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data: Any) -> tuple[str, ...]:
        """Split ``data`` on commas, dropping blanks.

        Raises:
            rest_framework.exceptions.ValidationError: If too many values.
        """
        raw = super().to_internal_value(data)
        values = tuple(part.strip() for part in raw.split(",") if part.strip())
        if len(values) > self.max_items:
            raise serializers.ValidationError(
                f"Provide at most {self.max_items} comma-separated values."
            )
        return values


class CommaSeparatedChoiceField(CommaSeparatedCharField):
    """A comma-separated list constrained to an allow-list."""

    def __init__(self, *args: Any, choices: Any, **kwargs: Any) -> None:
        """Store the permitted values."""
        self.allowed = {value for value, _label in choices}
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data: Any) -> tuple[str, ...]:
        """Split and validate membership.

        Raises:
            rest_framework.exceptions.ValidationError: On an unknown value.
        """
        values = super().to_internal_value(data)
        unknown = [value for value in values if value not in self.allowed]
        if unknown:
            allowed = ", ".join(sorted(self.allowed))
            raise serializers.ValidationError(
                f"Unknown value(s): {', '.join(unknown)}. Choose from: {allowed}."
            )
        return values


class StrictSerializer(serializers.Serializer):
    """Serializer that rejects keys it does not declare.

    DRF silently discards unknown keys, so a client typo such as
    ``favourite_categories`` would return ``200 OK`` while changing nothing 
    an expensive debugging session for the frontend. Failing loudly is kinder.
    """

    def to_internal_value(self, data: Any) -> Any:
        """Validate that no undeclared keys were submitted.

        Args:
            data: The raw incoming payload.

        Returns:
            The validated data.

        Raises:
            rest_framework.exceptions.ValidationError: If unknown keys are present.
        """
        if hasattr(data, "keys"):
            unknown = set(data.keys()) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {key: ["Unrecognised field."] for key in sorted(unknown)}
                )
        return super().to_internal_value(data)


class PaginatedFilterSerializer(StrictSerializer):
    """Base for strict query-parameter validation on a paginated list.

    A strict serializer rejects any key it does not declare - which is
    the point, so a typo'd filter is a 400 rather than a silently
    unfiltered page. That makes it the serializer's job to know about the
    paginator's own parameters too: without these two fields, page 2 of
    any list would be rejected as an unknown filter.
    """

    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=200, required=False)
