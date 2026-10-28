"""Customers: who the company talks to, by number. Numbers and names stay plaintext (lists, caller ID, analytics);
free-text notes are encrypted with the device-data key ring (common/devicecrypto.py)."""

from django.conf import settings
from django.db import models


class Customer(models.Model):
    key = models.CharField(max_length=64, unique=True, help_text="Address key: E.164, short-code digits or upper-cased sender ID.")
    number_e164 = models.CharField(max_length=32, blank=True, help_text="Set when the key is a real phone number.")
    raw_sender = models.CharField(max_length=64, blank=True, help_text="As first seen, for short codes and sender IDs.")
    display_name = models.CharField(max_length=120, blank=True)
    organisation = models.CharField(max_length=120, blank=True)
    tags = models.JSONField(default=list, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_customers")
    encrypted_notes = models.TextField(blank=True)
    # Caller ID: the name is sent to phones that have been in contact with this customer (CustomerDevice) or, with this
    # flag, to every Calls phone. Off by default: a name stays on the phones that already know the customer.
    caller_id_all_phones = models.BooleanField(default=False)
    auto_sms_opt_out = models.BooleanField(default=False, help_text="Never send this number the automatic missed-call SMS.")
    first_seen_sms = models.DateTimeField(null=True, blank=True)
    last_seen_sms = models.DateTimeField(null=True, blank=True)
    first_seen_call = models.DateTimeField(null=True, blank=True)
    last_seen_call = models.DateTimeField(null=True, blank=True)
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["display_name", "key"]
        permissions = [("manage_customers", "Edit, merge and delete directory entries")]
        indexes = [
            models.Index(fields=["display_name"], name="dir_customer_name"),
            models.Index(fields=["updated_at", "id"], name="dir_customer_delta"),
        ]

    def __str__(self):
        return self.display_name or self.key


class CustomerDevice(models.Model):
    """Which phones have been in contact with a customer (SMS or calls). Scopes caller ID and directory visibility."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="device_links")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="customer_links")
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["customer", "device"], name="uniq_customer_device")]
        indexes = [models.Index(fields=["device", "customer"], name="dir_link_device")]
