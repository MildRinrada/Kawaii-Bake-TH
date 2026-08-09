"""Shared constants for the framework-free AI package.

This package must never import Django: the assistant app reads configuration
from settings and passes it in as plain values.
"""

from __future__ import annotations

PROVIDER_MOCK = "mock"
PROVIDER_OPENAI = "openai"

ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
