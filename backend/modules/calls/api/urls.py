"""Admin routes (session + CSRF), mounted at /api/v1/. Phone routes live in device_urls.py."""

from django.urls import path

from . import views

urlpatterns = [
    path("calls/calls/", views.CallListView.as_view()),
    path("calls/calls/<int:pk>/", views.CallDetailView.as_view()),
    path("calls/calls/<int:pk>/annotations/", views.CallAnnotationListView.as_view()),
    path("calls/annotations/<int:pk>/", views.CallAnnotationDetailView.as_view()),
    path("calls/callbacks/", views.CallbackListView.as_view()),
    path("calls/callbacks/bulk/", views.CallbackBulkView.as_view()),
    path("calls/callbacks/<int:pk>/", views.CallbackDetailView.as_view()),
    path("calls/callbacks/<int:pk>/cancel/", views.CallbackCancelView.as_view()),
    path("calls/live/", views.LiveView.as_view()),
    path("calls/stats/", views.StatsView.as_view()),
    path("calls/badges/", views.BadgesView.as_view()),
    path("calls/export/", views.ExportView.as_view()),
    path("calls/enrollments/", views.CallEnrollmentListView.as_view()),
    path("calls/enrollments/<int:pk>/", views.CallEnrollmentDetailView.as_view()),
    path("calls/enrollments/<int:pk>/revoke/", views.CallEnrollmentRevokeView.as_view()),
    path("calls/enrollments/<int:pk>/short-code/", views.CallEnrollmentShortCodeView.as_view()),
    path("calls/devices/", views.CallDeviceListView.as_view()),
    path("calls/devices/<uuid:pk>/enable/", views.CallDeviceEnableView.as_view()),
    path("calls/devices/<uuid:pk>/access/", views.CallDeviceAccessView.as_view()),
    path("calls/devices/<uuid:pk>/simulator/", views.CallSimulatorView.as_view()),
    path("calls/customers/", views.CustomerListView.as_view()),
    path("calls/customers/merge/", views.CustomerMergeView.as_view()),
    path("calls/customers/<int:pk>/", views.CustomerDetailView.as_view()),
    path("calls/customers/<int:pk>/timeline/", views.CustomerTimelineView.as_view()),
    path("calls/outcomes/", views.OutcomeListView.as_view()),
    path("calls/outcomes/<int:pk>/", views.OutcomeDetailView.as_view()),
    path("calls/settings/", views.SettingsView.as_view()),
    path("calls/office-hours/", views.OfficeHoursListView.as_view()),
    path("calls/office-hours/<int:office_id>/", views.OfficeHoursDetailView.as_view()),
    path("calls/tariffs/", views.TariffListView.as_view()),
    path("calls/tariffs/<int:pk>/", views.TariffDetailView.as_view()),
]
