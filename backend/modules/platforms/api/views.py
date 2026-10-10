from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from common.permissions import IsSuperAdmin
from modules.audit.services import record

from ..models import Platform
from ..services import platforms_for, sync_platform_rows


class PlatformSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    permission = serializers.CharField()
    is_enabled = serializers.BooleanField()
    order = serializers.IntegerField()


class PlatformUpdateItem(serializers.Serializer):
    key = serializers.CharField()
    is_enabled = serializers.BooleanField()
    order = serializers.IntegerField(min_value=0, max_value=1000)


class PlatformListView(APIView):
    @extend_schema(responses=PlatformSerializer(many=True), operation_id="platforms_list")
    def get(self, request):
        return Response(platforms_for(request.user))


class PlatformAdminView(APIView):
    """Settings → Platforms (super admin): every registered platform, including disabled ones."""

    permission_classes = [IsSuperAdmin]

    @extend_schema(responses=PlatformSerializer(many=True), operation_id="platforms_admin_list")
    def get(self, request):
        return Response(platforms_for(request.user, include_disabled=True))

    @extend_schema(request=PlatformUpdateItem(many=True), responses=PlatformSerializer(many=True), operation_id="platforms_admin_update")
    def put(self, request):
        items = PlatformUpdateItem(data=request.data, many=True)
        items.is_valid(raise_exception=True)
        sync_platform_rows()
        with transaction.atomic():
            for item in items.validated_data:
                updated = Platform.objects.filter(key=item["key"]).update(is_enabled=item["is_enabled"], order=item["order"])
                if not updated:
                    raise ApiError("unknown_platform", f"Unknown platform '{item['key']}'.")
        record("platforms.update", request=request, metadata={"platforms": items.validated_data})
        return Response(platforms_for(request.user, include_disabled=True))
