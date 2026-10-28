from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView


def health(request):
    return JsonResponse({"ok": True})


api = [
    path("", include("modules.identity.api.urls")),
    path("", include("modules.platforms.api.urls")),
    path("", include("modules.audit.api.urls")),
    path("", include("modules.mail.api.urls")),
    path("", include("modules.sms.api.urls")),
    path("", include("modules.calls.api.urls")),
    path("health/", health),
]

# Phone-facing API: device-token auth only, never session auth. Nginx sends /api/v1/device/ straight to Django.
device_api = [
    path("", include("modules.devices.api.urls")),
    path("", include("modules.sms.api.device_urls")),
    path("", include("modules.calls.api.device_urls")),
]

urlpatterns = [path("api/v1/device/", include(device_api)), path("api/v1/", include(api))]

if settings.DEBUG:
    urlpatterns += [path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"), path("django-admin/", admin.site.urls)]
