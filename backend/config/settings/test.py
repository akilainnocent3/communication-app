from .base import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "cm", "USER": "cm", "PASSWORD": "cm", "HOST": "127.0.0.1", "PORT": "5432"}}
import os  # noqa: E402

if os.environ.get("TEST_DATABASE_URL"):
    import environ  # noqa: E402

    DATABASES = {"default": environ.Env.db_url_config(os.environ["TEST_DATABASE_URL"])}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = "memory://"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MAIL_TOKEN_KEYS = ["Gx3xN0b8nJ6m0iYwqK9oQv7v2r2N8pZ6Y8u0dA1tL3E="]
GOOGLE_OAUTH_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
GOOGLE_OAUTH_CLIENT_SECRET = "test-secret"
GOOGLE_OAUTH_REDIRECT_URI = "http://testserver/api/v1/mail/oauth/callback/"
PUBLIC_APP_URL = "http://testserver"
MAIL_ENABLE_FAKE_PROVIDER = True
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"login": "1000/min", "public_connect": "1000/min", "device_enroll": "1000/min", "device_auth": "1000/min", "device": "10000/min"}}  # noqa: F405
SMS_DATA_KEYS = ["bW9ja19zbXNfa2V5X2Zvcl90ZXN0c19vbmx5XzMyYnk="]
SMS_ENABLE_SIMULATOR = True
SMS_DEFAULT_REGION = "TZ"
