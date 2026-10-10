from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Group, PermissionsMixin
from django.db import models
from django.utils import timezone as dj_timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)


class Role(models.Model):
    """A named bundle of permissions. Backed by a Django Group so `user.has_perm` just works."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OFFICE_MANAGER = "office_manager"
    VIEWER = "viewer"

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    rank = models.PositiveSmallIntegerField(default=100, help_text="Lower is more powerful.")
    group = models.OneToOneField(Group, on_delete=models.PROTECT, related_name="role")
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["rank", "name"]
        permissions = [("manage_users", "Manage users, roles and offices")]

    def __str__(self):
        return self.name


class Office(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40, unique=True)
    colour = models.CharField(max_length=9, default="#3758f9")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def default_preferences():
    return {
        "shortcuts": True,
        "density": "comfortable",
        "reading_pane": "right",
        "swipe_right": "archive",
        "swipe_left": "trash",
        "undo_send_seconds": 10,
    }


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    office = models.ForeignKey(Office, null=True, blank=True, on_delete=models.SET_NULL, related_name="staff")
    timezone = models.CharField(max_length=64, default="Africa/Dar_es_Salaam")
    preferences = models.JSONField(default=default_preferences, blank=True)
    totp_secret = models.TextField(blank=True, help_text="Encrypted TOTP secret.")
    totp_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=dj_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["full_name", "email"]

    def __str__(self):
        return self.email

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]

    def get_full_name(self):
        return self.display_name

    def get_short_name(self):
        return self.display_name

    @property
    def role_slug(self) -> str:
        if self.is_superuser:
            return Role.SUPER_ADMIN
        return self.role.slug if self.role_id else ""
