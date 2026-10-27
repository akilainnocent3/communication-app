"""Admin routes (session + CSRF), mounted at /api/v1/. Phone routes live in device_urls.py."""

from django.urls import path, re_path

from . import compose, conversations, devices

urlpatterns = [
    # Phones and enrollment
    path("sms/devices/", devices.DeviceListView.as_view()),
    path("sms/devices/<uuid:pk>/", devices.DeviceDetailView.as_view()),
    re_path(r"^sms/devices/(?P<pk>[0-9a-f-]{36})/(?P<action>suspend|resume|revoke)/$", devices.DeviceStatusView.as_view()),
    path("sms/devices/<uuid:pk>/resync/", devices.DeviceResyncView.as_view()),
    path("sms/devices/<uuid:pk>/heartbeats/", devices.DeviceHeartbeatsView.as_view()),
    path("sms/devices/<uuid:pk>/access/", devices.DeviceAccessView.as_view()),
    path("sms/devices/<uuid:pk>/simulator/", devices.SimulatorView.as_view()),
    path("sms/devices/<uuid:pk>/sims/<int:sim_id>/", devices.SimLineView.as_view()),
    path("sms/enrollments/", devices.EnrollmentListView.as_view()),
    path("sms/enrollments/<int:pk>/", devices.EnrollmentDetailView.as_view()),
    path("sms/enrollments/<int:pk>/revoke/", devices.EnrollmentRevokeView.as_view()),
    # Conversations and messages
    path("sms/conversations/", conversations.ConversationListView.as_view()),
    path("sms/conversations/actions/", conversations.ActionView.as_view()),
    path("sms/conversations/<int:pk>/", conversations.ConversationDetailView.as_view()),
    path("sms/conversations/<int:pk>/messages/", conversations.MessageListView.as_view()),
    path("sms/conversations/<int:pk>/notes/", conversations.NoteListView.as_view()),
    path("sms/conversations/<int:pk>/notes/<int:note_id>/", conversations.NoteDetailView.as_view()),
    path("sms/messages/<int:pk>/reveal/", conversations.RevealView.as_view()),
    path("sms/messages/<int:pk>/star/", conversations.StarView.as_view()),
    path("sms/messages/<int:pk>/media/<int:part_id>/", conversations.MediaView.as_view()),
    path("sms/messages/<int:pk>/cancel/", compose.CancelView.as_view()),
    path("sms/messages/<int:pk>/retry/", compose.RetryView.as_view()),
    path("sms/send/", compose.SendView.as_view()),
    path("sms/segments/", compose.SegmentsView.as_view()),
    path("sms/outbox/", compose.OutboxView.as_view()),
    # Contacts, tools, dashboard
    path("sms/contacts/", conversations.ContactListView.as_view()),
    path("sms/blocked/", conversations.BlockView.as_view()),
    path("sms/blocked/<int:pk>/", conversations.UnblockView.as_view()),
    path("sms/assignees/", conversations.AssigneeListView.as_view()),
    path("sms/stats/", conversations.StatsView.as_view()),
    path("sms/quick-replies/", compose.QuickReplyListView.as_view()),
    path("sms/quick-replies/<int:pk>/", compose.QuickReplyDetailView.as_view()),
    path("sms/rules/", compose.SensitiveRuleListView.as_view()),
    path("sms/rules/<int:pk>/", compose.SensitiveRuleDetailView.as_view()),
    path("sms/settings/", compose.SmsSettingsView.as_view()),
]
