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
    path("health/", health),
]

urlpatterns = [path("api/v1/", include(api))]

if settings.DEBUG:
    urlpatterns += [path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"), path("django-admin/", admin.site.urls)]
