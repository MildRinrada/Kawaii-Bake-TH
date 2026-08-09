"""Q&A routes, mounted at ``/api/v1/qa/``."""

from __future__ import annotations

from django.urls import path

from apps.qa.api.views.qa_views import (
    AnswerDetailView,
    ThreadAcceptView,
    ThreadAnswersView,
    ThreadDetailView,
    ThreadListCreateView,
)

app_name = "qa"

urlpatterns = [
    path("threads/", ThreadListCreateView.as_view(), name="thread-list"),
    path("threads/<int:thread_id>/", ThreadDetailView.as_view(), name="thread-detail"),
    path(
        "threads/<int:thread_id>/answers/",
        ThreadAnswersView.as_view(),
        name="thread-answers",
    ),
    path(
        "threads/<int:thread_id>/accept/",
        ThreadAcceptView.as_view(),
        name="thread-accept",
    ),
    path("answers/<int:answer_id>/", AnswerDetailView.as_view(), name="answer-detail"),
]
