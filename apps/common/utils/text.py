"""Pure text helpers shared across apps."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_ingredient_name(name: str) -> str:
    """Return the canonical comparison form of an ingredient name.

    NFC normalisation is required, not cosmetic: Thai combining vowels and
    tone marks have several valid encodings, so visually identical strings
    compare unequal without it and de-duplication silently fails.

    Lived in ``apps.recipes.utils`` through Phase 11; moved here (and
    re-exported from there) when the recommendation app's substitution
    lookup needed the exact same normalisation  two implementations of one
    matching rule would drift, which is the failure mode the
    ``normalized_name`` column exists to prevent.

    Args:
        name: The ingredient name as typed.

    Returns:
        The normalised form used for de-duplication and indexed lookups.
    """
    normalized = unicodedata.normalize("NFC", name).strip().casefold()
    return _WHITESPACE.sub(" ", normalized)
