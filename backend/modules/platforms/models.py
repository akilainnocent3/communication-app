from django.db import models


class Platform(models.Model):
    """Enablement and order of a registered platform, editable by a super admin."""

    key = models.SlugField(max_length=40, unique=True)
    is_enabled = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "key"]
        permissions = [("manage_platforms", "Enable, disable and reorder platforms")]

    def __str__(self):
        return self.key
