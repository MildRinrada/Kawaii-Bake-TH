"""Provider resolution by name.

The assistant app calls ``build_provider(name=settings.AI_PROVIDER, config=…)``
— configuration is read from Django settings **there**, so this package stays
framework-free. Registering a new backend is one entry in ``_BUILDERS``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ai.constants import PROVIDER_MOCK, PROVIDER_OPENAI
from ai.exceptions import UnknownProviderError
from ai.providers.base import AIProvider
from ai.providers.mock import MockAIProvider
from ai.providers.openai import OpenAIProvider


def _build_mock(config: Mapping[str, Any]) -> AIProvider:
    """Build the offline provider; it takes no configuration."""
    return MockAIProvider()


def _build_openai(config: Mapping[str, Any]) -> AIProvider:
    """Build the OpenAI-compatible provider from plain config values."""
    return OpenAIProvider(
        api_key=config.get("api_key"),
        model=config.get("model") or "gpt-4o-mini",
        base_url=config.get("base_url") or "https://api.openai.com/v1",
    )


_BUILDERS: dict[str, Callable[[Mapping[str, Any]], AIProvider]] = {
    PROVIDER_MOCK: _build_mock,
    PROVIDER_OPENAI: _build_openai,
}


def build_provider(
    *, name: str, config: Mapping[str, Any] | None = None
) -> AIProvider:
    """Resolve a provider by name.

    Args:
        name: A registered provider name (``mock``, ``openai``).
        config: Provider-specific plain values (API key, model, base URL).

    Returns:
        A ready-to-use provider instance.

    Raises:
        UnknownProviderError: If ``name`` is not registered.
    """
    builder = _BUILDERS.get(name)
    if builder is None:
        known = ", ".join(sorted(_BUILDERS))
        raise UnknownProviderError(f"Unknown AI provider {name!r}. Known: {known}.")
    return builder(config or {})
