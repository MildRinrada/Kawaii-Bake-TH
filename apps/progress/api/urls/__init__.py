"""Progress urlconfs.

There is no ``/api/v1/progress/`` prefix: every route lives under the prefix
of what it decorates (lessons, courses, me) and is mounted there by config -
the lessons precedent (ADR 0009).
"""
