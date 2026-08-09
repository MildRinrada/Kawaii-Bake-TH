"""Read serializers for quizzes.

The taker question/choice serializers render **DTOs** from the questions
app's public selector — objects that structurally have no ``is_correct``
field. There is no owner variant of the quiz payload: correctness is only
ever readable through the owner's own question-bank endpoints.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.recipes.api.serializers.recipe_serializers import AuthorRefSerializer


class TakerChoiceSerializer(serializers.Serializer):
    """One answer choice as shown to a taker. No correctness here."""

    id = serializers.IntegerField(read_only=True)
    text = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)


class TakerQuestionSerializer(serializers.Serializer):
    """One question as shown to a taker."""

    id = serializers.IntegerField(read_only=True)
    question_type = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)
    difficulty = serializers.CharField(read_only=True)
    choices = TakerChoiceSerializer(many=True, read_only=True)


class QuizListItemSerializer(serializers.Serializer):
    """One quiz in a listing.

    ``id`` is included because it is the value other resources link with
    (``Lesson.quiz_id``); slugs stay the public URL identity.
    """

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    pass_percent = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    visibility = serializers.CharField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    owner = AuthorRefSerializer(read_only=True)


class QuizDetailSerializer(QuizListItemSerializer):
    """A full quiz, questions included in the taker-safe shape."""

    description = serializers.CharField(read_only=True)
    questions = serializers.SerializerMethodField()

    @extend_schema_field(TakerQuestionSerializer(many=True))
    def get_questions(self, obj: object) -> list[dict[str, object]]:
        """Render the composition passed in by the view via context."""
        questions = self.context.get("questions", [])
        return TakerQuestionSerializer(questions, many=True).data
