"""SMS routes for phones, mounted at /api/v1/device/ next to modules.devices.api.urls."""

from django.urls import path

from . import device

urlpatterns = [
    path("config/", device.ConfigView.as_view()),
    path("sync/media/", device.MediaUploadView.as_view()),
    path("outbox/claim/", device.ClaimView.as_view()),
    path("outbox/status/", device.StatusView.as_view()),
]
