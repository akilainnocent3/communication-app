from django.contrib import admin

from .models import Office, Role, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "role", "office", "is_active")
    search_fields = ("email", "full_name")
    exclude = ("password", "totp_secret")


admin.site.register(Role)
admin.site.register(Office)
