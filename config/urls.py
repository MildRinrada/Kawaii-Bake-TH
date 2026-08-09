"""Root URL configuration.

Django is API-only. The only non-API route is Django admin; everything else
lives under ``/api/v1/`` and is consumed by the Next.js frontend.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

API_V1 = "api/v1/"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(f"{API_V1}auth/", include("apps.authentication.api.urls")),
    # Nested urlconfs share a prefix with the app that owns it (ADR 0009):
    # the prefix is config, not coupling, and the multi-segment patterns
    # cannot collide with the host app's routes.
    path(f"{API_V1}users/", include("apps.favorites.api.urls.me")),
    path(f"{API_V1}users/", include("apps.users.api.urls")),
    path(f"{API_V1}recipe-categories/", include("apps.recipe_categories.api.urls")),
    path(f"{API_V1}recipes/", include("apps.reviews.api.urls.recipe_nested")),
    path(f"{API_V1}recipes/", include("apps.favorites.api.urls.recipe_nested")),
    path(f"{API_V1}recipes/", include("apps.recommendation.api.urls.recipe_nested")),
    path(f"{API_V1}recipes/", include("apps.recipes.api.urls")),
    # Two urlconfs share the courses prefix: the lessons app owns the
    # `{slug}/lessons/…` and `{slug}/progress/` routes (ADR 0009). Django tries
    # each include in order and falls through on no-match; the two-segment
    # patterns cannot collide with courses' single-segment `<str:slug>/`.
    path(f"{API_V1}courses/", include("apps.lessons.api.urls.course_nested")),
    path(f"{API_V1}courses/", include("apps.progress.api.urls.course_nested")),
    path(f"{API_V1}courses/", include("apps.reviews.api.urls.course_nested")),
    path(f"{API_V1}courses/", include("apps.favorites.api.urls.course_nested")),
    path(f"{API_V1}courses/", include("apps.certificates.api.urls.course_nested")),
    path(f"{API_V1}courses/", include("apps.courses.api.urls")),
    path(f"{API_V1}lessons/", include("apps.progress.api.urls.lesson_nested")),
    path(f"{API_V1}lessons/", include("apps.lessons.api.urls")),
    path(f"{API_V1}me/", include("apps.progress.api.urls.me")),
    path(f"{API_V1}me/", include("apps.assistant.api.urls.me")),
    path(f"{API_V1}me/", include("apps.certificates.api.urls.me")),
    path(f"{API_V1}me/notifications/", include("apps.notifications.api.urls")),
    path(f"{API_V1}me/", include("apps.gamification.api.urls.me")),
    path(f"{API_V1}me/", include("apps.rewards.api.urls.me")),
    path(f"{API_V1}me/", include("apps.users.api.urls.me")),
    path(f"{API_V1}rewards/", include("apps.rewards.api.urls")),
    path(f"{API_V1}assistant/", include("apps.assistant.api.urls")),
    path(f"{API_V1}certificates/", include("apps.certificates.api.urls")),
    path(
        f"{API_V1}achievements/",
        include("apps.certificates.api.urls.achievements"),
    ),
    path(f"{API_V1}leaderboard/", include("apps.gamification.api.urls")),
    path(f"{API_V1}questions/", include("apps.questions.api.urls")),
    path(f"{API_V1}quizzes/", include("apps.quizzes.api.urls")),
    path(f"{API_V1}reviews/", include("apps.reviews.api.urls")),
    path(f"{API_V1}gallery/", include("apps.gallery.api.urls")),
    path(f"{API_V1}qa/", include("apps.qa.api.urls")),
    path(f"{API_V1}recommendations/", include("apps.recommendation.api.urls")),
    # OpenAPI schema — the Next.js client generates TypeScript types from this.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
