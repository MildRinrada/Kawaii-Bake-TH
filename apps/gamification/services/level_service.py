"""The level curve  a pure function from total XP to level standing.

Progressive: advancing from level ``L`` to ``L+1`` costs ``L × 100`` XP,
so early levels come fast and the curve stretches naturally. The curve
lives in code, not in a table: it is a rule, not content, and changing it
plus running recalculation re-derives every stored level consistently.
"""

from __future__ import annotations

from dataclasses import dataclass

# XP to go from level L to L+1 = L * LEVEL_STEP.
LEVEL_STEP = 100


@dataclass(frozen=True)
class LevelInfo:
    """A user's standing on the level curve.

    Attributes:
        level: Current level (1-based; an empty ledger is level 1).
        xp_into_level: XP accumulated past the current level's threshold.
        xp_for_next_level: Total XP inside this level before promotion.
        total_xp: The ledger sum this standing was derived from.
    """

    level: int
    xp_into_level: int
    xp_for_next_level: int
    total_xp: int


def xp_for_level(*, level: int) -> int:
    """XP required to advance out of ``level``.

    The single public statement of the curve, so API payloads and clients
    never restate it (ADR 0024).

    Args:
        level: A 1-based level number.

    Returns:
        The XP span of that level.
    """
    return max(1, level) * LEVEL_STEP


def calculate_level(*, total_xp: int) -> LevelInfo:
    """Map a ledger total onto the curve.

    Args:
        total_xp: Sum of the user's XP ledger.

    Returns:
        The derived standing.
    """
    remaining = max(0, total_xp)
    level = 1
    while remaining >= level * LEVEL_STEP:
        remaining -= level * LEVEL_STEP
        level += 1
    return LevelInfo(
        level=level,
        xp_into_level=remaining,
        xp_for_next_level=xp_for_level(level=level),
        total_xp=max(0, total_xp),
    )
