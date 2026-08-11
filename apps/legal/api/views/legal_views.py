"""Legal-document endpoints.

Reading is public  anyone deciding whether to register must be able to
read what they are agreeing to. Writing is staff-only.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.legal.api.serializers import (
    LegalDocumentSerializer,
    LegalDocumentSummarySerializer,
    LegalDocumentUpdateSerializer,
)
from apps.legal.exceptions import LegalDocumentNotFoundError
from apps.legal.selectors import legal_selector
from apps.legal.services import legal_service


class LegalDocumentListView(ServiceAPIView):
    """List every legal document (without bodies)."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        responses=LegalDocumentSummarySerializer(many=True), tags=["legal"]
    )
    def get(self, request: Request) -> Response:
        """Return all documents' metadata."""
        documents = legal_selector.list_documents()
        serializer = LegalDocumentSummarySerializer(documents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LegalDocumentDetailView(ServiceAPIView):
    """Read or edit one legal document."""

    permission_classes = (AllowAny,)

    def get_permissions(self):  # noqa: ANN201 - DRF signature
        """Public read, staff write."""
        if self.request.method == "PATCH":
            return [IsAdminUser()]
        return [AllowAny()]

    @extend_schema(responses=LegalDocumentSerializer, tags=["legal"])
    def get(self, request: Request, kind: str) -> Response:
        """Return one document with its full text."""
        document = legal_selector.get_document(kind=kind)
        if document is None:
            raise LegalDocumentNotFoundError
        return Response(
            LegalDocumentSerializer(document).data, status=status.HTTP_200_OK
        )

    @extend_schema(
        request=LegalDocumentUpdateSerializer,
        responses=LegalDocumentSerializer,
        tags=["legal"],
    )
    def patch(self, request: Request, kind: str) -> Response:
        """Edit the document; every content change bumps its version."""
        serializer = LegalDocumentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document = legal_service.update_document(
            kind=kind,
            title=serializer.validated_data.get("title"),
            body=serializer.validated_data.get("body"),
            actor_id=request.user.id,
        )
        return Response(
            LegalDocumentSerializer(document).data, status=status.HTTP_200_OK
        )
