"""Exceptions raised by AI providers.

Deliberately plain ``Exception`` subclasses, **not** ``DomainError``: this
package is framework-free and knows nothing about HTTP. The assistant app
catches these at its boundary and raises its own domain errors (ADR 0008 —
a callee never raises the caller's exception, and vice versa).
"""

from __future__ import annotations


class AIProviderError(Exception):
    """Base class for anything that goes wrong while generating a completion."""


class ProviderNotConfiguredError(AIProviderError):
    """Raised when a provider is selected but its credentials are missing."""


class UnknownProviderError(AIProviderError):
    """Raised when the configured provider name matches no registered provider."""
