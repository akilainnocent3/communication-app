from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from modules.audit.services import record

from ..models import Draft, EmailTemplate, OutgoingAttachment, ScheduledEmail
from ..services import access, send
from ..services.sanitize import sanitize_compose_html
from .permissions import CanUseMail
from .serializers import (
    ComposeSerializer,
    DraftSerializer,
    DraftWriteSerializer,
    QueuedSerializer,
    RescheduleSerializer,
    TemplateSerializer,
    UploadedSerializer,
    UploadSerializer,
)

BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".scr", ".js", ".vbs", ".msi", ".jar", ".ps1"}  # Gmail blocks these too


class UploadView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]
    parser_classes = [MultiPartParser]

    @extend_schema(request={"multipart/form-data": UploadSerializer}, responses={201: UploadedSerializer}, operation_id="mail_uploads_create")
    def post(self, request):
        data = UploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        mailbox = access.get_mailbox(request.user, data.validated_data["mailbox"], access.SEND)
        upload = data.validated_data["file"]
        name = (upload.name or "attachment").replace("\\", "_").replace("/", "_")[:255]
        if any(name.lower().endswith(ext) for ext in BLOCKED_EXTENSIONS):
            raise ApiError("blocked_file", "This file type is blocked for security reasons. Zip it or share a link instead.")
        if upload.size > settings.MAIL_MAX_ATTACHMENT_BYTES:
            raise ApiError("file_too_large", "This file is larger than 25 MB. Share it with a link instead.")
        item = OutgoingAttachment.objects.create(
            mailbox=mailbox, uploaded_by=request.user, filename=name, content_type=upload.content_type or "application/octet-stream", size=upload.size, content=upload.read(),
        )
        OutgoingAttachment.objects.filter(created_at__lt=timezone.now() - timedelta(days=7)).delete()
        return Response({"id": item.pk, "filename": item.filename, "content_type": item.content_type, "size": item.size}, status=status.HTTP_201_CREATED)


class UploadDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses={204: None}, operation_id="mail_uploads_destroy")
    def delete(self, request, pk):
        OutgoingAttachment.objects.filter(pk=pk, uploaded_by=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=ComposeSerializer, responses={202: QueuedSerializer}, operation_id="mail_send")
    def post(self, request):
        data = ComposeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = send.queue_send(request.user, data.validated_data, request=request)
        return Response(QueuedSerializer(item).data, status=status.HTTP_202_ACCEPTED)


class CancelSendView(APIView):
    """Undo send (or cancel a scheduled send). Returns what was cancelled so the UI can reopen it."""

    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT}, operation_id="mail_send_cancel")
    def post(self, request, pk):
        payload = send.cancel(request.user, pk, request=request)
        return Response({k: payload.get(k) for k in ("mailbox", "to", "cc", "bcc", "subject", "html", "mode", "in_reply_to_message", "attachment_ids", "draft_id")} | {"send_as": payload.get("from", {}).get("email")})


class ScheduledListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("mailbox", str)], responses=QueuedSerializer(many=True), operation_id="mail_scheduled_list")
    def get(self, request):
        mailboxes = access.accessible_mailboxes(request.user)
        mailbox = request.query_params.get("mailbox")
        if mailbox and mailbox != "all":
            mailboxes = mailboxes.filter(pk=access.get_mailbox(request.user, mailbox).pk)
        rows = ScheduledEmail.objects.filter(mailbox__in=mailboxes, kind=ScheduledEmail.SCHEDULED).filter(Q(status__in=[ScheduledEmail.PENDING, ScheduledEmail.SENDING]) | Q(status=ScheduledEmail.FAILED))
        return Response(QueuedSerializer(rows.order_by("send_at")[:200], many=True).data)


class ScheduledDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    def _item(self, request, pk) -> ScheduledEmail:
        item = ScheduledEmail.objects.filter(pk=pk, mailbox__in=access.accessible_mailboxes(request.user, access.SEND)).first()
        if not item:
            raise ApiError("not_found", "This scheduled message was not found.", status.HTTP_404_NOT_FOUND)
        return item

    @extend_schema(request=RescheduleSerializer, responses=QueuedSerializer, operation_id="mail_scheduled_update")
    def patch(self, request, pk):
        item = self._item(request, pk)
        data = RescheduleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if item.status not in (ScheduledEmail.PENDING, ScheduledEmail.FAILED):
            raise ApiError("already_sent", "This message has already been sent.", status.HTTP_409_CONFLICT)
        if data.validated_data["send_at"] <= timezone.now():
            raise ApiError("validation_error", "Pick a time in the future.")
        item.send_at, item.status, item.error = data.validated_data["send_at"], ScheduledEmail.PENDING, ""
        item.save(update_fields=["send_at", "status", "error"])
        record("mail.schedule_update", request=request, mailbox=item.mailbox, target_type="scheduled", target_id=item.pk, metadata={"send_at": item.send_at.isoformat()})
        return Response(QueuedSerializer(item).data)

    @extend_schema(responses={204: None}, operation_id="mail_scheduled_destroy")
    def delete(self, request, pk):
        item = self._item(request, pk)
        if item.status == ScheduledEmail.FAILED:
            item.status = ScheduledEmail.CANCELLED
            item.save(update_fields=["status"])
        else:
            send.cancel(request.user, item.pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DraftListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("mailbox", str)], responses=DraftSerializer(many=True), operation_id="mail_drafts_list")
    def get(self, request):
        mailboxes = access.accessible_mailboxes(request.user)
        mailbox = request.query_params.get("mailbox")
        if mailbox and mailbox != "all":
            mailboxes = mailboxes.filter(pk=access.get_mailbox(request.user, mailbox).pk)
        return Response(DraftSerializer(Draft.objects.filter(mailbox__in=mailboxes).order_by("-updated_at")[:200], many=True).data)

    @extend_schema(request=DraftWriteSerializer, responses={201: DraftSerializer}, operation_id="mail_drafts_create")
    def post(self, request):
        data = DraftWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        draft = send.save_draft(request.user, data.validated_data)
        return Response(DraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class DraftDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    def _draft(self, request, pk) -> Draft:
        draft = Draft.objects.filter(pk=pk, mailbox__in=access.accessible_mailboxes(request.user)).select_related("mailbox").first()
        if not draft:
            raise ApiError("not_found", "This draft was not found. It may have been sent or deleted.", status.HTTP_404_NOT_FOUND)
        return draft

    @extend_schema(responses=DraftSerializer, operation_id="mail_drafts_retrieve")
    def get(self, request, pk):
        return Response(DraftSerializer(self._draft(request, pk)).data)

    @extend_schema(request=DraftWriteSerializer, responses=DraftSerializer, operation_id="mail_drafts_update")
    def patch(self, request, pk):
        draft = self._draft(request, pk)
        data = DraftWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(DraftSerializer(send.save_draft(request.user, data.validated_data, draft)).data)

    @extend_schema(responses={204: None}, operation_id="mail_drafts_destroy")
    def delete(self, request, pk):
        send.delete_draft(request.user, self._draft(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TemplateListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("mailbox", int)], responses=TemplateSerializer(many=True), operation_id="mail_templates_list")
    def get(self, request):
        mailboxes = access.accessible_mailboxes(request.user)
        qs = EmailTemplate.objects.filter(Q(mailbox__isnull=True) | Q(mailbox__in=mailboxes))
        if request.query_params.get("mailbox"):
            qs = qs.filter(Q(mailbox__isnull=True) | Q(mailbox_id=request.query_params["mailbox"]))
        return Response(TemplateSerializer(qs, many=True).data)

    @extend_schema(request=TemplateSerializer, responses={201: TemplateSerializer}, operation_id="mail_templates_create")
    def post(self, request):
        data = TemplateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        mailbox = data.validated_data.get("mailbox")
        if mailbox:
            access.get_mailbox(request.user, mailbox.pk, access.SEND)
        template = data.save(created_by=request.user, body_html=sanitize_compose_html(data.validated_data["body_html"]))
        return Response(TemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class TemplateDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    def _template(self, request, pk) -> EmailTemplate:
        template = EmailTemplate.objects.filter(Q(mailbox__isnull=True) | Q(mailbox__in=access.accessible_mailboxes(request.user)), pk=pk).first()
        if not template:
            raise ApiError("not_found", "This template was not found.", status.HTTP_404_NOT_FOUND)
        if template.created_by_id != request.user.pk and not access.is_mail_admin(request.user):
            raise ApiError("permission_denied", "Only the author or an admin can change this template.", status.HTTP_403_FORBIDDEN)
        return template

    @extend_schema(request=TemplateSerializer, responses=TemplateSerializer, operation_id="mail_templates_update")
    def patch(self, request, pk):
        template = self._template(request, pk)
        data = TemplateSerializer(template, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        extra = {"body_html": sanitize_compose_html(data.validated_data["body_html"])} if "body_html" in data.validated_data else {}
        return Response(TemplateSerializer(data.save(**extra)).data)

    @extend_schema(responses={204: None}, operation_id="mail_templates_destroy")
    def delete(self, request, pk):
        self._template(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
