from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """Append-only record of a security-relevant action. Never updated or deleted by the application."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=64, db_index=True)
    # Plain columns (no FK) so events outlive the mailbox and the audit app stays independent of mail.
    mailbox_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    mailbox_email = models.CharField(max_length=254, blank=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=128, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["mailbox_id", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError("Audit events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit events are append-only.")
