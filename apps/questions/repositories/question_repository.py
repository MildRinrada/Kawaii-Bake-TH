"""Write-side database access for the question bank.

Home of the two write primitives the freeze design rests on:

* :func:`freeze` — the idempotent, monotonic conditional UPDATE.
* :func:`acquire_edit_gate` — the optimistic gate every content mutation must
  pass first. Its UPDATE both checks ``frozen_at IS NULL`` **and** takes the
  row's write lock, so a concurrent freeze (from a quiz attempt starting) is
  serialized by the database itself — no ``select_for_update``, no race window.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.questions.constants import TAG_SLUG_MAX_LENGTH, TAG_SLUG_SUFFIX_BYTES
from apps.questions.models import AnswerChoice, Question, QuestionTag


def create_question(
    *,
    author_id: int,
    choices: Sequence[Mapping[str, Any]],
    tag_ids: Sequence[int],
    **fields: Any,
) -> Question:
    """Create a question with its choices and tags atomically.

    Args:
        author_id: Primary key of the author.
        choices: Validated choice payloads, in display order.
        tag_ids: Primary keys of tags to assign.
        **fields: Remaining question field values.

    Returns:
        The created question.
    """
    with transaction.atomic():
        question = Question.objects.create(author_id=author_id, **fields)
        _insert_choices(question=question, choices=choices)
        if tag_ids:
            question.tags.set(tag_ids)
    return question


def acquire_edit_gate(*, question_id: int) -> bool:
    """Attempt the frozen-state gate for a content mutation.

    Returns:
        ``True`` when the question exists and is not frozen — the row's write
        lock is now held until the surrounding transaction ends. ``False``
        when frozen or absent; the caller distinguishes those two.
    """
    updated = Question.objects.filter(
        pk=question_id, frozen_at__isnull=True
    ).update(updated_at=timezone.now())
    return updated == 1


def update_question(*, question: Question, changes: Mapping[str, Any]) -> Question:
    """Apply changes to a question in a single UPDATE.

    Args:
        question: The question to update.
        changes: Field name to new value.

    Returns:
        The updated question.
    """
    if not changes:
        return question

    for field, value in changes.items():
        setattr(question, field, value)
    question.save(update_fields=[*changes.keys(), "updated_at"])
    return question


def replace_choices(
    *, question: Question, choices: Sequence[Mapping[str, Any]]
) -> None:
    """Replace a question's choices as a collection.

    Only ever called behind :func:`acquire_edit_gate`: an unfrozen question
    has no attempt selections pointing at its choices, so wholesale replace
    destroys nothing.

    Args:
        question: The question whose choices to replace.
        choices: Validated choice payloads, in display order.
    """
    question.choices.all().delete()
    _insert_choices(question=question, choices=choices)


def delete_question(*, question: Question) -> None:
    """Delete a question and its choices.

    Raises:
        django.db.models.ProtectedError: If a quiz still references it — the
            service maps this to the ``question_in_use`` domain error.
    """
    question.delete()


def freeze(*, question_ids: Sequence[int]) -> int:
    """Freeze questions that are not yet frozen. Idempotent and monotonic.

    Affecting fewer rows than requested is **success**, not conflict — it
    means another attempt froze some of them first, which is the desired end
    state. There is no unfreeze.

    Args:
        question_ids: Primary keys of the questions to freeze.

    Returns:
        How many rows were newly frozen.
    """
    if not question_ids:
        return 0
    return Question.objects.filter(
        pk__in=question_ids, frozen_at__isnull=True
    ).update(frozen_at=timezone.now())


def get_or_create_tags(*, names: Sequence[str]) -> list[int]:
    """Resolve tag names to ids, creating missing tags.

    Case-insensitive: "Bread" and "bread" resolve to one tag. Slug collisions
    (two names slugifying identically) fall back to a random suffix.

    Args:
        names: Tag names as typed by the author.

    Returns:
        Tag primary keys, in input order, de-duplicated.
    """
    ids: list[int] = []
    seen: set[str] = set()
    for name in names:
        cleaned = " ".join(name.split())
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        ids.append(_resolve_tag(name=cleaned))
    return ids


def _resolve_tag(*, name: str) -> int:
    """Find or create one tag, tolerating concurrent creation.

    Attempt-and-catch in a savepoint, like every other optimistic insert in
    the project: a concurrent request creating the same name (or a distinct
    name colliding on slug) surfaces as ``IntegrityError`` and resolves to a
    re-fetch or a suffixed slug.
    """
    existing = QuestionTag.objects.filter(name__iexact=name).first()
    if existing is not None:
        return existing.pk

    base = slugify(name, allow_unicode=True)[:TAG_SLUG_MAX_LENGTH].rstrip("-")
    candidate = base or f"tag-{secrets.token_hex(TAG_SLUG_SUFFIX_BYTES)}"
    for _ in range(2):
        try:
            with transaction.atomic():
                return QuestionTag.objects.create(name=name, slug=candidate).pk
        except IntegrityError:
            racer = QuestionTag.objects.filter(name__iexact=name).first()
            if racer is not None:
                return racer.pk
            # Distinct name, same slug — retry once with a random suffix.
            suffix = secrets.token_hex(TAG_SLUG_SUFFIX_BYTES)
            candidate = f"{base or 'tag'}-{suffix}"
    raise IntegrityError(f"Could not allocate a slug for tag {name!r}.")


def _insert_choices(
    *, question: Question, choices: Sequence[Mapping[str, Any]]
) -> None:
    """Bulk-insert choices with dense, server-assigned positions."""
    AnswerChoice.objects.bulk_create(
        AnswerChoice(
            question=question,
            text=str(choice["text"]).strip(),
            is_correct=bool(choice.get("is_correct", False)),
            position=index,
        )
        for index, choice in enumerate(choices)
    )
