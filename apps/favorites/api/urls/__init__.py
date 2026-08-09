"""Favorites urlconfs.

There is no ``/api/v1/favorites/`` prefix: every route lives under the prefix
of what it decorates (recipes, courses, users) and is mounted there by
config — the lessons precedent (ADR 0009).
"""
