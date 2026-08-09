# 0003 — Isolate AI Behind a Provider Factory

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

AI providers (Anthropic, OpenAI, Gemini, Ollama) change rapidly in pricing,
capability, and API shape. Coupling Django apps to a specific SDK would spread
provider churn across the codebase.

## Decision

All AI access goes through the standalone `ai/` package. Concrete SDK calls live
only in `ai/providers/*`; `ai/factory.py` selects the provider from settings.
Feature apps call use-case modules (`ai/chatbot`, `ai/recommendation`, ...) and
never import a provider SDK directly. The `ai/` package never imports Django.

## Consequences

- Swapping or A/B-testing providers is a config change.
- AI logic is unit-testable without Django and mockable at the factory seam.
- Requires import-linter contracts to keep the boundary honest.
