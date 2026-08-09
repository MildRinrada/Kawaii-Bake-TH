"""Read serializers for quiz attempts."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.quizzes.api.serializers.quiz_serializers import TakerQuestionSerializer


class AttemptSummarySerializer(serializers.Serializer):
    """One attempt's headline numbers — all denormalized at grading time."""

    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True)
    submitted_at = serializers.DateTimeField(read_only=True, allow_null=True)
    score = serializers.IntegerField(read_only=True)
    max_score = serializers.IntegerField(read_only=True)
    correct_count = serializers.IntegerField(read_only=True)
    incorrect_count = serializers.IntegerField(read_only=True)
    percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    passed = serializers.BooleanField(read_only=True, allow_null=True)


class AttemptAnswerSerializer(serializers.Serializer):
    """One snapshot row: the question (taker shape), selection and outcome.

    ``explanation`` is present only on submitted attempts — the view passes
    an empty mapping otherwise. ``was_correct`` reveals the outcome, never
    the key: a wrong answer does not say which choice was right.
    """

    question_id = serializers.IntegerField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    points_possible = serializers.IntegerField(read_only=True)
    points_awarded = serializers.IntegerField(read_only=True)
    was_correct = serializers.BooleanField(read_only=True, allow_null=True)
    selected_choice_ids = serializers.SerializerMethodField()
    question = serializers.SerializerMethodField()
    explanation = serializers.SerializerMethodField()

    def get_selected_choice_ids(self, obj: Any) -> list[int]:
        """Return the prefetched selection as ids."""
        return sorted(choice.pk for choice in obj.selected_choices.all())

    def get_question(self, obj: Any) -> dict[str, Any] | None:
        """Render the taker-shaped question DTO from context."""
        dto = self.context.get("questions", {}).get(obj.question_id)
        return TakerQuestionSerializer(dto).data if dto is not None else None

    def get_explanation(self, obj: Any) -> str:
        """Return the post-submit explanation, empty until submitted."""
        return self.context.get("explanations", {}).get(obj.question_id, "")
