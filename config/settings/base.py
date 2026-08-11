"""Base settings shared by every environment.

KawaiiBake's Django layer is **API-only**: it serves JSON to a Next.js frontend.
There are no page templates and no project static files. Templates and
staticfiles remain enabled solely for Django admin and server-rendered emails.

Environment-specific modules (``development``, ``production``, ``testing``)
import everything from here and override only what differs.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------------------------------
# Environment helpers
# --------------------------------------------------------------------------
def env(key: str, default: str | None = None) -> str | None:
    """Return an environment variable as a string."""
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    """Return an environment variable coerced to a boolean."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    """Return an environment variable coerced to an integer."""
    raw = os.environ.get(key)
    return int(raw) if raw else default


def env_list(key: str, default: list[str] | None = None) -> list[str]:
    """Return a comma-separated environment variable as a list."""
    raw = os.environ.get(key)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Security
# --------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-development-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])


# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
]

# Feature apps are added here as each phase is implemented.
# Order documents dependency direction: `recipe_categories` knows nothing about
# `recipes`, while `recipes` owns the many-to-many between them.
LOCAL_APPS = [
    "apps.core",
    "apps.common",
    "apps.users",
    "apps.authentication",
    "apps.recipe_categories",
    "apps.recipes",
    "apps.courses",
    "apps.lessons",
    "apps.questions",
    "apps.quizzes",
    "apps.reviews",
    "apps.favorites",
    "apps.progress",
    "apps.assistant",
    "apps.certificates",
    "apps.gamification",
    "apps.notifications",
    "apps.gallery",
    "apps.qa",
    "apps.recommendation",
    "apps.rewards",
    "apps.security",
    "apps.legal",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    # CorsMiddleware must precede CommonMiddleware so CORS headers survive redirects.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.request_logging.RequestIDMiddleware",
    # Last in, so `request.user` and `request.request_id` are already set
    # when it inspects a request  it records who, not just what.
    "apps.security.middleware.threat_watch.ThreatWatchMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
# DIRS is empty on purpose: there are no project page templates. APP_DIRS stays
# on because Django admin and the email bodies in
# ``apps/authentication/templates/authentication/emails/`` are rendered here.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                # All four are required by Django admin's system checks.
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "kawaiibake"),
        "USER": env("DB_USER", "kawaiibake"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "apps.authentication.auth_backends.email_backend.EmailBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Django's default is PBKDF2-SHA256, which is production-grade.
# `production.py` puts Argon2 first (requires the `argon2-cffi` package).

# Only the Django admin has an interactive login page; the API never redirects.
LOGIN_URL = "admin:login"

# The credential issuer is the single seam between "who you are" and "how the
# client proves it". Phase 1 issues session cookies; swapping in
# `...jwt_issuer.JwtCredentialIssuer` later changes nothing else. See ADR 0007.
AUTH_CREDENTIAL_ISSUER = env(
    "AUTH_CREDENTIAL_ISSUER",
    "apps.authentication.api.credentials.session_issuer.SessionCredentialIssuer",
)


# --------------------------------------------------------------------------
# REST framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.authentication.api.authentication.CsrfEnforcedSessionAuthentication",
    ],
    # Secure by default: public endpoints opt out with `permission_classes = (AllowAny,)`.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "apps.common.api.exception_handler.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "DEFAULT_PAGINATION_CLASS": "apps.common.api.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": env_int("API_PAGE_SIZE", 20),
    # Only the anonymous security ingest opts into throttling; every other
    # endpoint is either authenticated or already cheap.
    "DEFAULT_THROTTLE_RATES": {
        "security_signal": env("SECURITY_SIGNAL_RATE", "30/min"),
    },
}

# --------------------------------------------------------------------------
# Search backend
# --------------------------------------------------------------------------
# The default is portable across PostgreSQL and SQLite and is fully covered by
# the test suite. Point this at
# `infrastructure.search.postgres_search.PostgresSearchBackend` in production
# once the `pg_trgm` extension and its GIN index exist.
SEARCH_BACKEND = env(
    "SEARCH_BACKEND", "infrastructure.search.simple_search.SimpleSearchBackend"
)

SPECTACULAR_SETTINGS = {
    "TITLE": "KawaiiBake API",
    "DESCRIPTION": "Backend API for the KawaiiBake bakery learning platform.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    # Fields sharing a name across apps ("difficulty") or a choice set across
    # fields need explicit enum names, or the generator invents suffixed ones.
    "ENUM_NAME_OVERRIDES": {
        "BakingExperienceLevelEnum": "apps.users.constants.BakingExperienceLevel.choices",
        "RecipeDifficultyEnum": "apps.recipes.constants.Difficulty.choices",
        "CourseDifficultyEnum": "apps.courses.constants.CourseDifficulty.choices",
        "QuestionDifficultyEnum": "apps.questions.constants.QuestionDifficulty.choices",
        "GalleryPostStatusEnum": "apps.gallery.constants.GalleryPostStatus.choices",
        "ThreadStatusEnum": "apps.qa.constants.ThreadStatus.choices",
        "ThreadModerationStatusEnum": "apps.qa.constants.THREAD_MODERATION_CHOICES",
        # PreferredLanguage and AssistantLanguage share the th/en value set
        # on purpose (ADR 0020 §8)  name the users one explicitly.
        "PreferredLanguageEnum": "apps.users.constants.PreferredLanguage.choices",
        "SignalKindEnum": "apps.security.constants.SignalKind.choices",
        "ThreatLevelEnum": "apps.security.constants.ThreatLevel.choices",
        "ReviewStateEnum": "apps.security.constants.ReviewState.choices",
    },
}


# --------------------------------------------------------------------------
# Threat watching (ADR 0025)
# --------------------------------------------------------------------------
# Read back through `apps.security.config`, never directly, so a test can
# override one switch without knowing its env var name.

# Master switch for the server-side detectors. Off means the middleware
# passes every request straight through and records nothing.
SECURITY_WATCH_ENABLED = env_bool("SECURITY_WATCH_ENABLED", True)

# Whether an active block is enforced. Separate from watching on purpose:
# an operator may want to observe for a week before enforcing anything.
SECURITY_BLOCKING_ENABLED = env_bool("SECURITY_BLOCKING_ENABLED", True)

# Whether reaching `critical` blocks an address with no human involved.
# Default OFF  a heuristic block is an outage for whoever shares that
# address, and shared/NAT addresses are the norm on mobile networks.
SECURITY_AUTO_BLOCK = env_bool("SECURITY_AUTO_BLOCK", False)
SECURITY_AUTO_BLOCK_MINUTES = env_int("SECURITY_AUTO_BLOCK_MINUTES", 60)

# Never scored, never blocked. Put the operator's own address here before
# testing the honeypot, or the first test locks them out of the dashboard
# that would let them undo it.
SECURITY_TRUSTED_IPS = env_list("SECURITY_TRUSTED_IPS", ["127.0.0.1", "::1"])

# The browser guard, served to the frontend via `/api/v1/security/client-policy/`:
#   off    - ship nothing
#   detect - observe and report, never interfere
#   deter  - additionally intercept F12 / Ctrl+Shift+I / Ctrl+U / right-click
# Devtools CANNOT actually be prevented from a web page (ADR 0025); `deter`
# is a speed bump plus a signal, and is deliberately not the default.
SECURITY_CLIENT_GUARD_MODE = env("SECURITY_CLIENT_GUARD_MODE", "detect")

# Leave signed-in visitors alone. The people most likely to open devtools
# here are staff and the most engaged learners.
SECURITY_GUARD_EXEMPT_AUTHENTICATED = env_bool(
    "SECURITY_GUARD_EXEMPT_AUTHENTICATED", True
)

# Whether the public ingest endpoint accepts browser-reported signals.
SECURITY_CLIENT_REPORTS_ENABLED = env_bool("SECURITY_CLIENT_REPORTS_ENABLED", True)

# Shared secret letting the Next.js edge forward a visitor's real address
# for trap hits it saw and Django did not. Empty disables forwarding.
SECURITY_INGEST_SECRET = env("SECURITY_INGEST_SECRET", "")


# --------------------------------------------------------------------------
# Frontend (Next.js) integration
# --------------------------------------------------------------------------
# Distinct from SITE_BASE_URL, which is Django's own origin. Verification and
# password-reset links must land on the frontend, never on Django.
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", "http://localhost:3000")
FRONTEND_PASSWORD_RESET_PATH = env("FRONTEND_PASSWORD_RESET_PATH", "/reset-password")
FRONTEND_EMAIL_VERIFY_PATH = env("FRONTEND_EMAIL_VERIFY_PATH", "/verify-email")

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", ["http://localhost:3000"])
# Required for cookie-based auth. Never combine with CORS_ALLOW_ALL_ORIGINS.
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", ["http://localhost:3000"])


# --------------------------------------------------------------------------
# Sessions & CSRF cookies
# --------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 14)
# Left False on purpose: "remember me" sets the expiry explicitly per login.
# Flipping this globally would invert the meaning of `set_expiry(None)`.
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# The frontend must READ this cookie to echo it in the X-CSRFToken header, so
# it cannot be HttpOnly. Double-submit tokens must be secret from *other*
# origins, not from our own JavaScript.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"


# --------------------------------------------------------------------------
# Token lifetimes (stateless auth tokens  see docs/adr/0006)
# --------------------------------------------------------------------------
# Read by Django's PasswordResetTokenGenerator directly.
PASSWORD_RESET_TIMEOUT = env_int("PASSWORD_RESET_TIMEOUT", 60 * 60)
# Read by EmailVerificationTokenGenerator (which overrides check_token).
EMAIL_VERIFICATION_TIMEOUT = env_int("EMAIL_VERIFICATION_TIMEOUT", 60 * 60 * 24 * 7)

# When True, unverified users cannot sign in at all. When False (default) they
# may sign in but verified-only areas remain gated by permissions.
REQUIRE_VERIFIED_EMAIL_TO_LOGIN = env_bool("REQUIRE_VERIFIED_EMAIL_TO_LOGIN", False)


# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------
# Static & media
# --------------------------------------------------------------------------
# STATICFILES_DIRS is intentionally absent: the project ships no static assets.
# staticfiles remains enabled because Django admin serves its own CSS/JS.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# `infrastructure.storage.get_media_storage` resolves this alias at field-init
# time, so swapping local disk for S3 never touches a migration  and renaming
# the alias itself needs none either, because model fields store the callable
# rather than the resolved backend.
MEDIA_STORAGE_ALIAS = "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "media": {
        "BACKEND": "infrastructure.storage.local_storage.LocalMediaStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# --------------------------------------------------------------------------
# Cache (used for auth rate limiting)
# --------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "kawaiibake-default",
    }
}


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@kawaiibake.local")
SITE_NAME = env("SITE_NAME", "KawaiiBake")
SITE_BASE_URL = env("SITE_BASE_URL", "http://localhost:8000")


# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE


# --------------------------------------------------------------------------
# AI assistant
# --------------------------------------------------------------------------
# Which backend answers, resolved by name through `ai.factory`. The default
# is the deterministic offline mock  local development and CI need no API
# key. Set AI_PROVIDER=openai plus OPENAI_API_KEY to go live; base URL is
# overridable for OpenAI-compatible local runtimes (Ollama, vLLM).
AI_PROVIDER = env("AI_PROVIDER", "mock")
AI_OPENAI_API_KEY = env("OPENAI_API_KEY")
AI_OPENAI_MODEL = env("AI_OPENAI_MODEL", "gpt-4o-mini")
AI_OPENAI_BASE_URL = env("AI_OPENAI_BASE_URL", "https://api.openai.com/v1")


# --------------------------------------------------------------------------
# Rate limiting (auth endpoints)
# --------------------------------------------------------------------------
LOGIN_RATE_LIMIT_ATTEMPTS = env_int("LOGIN_RATE_LIMIT_ATTEMPTS", 10)
LOGIN_RATE_LIMIT_WINDOW = env_int("LOGIN_RATE_LIMIT_WINDOW", 15 * 60)
PASSWORD_RESET_RATE_LIMIT_ATTEMPTS = env_int("PASSWORD_RESET_RATE_LIMIT_ATTEMPTS", 5)
PASSWORD_RESET_RATE_LIMIT_WINDOW = env_int("PASSWORD_RESET_RATE_LIMIT_WINDOW", 60 * 60)
REGISTRATION_RATE_LIMIT_ATTEMPTS = env_int("REGISTRATION_RATE_LIMIT_ATTEMPTS", 10)
REGISTRATION_RATE_LIMIT_WINDOW = env_int("REGISTRATION_RATE_LIMIT_WINDOW", 60 * 60)
# Live "is this handle free?" checks are debounced client-side, but the limit
# is what actually stops bulk username enumeration.
USERNAME_CHECK_RATE_LIMIT_ATTEMPTS = env_int("USERNAME_CHECK_RATE_LIMIT_ATTEMPTS", 30)
USERNAME_CHECK_RATE_LIMIT_WINDOW = env_int("USERNAME_CHECK_RATE_LIMIT_WINDOW", 60)
# Assistant sends cost real provider money, so they are throttled per user.
ASSISTANT_MESSAGE_RATE_LIMIT_ATTEMPTS = env_int(
    "ASSISTANT_MESSAGE_RATE_LIMIT_ATTEMPTS", 30
)
ASSISTANT_MESSAGE_RATE_LIMIT_WINDOW = env_int(
    "ASSISTANT_MESSAGE_RATE_LIMIT_WINDOW", 5 * 60
)


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
from infrastructure.logging.config import build_logging_config  # noqa: E402

LOGGING = build_logging_config(debug=DEBUG)
