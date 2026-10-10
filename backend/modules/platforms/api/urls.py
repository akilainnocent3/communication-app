from django.urls import path

from .views import PlatformAdminView, PlatformListView

urlpatterns = [
    path("platforms/", PlatformListView.as_view()),
    path("settings/platforms/", PlatformAdminView.as_view()),
]
