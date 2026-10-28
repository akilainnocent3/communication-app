"""Calls routes for phones, mounted at /api/v1/device/ next to the devices and SMS routes."""

from django.urls import path

from . import device

urlpatterns = [
    path("calls/config/", device.CallsConfigView.as_view()),
    path("calls/callbacks/", device.CallbacksView.as_view()),
    path("calls/directory/", device.DirectoryView.as_view()),
]
