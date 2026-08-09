"""Quiz API routes, mounted at ``/api/v1/quizzes/``.

Literals are declared before ``<str:slug>`` (which also would not match a
path containing ``/``), and every literal is in ``RESERVED_QUIZ_SLUGS``.
"""

from __future__ import annotations

from django.urls import path

from apps.quizzes.api.views.attempt_views import (
    AttemptDetailView,
    AttemptListView,
    QuizStartView,
    QuizSubmitView,
)
from apps.quizzes.api.views.lifecycle_views import (
    QuizArchiveView,
    QuizPublishView,
    QuizUnpublishView,
)
from apps.quizzes.api.views.quiz_views import QuizDetailView, QuizListCreateView

app_name = "quizzes"

urlpatterns = [
    path("", QuizListCreateView.as_view(), name="list"),
    path("<str:slug>/", QuizDetailView.as_view(), name="detail"),
    path("<str:slug>/publish/", QuizPublishView.as_view(), name="publish"),
    path("<str:slug>/unpublish/", QuizUnpublishView.as_view(), name="unpublish"),
    path("<str:slug>/archive/", QuizArchiveView.as_view(), name="archive"),
    path("<str:slug>/start/", QuizStartView.as_view(), name="start"),
    path("<str:slug>/submit/", QuizSubmitView.as_view(), name="submit"),
    path("<str:slug>/attempts/", AttemptListView.as_view(), name="attempts"),
    path(
        "<str:slug>/attempts/<int:attempt_id>/",
        AttemptDetailView.as_view(),
        name="attempt-detail",
    ),
]
