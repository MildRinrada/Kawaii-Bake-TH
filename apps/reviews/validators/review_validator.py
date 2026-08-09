"""Domain rules for reviews.

The serializer validates the message (types, lengths, choice membership);
this validates meaning: a comment of pure whitespace is no comment.
"""

from __future__ import annotations


def normalize_comment(comment: str | None) -> str:
    """Collapse a missing or whitespace-only comment to the empty string.

    Rating-only reviews are legitimate — the empty string is the canonical
    "no comment", so listings never render whitespace ghosts.

    Args:
        comment: The raw comment, possibly ``None``.

    Returns:
        The stripped comment, or ``""``.
    """
    if comment is None:
        return ""
    return comment.strip()
