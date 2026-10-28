"""Phone-facing routes, mounted at /api/v1/device/. Nginx proxies this prefix straight to Django."""

from django.urls import path

from . import views

urlpatterns = [
    path("enroll/info/", views.EnrollInfoView.as_view()),
    path("enroll/resolve/", views.EnrollResolveView.as_view()),
    path("enroll/", views.EnrollView.as_view()),
    path("auth/token/", views.TokenView.as_view()),
    path("heartbeat/", views.HeartbeatView.as_view()),
    path("push-token/", views.PushTokenView.as_view()),
    path("sync/events/", views.SyncEventsView.as_view()),
]
