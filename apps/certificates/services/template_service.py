"""Staff curation of per-course certificate templates (ADR 0029).

Draft saves are the designer's autosave — cheap, frequent, validated.
Publishing is the deliberate act that freezes the draft as the course's
production design. A course with no row (or a deleted row) uses
``DEFAULT_DESIGN``, so the platform always has a printable answer.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import QuerySet

from apps.certificates.exceptions import CertificateCourseNotFoundError
from apps.certificates.models import CertificateTemplate
from apps.certificates.repositories import certificate_repository
from apps.certificates.validators.template_validator import validate_design
from apps.courses.selectors import course_selector

logger = logging.getLogger(__name__)

# The built-in KawaiiBake design: an A4-landscape scene the designer
# seeds new drafts from. Kept server-side so "reset to default" and a
# fresh course agree on what default means.
DEFAULT_DESIGN: dict[str, Any] = {
    "size": {"width": 1123, "height": 794},
    "background": "#fffaf3",
    "elements": [
        {
            "id": "border",
            "kind": "box",
            "name": "กรอบตกแต่ง",
            "x": 28, "y": 28, "w": 1067, "h": 738,
            "rotation": 0, "opacity": 1, "z": 0,
            "locked": False, "hidden": False,
            "style": {
                "background": "transparent",
                "borderWidth": 3,
                "borderColor": "#e7b8c4",
                "borderRadius": 18,
            },
        },
        {
            "id": "brand",
            "kind": "text",
            "name": "ชื่อเว็บไซต์",
            "text": "KawaiiBake",
            "x": 411, "y": 70, "w": 300, "h": 48,
            "rotation": 0, "opacity": 1, "z": 1,
            "locked": False, "hidden": False,
            "style": {
                "fontFamily": "display",
                "fontSize": 34,
                "fontWeight": 600,
                "align": "center",
                "color": "#a24c68",
            },
        },
        {
            "id": "title",
            "kind": "text",
            "name": "หัวเรื่องใบประกาศ",
            "text": "ประกาศนียบัตรฉบับนี้มอบให้เพื่อรับรองว่า",
            "x": 261, "y": 200, "w": 600, "h": 36,
            "rotation": 0, "opacity": 1, "z": 2,
            "locked": False, "hidden": False,
            "style": {"fontSize": 20, "align": "center", "color": "#6b5560"},
        },
        {
            "id": "recipient",
            "kind": "field",
            "name": "ชื่อผู้รับ",
            "field": "recipient_full_name",
            "x": 211, "y": 260, "w": 700, "h": 72,
            "rotation": 0, "opacity": 1, "z": 3,
            "locked": False, "hidden": False,
            "style": {
                "fontFamily": "display",
                "fontSize": 48,
                "fontWeight": 600,
                "align": "center",
                "color": "#3d2c33",
            },
        },
        {
            "id": "completed-line",
            "kind": "text",
            "name": "ข้อความรับรอง",
            "text": "ได้เรียนจบหลักสูตรอย่างสมบูรณ์",
            "x": 311, "y": 356, "w": 500, "h": 32,
            "rotation": 0, "opacity": 1, "z": 4,
            "locked": False, "hidden": False,
            "style": {"fontSize": 18, "align": "center", "color": "#6b5560"},
        },
        {
            "id": "course",
            "kind": "field",
            "name": "ชื่อคอร์ส",
            "field": "course_name",
            "x": 211, "y": 400, "w": 700, "h": 48,
            "rotation": 0, "opacity": 1, "z": 5,
            "locked": False, "hidden": False,
            "style": {
                "fontFamily": "display",
                "fontSize": 30,
                "fontWeight": 600,
                "align": "center",
                "color": "#a24c68",
            },
        },
        {
            "id": "date",
            "kind": "field",
            "name": "วันที่เรียนจบ",
            "field": "completion_date",
            "x": 411, "y": 470, "w": 300, "h": 28,
            "rotation": 0, "opacity": 1, "z": 6,
            "locked": False, "hidden": False,
            "style": {"fontSize": 16, "align": "center", "color": "#6b5560"},
        },
        {
            "id": "certificate-id",
            "kind": "field",
            "name": "เลขที่ใบประกาศ",
            "field": "certificate_id",
            "x": 60, "y": 720, "w": 260, "h": 24,
            "rotation": 0, "opacity": 1, "z": 7,
            "locked": False, "hidden": False,
            "style": {"fontSize": 13, "align": "left", "color": "#9b8b92"},
        },
        {
            "id": "signature-1",
            "kind": "signature",
            "name": "ลายเซ็นผู้สอน",
            "x": 700, "y": 590, "w": 280, "h": 110,
            "rotation": 0, "opacity": 1, "z": 8,
            "locked": False, "hidden": False,
            "signature": {
                "name": "ผู้สอนประจำคอร์ส",
                "title": "Instructor",
                "organization": "KawaiiBake",
                "image": "",
            },
            "style": {"fontSize": 14, "align": "center", "color": "#3d2c33"},
        },
    ],
}


def list_templates() -> QuerySet[CertificateTemplate]:
    """Every existing template row with its course, for the workspace.

    Returns:
        A lazy queryset, most recently edited first.
    """
    return CertificateTemplate.objects.select_related(
        "course", "updated_by"
    )


def _resolve_course(slug: str):
    course = course_selector.get_course_ref(
        slug=slug, viewer_id=None, viewer_is_staff=True
    )
    if course is None:
        raise CertificateCourseNotFoundError
    return course


def get_template(*, course_slug: str) -> CertificateTemplate:
    """Fetch (or seed from default) the template of one course.

    Args:
        course_slug: The course slug.

    Returns:
        The template row, draft seeded with :data:`DEFAULT_DESIGN` when
        the course never had one.

    Raises:
        CertificateCourseNotFoundError: If the course does not exist.
    """
    course = _resolve_course(course_slug)
    return certificate_repository.get_or_create_template(
        course_id=course.id, default_design=DEFAULT_DESIGN
    )


def save_draft(
    *, course_slug: str, design: Any, actor_id: int
) -> CertificateTemplate:
    """Validate and store the designer's working copy.

    Args:
        course_slug: The course slug.
        design: The submitted design document.
        actor_id: The staff member editing.

    Returns:
        The updated template.

    Raises:
        CertificateCourseNotFoundError: If the course does not exist.
        django.core.exceptions.ValidationError: If the document breaks
            the scene rules (bounds, caps, the 3-signature ceiling).
    """
    validate_design(design)
    template = get_template(course_slug=course_slug)
    return certificate_repository.save_draft(
        template=template, design=design, actor_id=actor_id
    )


def publish(*, course_slug: str, actor_id: int) -> CertificateTemplate:
    """Freeze the current draft as the course's production design.

    Args:
        course_slug: The course slug.
        actor_id: The staff member publishing.

    Returns:
        The updated template.
    """
    template = get_template(course_slug=course_slug)
    validate_design(template.draft_design)
    template = certificate_repository.publish_template(
        template=template, actor_id=actor_id
    )
    logger.info(
        "certificate template published",
        extra={"course_id": template.course_id, "actor_id": actor_id},
    )
    return template


def reset_draft(*, course_slug: str, actor_id: int) -> CertificateTemplate:
    """Discard the draft: back to the published design, else the default.

    Args:
        course_slug: The course slug.
        actor_id: The staff member resetting.

    Returns:
        The updated template.
    """
    template = get_template(course_slug=course_slug)
    design = template.published_design or DEFAULT_DESIGN
    return certificate_repository.save_draft(
        template=template, design=design, actor_id=actor_id
    )


def remove_template(*, course_slug: str, actor_id: int) -> None:
    """Delete the row — the course goes back to the built-in default.

    Args:
        course_slug: The course slug.
        actor_id: The staff member resetting, for the audit log.
    """
    template = get_template(course_slug=course_slug)
    certificate_repository.delete_template(template=template)
    logger.info(
        "certificate template removed",
        extra={"course_slug": course_slug, "actor_id": actor_id},
    )
