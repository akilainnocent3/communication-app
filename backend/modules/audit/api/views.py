import csv

from django.http import StreamingHttpResponse
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import decode_cursor, encode_cursor
from common.permissions import HasPerm

from ..models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ["id", "actor", "actor_email", "action", "mailbox_id", "mailbox_email", "target_type", "target_id", "ip", "user_agent", "metadata", "created_at"]


class AuditPageSerializer(serializers.Serializer):
    results = AuditEventSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


FILTERS = [
    OpenApiParameter("actor", int), OpenApiParameter("mailbox", int), OpenApiParameter("action", str),
    OpenApiParameter("from", str, description="YYYY-MM-DD"), OpenApiParameter("to", str, description="YYYY-MM-DD"),
    OpenApiParameter("cursor", str),
]


def filtered(params):
    qs = AuditEvent.objects.all()
    if params.get("actor"):
        qs = qs.filter(actor_id=params["actor"])
    if params.get("mailbox"):
        qs = qs.filter(mailbox_id=params["mailbox"])
    if params.get("action"):
        action = params["action"]
        qs = qs.filter(action__startswith=action[:-1]) if action.endswith("*") else qs.filter(action=action)
    if (start := parse_date(params.get("from") or "")):
        qs = qs.filter(created_at__date__gte=start)
    if (end := parse_date(params.get("to") or "")):
        qs = qs.filter(created_at__date__lte=end)
    return qs


class AuditListView(APIView):
    permission_classes = [IsAuthenticated, HasPerm.of("audit.view_auditevent")]

    @extend_schema(parameters=FILTERS, responses=AuditPageSerializer, operation_id="audit_events_list")
    def get(self, request):
        qs = filtered(request.query_params)
        cursor = decode_cursor(request.query_params.get("cursor"))
        if cursor and "id" in cursor:
            qs = qs.filter(id__lt=cursor["id"])
        rows = list(qs.order_by("-id")[:51])
        more = len(rows) > 50
        rows = rows[:50]
        return Response({"results": AuditEventSerializer(rows, many=True).data, "next_cursor": encode_cursor({"id": rows[-1].id}) if more else None})


class Echo:
    def write(self, value):
        return value


class AuditExportView(APIView):
    permission_classes = [IsAuthenticated, HasPerm.of("audit.view_auditevent")]

    @extend_schema(parameters=FILTERS[:-1], responses={(200, "text/csv"): str}, operation_id="audit_events_export")
    def get(self, request):
        from modules.audit.services import record

        record("audit.export", request=request, metadata={k: v for k, v in request.query_params.items()})
        writer = csv.writer(Echo())
        header = ["time", "actor", "action", "mailbox", "target_type", "target_id", "ip", "metadata"]

        def rows():
            yield writer.writerow(header)
            for event in filtered(request.query_params).order_by("-id").iterator(chunk_size=500):
                yield writer.writerow([
                    event.created_at.isoformat(), event.actor_email, event.action, event.mailbox_email,
                    event.target_type, event.target_id, event.ip or "", _safe(event.metadata),
                ])

        response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
        return response


def _safe(metadata) -> str:
    import json

    text = json.dumps(metadata, default=str, ensure_ascii=False)
    # Spreadsheet formula injection guard.
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text
