"""Question bank API routes, mounted at ``/api/v1/questions/``."""

from __future__ import annotations

from django.urls import path

from apps.questions.api.views.question_views import (
    QuestionDetailView,
    QuestionListCreateView,
    QuestionTagListView,
)

app_name = "questions"

urlpatterns = [
    path("", QuestionListCreateView.as_view(), name="list"),
    path("tags/", QuestionTagListView.as_view(), name="tags"),
    path("<int:question_id>/", QuestionDetailView.as_view(), name="detail"),
]
