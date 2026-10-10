from django.urls import path

from .views import AuditExportView, AuditListView

urlpatterns = [
    path("audit/events/", AuditListView.as_view()),
    path("audit/events/export/", AuditExportView.as_view()),
]
