from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("auth/preferences/", views.PreferencesView.as_view()),
    path("auth/totp/setup/", views.TotpSetupView.as_view()),
    path("auth/totp/enable/", views.TotpEnableView.as_view()),
    path("auth/totp/disable/", views.TotpDisableView.as_view()),
    path("settings/users/", views.UserListView.as_view()),
    path("settings/users/<int:pk>/", views.UserDetailView.as_view()),
    path("settings/roles/", views.RoleListView.as_view()),
    path("settings/roles/<int:pk>/", views.RoleDetailView.as_view()),
    path("settings/permissions/", views.PermissionCatalogView.as_view()),
    path("settings/offices/", views.OfficeListView.as_view()),
    path("settings/offices/<int:pk>/", views.OfficeDetailView.as_view()),
]
