# ADR 0013 — AI Assistant Foundation

**Status:** Accepted (Phase 7)
**Context:** Phase 7 adds the Thai-first AI assistant: conversations,
messages, versioned prompts, usage tracking, and pluggable providers. This
is foundation only — no autonomous agents, no recommendation engine, no
RAG/vector store, no fine-tuning, no XP rewards.

---

## 1. Why the assistant owns conversation state

`apps/assistant` owns four tables — conversations, messages, prompt
templates, usage logs — and the content apps own none of them. The
dependency arrow points one way:

```
assistant ──▶ recipes    (public selectors)
          ──▶ lessons    (public selectors + the content-gate service)
          ──▶ courses    (public selectors)
```

Recipes, lessons and courses compile without the assistant existing — the
same shape as `progress` (ADR 0012). A recipe knows nothing about being
discussed; a conversation knows *which* recipe it discusses. That keeps AI
churn (prompt changes, provider swaps, future RAG) confined to one app, and
lets the content apps stay shippable leaves.

Lesson context is the one place the assistant calls another app's
**service**, not just selectors: lesson bodies are enrollment-gated, and
that two-layer 404/403 gate has exactly one implementation —
`lesson_service.get_lesson_content`. Re-deriving it from selectors would
duplicate visibility logic, the thing this codebase most consistently
refuses to do. The assistant catches lessons' domain errors at its boundary
and raises its own (`ContextNotFoundError`, `ContextAccessDeniedError`) —
ADR 0008's "every app raises its own errors" holds in both directions.

Context strictness is asymmetric on purpose:

- **Creation is strict.** You cannot anchor a conversation to content you
  cannot read: hidden target → 404, enrollment-gated lesson → 403
  `enrollment_required` (the syllabus already made the lesson public, so a
  404 would lie, and the frontend needs the enroll CTA signal).
- **Sends are lenient.** A target that later vanished (`SET_NULL`) or went
  private degrades to context-free answers. The user keeps their history;
  the assistant immediately stops seeing content the viewer no longer can.

## 2. Why explicit nullable FKs, not GenericForeignKey

The same verdict as reviews/favorites (ADR 0011), reaffirmed:
`recipe`/`lesson`/`course` are three nullable FKs with a check constraint
tying the set field to `context_type`. GFK cannot join, so it cannot
compose the prefix-parameterised visibility Q builders; it keeps no
referential integrity; and it serialises as an opaque `(content_type,
object_id)` pair the OpenAPI schema cannot type. Explicit columns give the
Next.js client typed `recipe_id`/`lesson_id`/`course_id` fields and give
future analytics ("which recipes generate the most questions") a plain
indexed join.

One difference from reviews: targets here are `SET_NULL`, not `CASCADE`,
and the check constraint therefore allows a typed conversation with a NULL
target. Deleting a recipe must not delete a user's chat history — the
conversation degrades (see §1) instead of disappearing.

## 3. Why the provider abstraction exists

The `ai/` package is framework-free: no Django import anywhere in it. The
assistant reads `AI_PROVIDER` from settings and calls
`ai.factory.build_provider(name=…, config=…)` with plain values; providers
speak in frozen dataclasses (`AIMessage` in, `AICompletion` out), never
models or serializers. Swapping OpenAI for a local model — or for the
deterministic mock — is a settings change touching zero assistant code.

The **mock is the default** (`AI_PROVIDER=mock`). Local development and CI
need no API key, cost nothing, and stay deterministic: the mock echoes the
user's message back, which is exactly what makes the Thai round-trip tests
meaningful (the bytes sent must return unchanged through provider, DB and
API). The OpenAI adapter uses the standard library and takes a `base_url`,
so OpenAI-compatible local runtimes (Ollama, vLLM) come free.

Provider failures follow the exception-translation rule: the `ai` package
raises its own `AIProviderError` (plain `Exception` — the package doesn't
know HTTP); the assistant translates to `AssistantUnavailableError` (503,
`assistant_unavailable`).

**The send is deliberately two transactions, not one.** The user's message
commits before the provider is called; the reply and usage log commit
after. A database transaction must never span an external network call — a
30-second provider timeout would hold row locks for its whole duration.
The observable contract: on provider failure the user's message is kept,
no reply appears, 503 is returned, and retrying is safe.

## 4. Why prompts are versioned

Prompt text is data, not code (`PromptTemplate`: name × language ×
version, `is_active`). Changing the assistant's behaviour must not require
a deploy — and must not silently change **old** conversations, whose
transcripts were shaped by the prompt they started under. Every
conversation stamps `prompt_version` at creation (the `published_at`
stamp-once pattern) and resolves that exact version on every send; new
conversations pick up whatever row is active. A partial unique constraint
(`(name, language) WHERE is_active`) makes "at most one active version"
a database guarantee, and version "1" ships as a data migration so a fresh
deployment answers immediately.

## 5. Why messages are append-only

There is no edit or delete API, no `updated_at`, and the repository
exposes only `add`. The transcript is the record of what was actually said
— to the user *and* to the model. Rewriting it would falsify the very
context that produced later replies, and would break usage accounting
(tokens were spent on the words as sent). The LearningActivity ledger
(ADR 0012) set the precedent: facts about the past are immutable.
`AIUsageLog` is a separate append-only table rather than message columns
because it answers to a different master — billing/quota survives
conversation deletion (messages CASCADE with their conversation; the
ledger does not).

## 6. Why Thai is first-class

The platform's users bake in Thai. `language` is a conversation field
(`th` default, `en` second), prompt templates exist per language with the
Thai versions written natively — not translated placeholders — and the
system prompt instructs the model to answer in the conversation's
language. UTF-8 is asserted end to end: model tests round-trip Thai +
emoji + multiline through the database, API tests through HTTP, and the
live e2e through a real server. `ensure_ascii=False` when rendering the
context block keeps Thai readable to the model instead of `\uXXXX`
escapes. This continues the Phase 2 decision (`allow_unicode` slugs) that
Thai content is the norm, not an edge case.

## 7. Why RAG / vector search is postponed

RAG earns its complexity when the corpus outgrows the prompt window. A
single recipe or lesson — the only context this phase anchors to — fits in
one system prompt, so retrieval infrastructure (embeddings, a vector
store, chunking, re-ranking, index invalidation on every content edit)
would today be a second copy of content that `context_service` already
loads live through visibility-checked selectors, with zero staleness. The
seams RAG will later need are already in place: providers are behind
adapters, context is a plain dict built in one module, and the `ai/`
package has reserved stubs (`embeddings/`, `vector_store/`). When
cross-content questions arrive ("which of my courses covers choux?"),
retrieval slots in behind `context_service` without touching the API.

## Security posture

- **Owner-only**: every conversation query filters by owner; "not yours"
  and "does not exist" are the same 404.
- **Prompt-injection boundary**: the system prompt is template text
  (server-owned) plus a fenced context block labelled "reference data, not
  instructions"; user content travels only as `user` turns and the
  `system` role is never stored, so stored content structurally cannot
  become a system message. Templates additionally state the boundary
  in-band.
- **Rate limiting**: sends are throttled per user via the
  `infrastructure.cache` counters (the auth pattern) *before* the provider
  is reached — every send costs real money. Quota/billing later enforces
  against `AIUsageLog` aggregates at the same hook.
- **Bounded input**: user messages are capped (4000 chars) at both the
  serializer and the service; context text fields are truncated before
  entering the prompt.

## Consequences

- Anonymous users cannot converse (every endpoint requires auth) — revisit
  if a public "ask about this recipe" teaser is ever wanted.
- A retried send after a 503 duplicates the user's message in the
  transcript (the reply was never generated). Accepted for the foundation;
  an idempotency key can close it later without schema change.
- The provider is called synchronously in-request. Streaming/async (Celery
  or SSE) is a view-layer change; the service seam already isolates it.
- `quiz` context is deliberately absent: quizzes are assessments, and an
  assistant with quiz content in scope is an answer-leak vector next to
  the answer-key secrecy work of Phase 4.
