"""Settings shared by every environment. Secrets come only from the environment (see .env.example)."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="") or "dev-only-insecure-key-change-me"
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000", "http://127.0.0.1:3000"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "modules.identity",
    "modules.audit",
    "modules.platforms",
    "modules.mail",
    "modules.devices",
    "modules.sms",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://cm:cm@127.0.0.1:5432/cm")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "identity.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = env("TIME_ZONE", default="Africa/Dar_es_Salaam")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sessions, CSRF, cookies --------------------------------------------------------------------------
SESSION_COOKIE_NAME = "cm_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 12)
SESSION_COOKIE_SECURE = env.bool("COOKIE_SECURE", default=False)
CSRF_COOKIE_NAME = "cm_csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_HTTPONLY = False

# --- Redis: broker + security store, and a separate evictable cache (common/stores.py, decision 59) ---------------
# REDIS_URL: Celery broker and the "security" cache (nonces, lockouts, rate limits, locks). Runs noeviction + AOF.
# REDIS_CACHE_URL: plain cache data that may be evicted (allkeys-lru). Empty = a separate DB on REDIS_URL's server
# (fine for development only: that server's noeviction policy then also applies to the cache).
REDIS_URL = env("REDIS_URL", default="")


def _cache_db(url: str) -> str:
    """DB 1 on the broker's server (development fallback when REDIS_CACHE_URL is empty)."""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    return urlunsplit(parts._replace(path="/1"))


REDIS_CACHE_URL = env("REDIS_CACHE_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_CACHE_URL or _cache_db(REDIS_URL)},
        "security": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL, "KEY_PREFIX": "sec"},
    }
else:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "default"},
        "security": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "security"},
    }

# --- DRF --------------------------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["common.auth.CsrfSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "common.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "public_connect": "60/min",
        # Phone-facing API (/api/v1/device/...): public enrollment and token minting per client IP, the rest per device.
        "device_enroll": "10/min",
        "device_short_code": "5/min",
        "device_short_code_hour": "20/hour",
        "device_auth": "30/min",
        "device": "300/min",
    },
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Communication Manager API",
    "DESCRIPTION": "Company admin platform for managing communication channels (Gmail first).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "MailboxStatusEnum": "modules.mail.models.MailboxStatus",
        "ProviderEnum": "modules.mail.models.Provider",
        "ConnectionSecurityEnum": [("ssl", "ssl"), ("starttls", "starttls")],
        "SwipeActionEnum": [("archive", "archive"), ("trash", "trash"), ("read", "read"), ("none", "none")],
        "UndoSendSecondsEnum": [(0, 0), (5, 5), (10, 10), (20, 20), (30, 30)],
        # Pinned so the SMS platform's own enums never rename the Gmail ones in the generated types.
        "ActionEnum": "modules.mail.services.actions.ACTIONS",
        "KindEnum": [("undo", "Undo window"), ("scheduled", "Scheduled")],
        "TypeEnum": [("system", "System"), ("user", "User")],
    },
}

# --- Celery -----------------------------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL or "memory://")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=not REDIS_URL)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {
    "mail-incremental-sync": {"task": "mail.sync_all_mailboxes", "schedule": timedelta(seconds=60)},
    "mail-dispatch-due-sends": {"task": "mail.dispatch_due_sends", "schedule": timedelta(seconds=5)},
    "mail-wake-snoozed": {"task": "mail.wake_snoozed_threads", "schedule": timedelta(seconds=60)},
    "mail-evict-bodies": {"task": "mail.evict_cached_bodies", "schedule": timedelta(hours=6)},
    "devices-refresh-health": {"task": "devices.refresh_health", "schedule": timedelta(minutes=1)},
    "devices-prune": {"task": "devices.prune", "schedule": timedelta(hours=1)},
    "sms-dispatch-due": {"task": "sms.dispatch_due", "schedule": timedelta(seconds=5)},
    "sms-expire-outbound": {"task": "sms.expire_outbound", "schedule": timedelta(minutes=1)},
    "sms-retention-purge": {"task": "sms.retention_purge", "schedule": timedelta(hours=6)},
    "sms-media-cleanup": {"task": "sms.media_cleanup", "schedule": timedelta(hours=1)},
    "sms-simulator-tick": {"task": "sms.simulator_tick", "schedule": timedelta(seconds=5)},
}

# --- Company / product ----------------------------------------------------------------------------------
COMPANY_NAME = env("COMPANY_NAME", default="Your Company")
PUBLIC_APP_URL = env("PUBLIC_APP_URL", default="http://localhost:3000").rstrip("/")

# --- Mail platform --------------------------------------------------------------------------------------
# MultiFernet keys, comma separated, newest first. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MAIL_TOKEN_KEYS = env.list("MAIL_TOKEN_KEYS", default=[])
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_REDIRECT_URI = env("GOOGLE_OAUTH_REDIRECT_URI", default="") or f"{PUBLIC_APP_URL}/api/v1/mail/oauth/callback/"
GOOGLE_OAUTH_SCOPES = env.list(
    "GOOGLE_OAUTH_SCOPES",
    default=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/gmail.settings.basic",
    ],
)
MAIL_INITIAL_SYNC_DAYS = env.int("MAIL_INITIAL_SYNC_DAYS", default=90)
MAIL_INITIAL_SYNC_MAX_THREADS = env.int("MAIL_INITIAL_SYNC_MAX_THREADS", default=3000)
MAIL_INVITE_TTL_HOURS = env.int("MAIL_INVITE_TTL_HOURS", default=72)
MAIL_BODY_CACHE_DAYS = env.int("MAIL_BODY_CACHE_DAYS", default=14)
MAIL_MAX_ATTACHMENT_BYTES = env.int("MAIL_MAX_ATTACHMENT_BYTES", default=25 * 1024 * 1024)
# Requests per second per mailbox (Gmail allows 250 quota units/s per user; most calls cost 5-10).
MAIL_RATE_PER_SECOND = env.float("MAIL_RATE_PER_SECOND", default=15.0)
# Allow the fake provider in this environment (dev, demo, tests). Off in production by default.
MAIL_ENABLE_FAKE_PROVIDER = env.bool("MAIL_ENABLE_FAKE_PROVIDER", default=True)

# --- Devices (shared by SMS and, later, Calls) and the SMS platform -------------------------------------------
# MultiFernet keys for SMS bodies and MMS files, comma separated, newest first. Separate from MAIL_TOKEN_KEYS so
# a leak of one key ring does not expose the other. Rotate with `python manage.py rotate_sms_keys`.
SMS_DATA_KEYS = env.list("SMS_DATA_KEYS", default=[])
# Encrypted MMS files. Private storage outside any web root; never served directly.
# Base URL phones use for /api/v1/device/ (encoded in the enrollment QR). Set it when the API has its own domain;
# it must be one of the hosts in the app's ALLOWED_SERVER_HOSTS build define.
SMS_DEVICE_API_URL = env("SMS_DEVICE_API_URL", default="").rstrip("/") or PUBLIC_APP_URL
SMS_MEDIA_ROOT = env("SMS_MEDIA_ROOT", default=str(BASE_DIR / "private" / "sms-media"))
SMS_MAX_MMS_BYTES = env.int("SMS_MAX_MMS_BYTES", default=2 * 1024 * 1024)
SMS_INITIAL_SYNC_DAYS = env.int("SMS_INITIAL_SYNC_DAYS", default=90)
SMS_ENROLL_TTL_HOURS = env.int("SMS_ENROLL_TTL_HOURS", default=24)
# Short enrollment codes (XXXX-XXXX): lifetime, and wrong codes (from all clients) within that window that lock every
# live short code. Per-IP limits: the device_short_code throttles below.
SMS_SHORT_CODE_MINUTES = env.int("SMS_SHORT_CODE_MINUTES", default=15)
SMS_SHORT_CODE_MAX_FAILURES = env.int("SMS_SHORT_CODE_MAX_FAILURES", default=50)
SMS_DEVICE_TOKEN_TTL = env.int("SMS_DEVICE_TOKEN_TTL", default=15)  # minutes
SMS_MIN_APP_VERSION = env("SMS_MIN_APP_VERSION", default="1.0.0")
# Refuse phones whose key is not hardware-backed with a verified Android key attestation chain. Needs the
# Google attestation roots in SMS_ATTESTATION_ROOTS_FILE (PEM bundle).
SMS_REQUIRE_KEY_ATTESTATION = env.bool("SMS_REQUIRE_KEY_ATTESTATION", default=False)
SMS_ATTESTATION_ROOTS_FILE = env("SMS_ATTESTATION_ROOTS_FILE", default="")
# Refuse phones without a passing Play Integrity verdict (needs PLAY_INTEGRITY_* below).
SMS_REQUIRE_PLAY_INTEGRITY = env.bool("SMS_REQUIRE_PLAY_INTEGRITY", default=False)
PLAY_INTEGRITY_PACKAGE_NAME = env("PLAY_INTEGRITY_PACKAGE_NAME", default="")
PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE = env("PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE", default="")
# Base64 SHA-256 of the company's APK signing certificate(s), for privately distributed builds.
PLAY_INTEGRITY_CERT_DIGESTS = env.list("PLAY_INTEGRITY_CERT_DIGESTS", default=[])
SMS_OUTBOUND_TTL_HOURS = env.int("SMS_OUTBOUND_TTL_HOURS", default=24)
SMS_DEVICE_DAILY_CAP = env.int("SMS_DEVICE_DAILY_CAP", default=300)
SMS_DEVICE_RATE_PER_MINUTE = env.int("SMS_DEVICE_RATE_PER_MINUTE", default=20)
SMS_USER_RATE_PER_MINUTE = env.int("SMS_USER_RATE_PER_MINUTE", default=30)
SMS_ALLOW_SHORT_CODES = env.bool("SMS_ALLOW_SHORT_CODES", default=False)
SMS_RETENTION_DAYS = env.int("SMS_RETENTION_DAYS", default=365)  # 0 = keep forever
SMS_MIRROR_DEVICE_DELETES = env.bool("SMS_MIRROR_DEVICE_DELETES", default=False)
SMS_DEFAULT_REGION = env("SMS_DEFAULT_REGION", default="TZ")
SMS_SHOW_ADMIN_NAME_ON_PHONE = env.bool("SMS_SHOW_ADMIN_NAME_ON_PHONE", default=True)
# Foreground-service poll interval the phone uses when FCM is not configured (seconds).
SMS_DEVICE_POLL_SECONDS = env.int("SMS_DEVICE_POLL_SECONDS", default=20)
# Simulated phones for demos and E2E tests. Production refuses to start with it on.
SMS_ENABLE_SIMULATOR = env.bool("SMS_ENABLE_SIMULATOR", default=MAIL_ENABLE_FAKE_PROVIDER)
# Firebase Cloud Messaging (optional): data-only wake-ups. The service-account file is a mounted secret.
FCM_PROJECT_ID = env("FCM_PROJECT_ID", default="")
FCM_SERVICE_ACCOUNT_FILE = env("FCM_SERVICE_ACCOUNT_FILE", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        # googleapiclient logs request URLs at DEBUG (may include tokens in query strings): keep it quiet.
        "googleapiclient": {"level": "WARNING"},
        "google_auth_oauthlib": {"level": "WARNING"},
        "urllib3": {"level": "WARNING"},
    },
}
