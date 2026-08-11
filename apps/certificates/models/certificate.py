"""The certificate entity  an immutable issued record."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.certificates.constants import (
    COURSE_TITLE_MAX_LENGTH,
    STUDENT_NAME_MAX_LENGTH,
)
from apps.core.models.base import TimeStampedModel


class Certificate(TimeStampedModel):
    """One issued course certificate.

    **Immutable once issued**: ``certificate_number``, ``issued_at`` and the
    printable snapshot never change  a certificate is a record of a fact,
    and the repository exposes no update path for them. The only mutation
    ever allowed is the stamp-once ``revoked_at``; revoked certificates
    remain forever (the partial unique frees the (user, course) slot for a
    re-issue while history survives).

    The printable fields (``student_name``, ``course_title``,
    ``completed_at``) are **snapshots at issuance**  the ADR 0010 snapshot-
    completeness rule: what the paper says must not change when the course
    is renamed or the user changes handle, and the future PDF phase must
    read nothing mutable. The snapshot is also why ``course`` can be
    ``SET_NULL``: deleting a course must not delete anyone's earned
    certificate, and course deletion (an existing API) keeps working.

    ``verification_token`` is the only public lookup key. The human-facing
    ``certificate_number`` is sequential and therefore enumerable  it is
    printed on paper, never routed.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        related_name="certificates",
        null=True,
        blank=True,
    )
    certificate_number = models.CharField(max_length=20, unique=True)
    verification_token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )
    issued_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Revocation changes the evidentiary value of someone's credential,
    # so it must be attributable: who did it and why, frozen with the
    # stamp. SET_NULL - the record outlives the operator's account.
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="revoked_certificates",
        null=True,
        blank=True,
    )
    revoked_reason = models.CharField(max_length=200, blank=True)

    # Printable snapshot  what the certificate says, frozen at issuance.
    student_name = models.CharField(max_length=STUDENT_NAME_MAX_LENGTH)
    course_title = models.CharField(max_length=COURSE_TITLE_MAX_LENGTH)
    completed_at = models.DateTimeField()

    class Meta:
        verbose_name = "certificate"
        verbose_name_plural = "certificates"
        ordering = ("-issued_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "course"),
                condition=Q(revoked_at__isnull=True),
                name="certificates_one_active_per_course",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-issued_at"], name="cert_user_issued_idx"),
        ]

    def __str__(self) -> str:
        """Return the certificate description."""
        return f"{self.certificate_number} · user {self.user_id}"

    @property
    def is_revoked(self) -> bool:
        """Whether this certificate has been revoked."""
        return self.revoked_at is not None
