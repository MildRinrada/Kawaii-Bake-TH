"""Logging configuration builder.

Keeps ``LOGGING`` out of the settings modules so the shape of the config is
testable and identical across environments.
"""

from __future__ import annotations

from typing import Any


def build_logging_config(*, debug: bool) -> dict[str, Any]:
    """Build the Django ``LOGGING`` dictionary.

    Args:
        debug: Whether the project is running in debug mode.

    Returns:
        A ``logging.config.dictConfig``-compatible dictionary.
    """
    level = "DEBUG" if debug else "INFO"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{asctime} {levelname} {name} {message}",
                "style": "{",
            },
            "simple": {"format": "{levelname} {message}", "style": "{"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple" if debug else "verbose",
            },
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "django": {"handlers": ["console"], "level": level, "propagate": False},
            # Security-relevant auth events (login success/failure, resets).
            "kawaiibake.security": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
