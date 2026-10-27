from .base import *  # noqa: F401,F403
from .base import MAIL_TOKEN_KEYS, SECRET_KEY, SMS_DEVICE_API_URL, SMS_ATTESTATION_ROOTS_FILE, SMS_DATA_KEYS, SMS_REQUIRE_KEY_ATTESTATION, SMS_REQUIRE_PLAY_INTEGRITY, env

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
MAIL_ENABLE_FAKE_PROVIDER = env.bool("MAIL_ENABLE_FAKE_PROVIDER", default=False)
SMS_ENABLE_SIMULATOR = env.bool("SMS_ENABLE_SIMULATOR", default=False)
# Nginx redirects to HTTPS (a Django redirect would break the internal http health check and proxy hop), and
# HSTS for subdomains / preload would bind the company's other subdomains, so those are left to the operator.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]

if SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
if not MAIL_TOKEN_KEYS:
    raise RuntimeError("MAIL_TOKEN_KEYS must be set in production.")
if "0LpZ_qn1Yk97rlZ_Hj-OXpLgd5x9zFfgjTL3rvbNhKg=" in MAIL_TOKEN_KEYS:
    raise RuntimeError("MAIL_TOKEN_KEYS contains the dev-only key from settings/dev.py; generate a new one.")
if not SMS_DATA_KEYS:
    raise RuntimeError("SMS_DATA_KEYS must be set in production.")
if "q0V6c3Vw8m1yFh3m0dZ8b6m0n3m8sYk2XHkqvQ9QeK4=" in SMS_DATA_KEYS:
    raise RuntimeError("SMS_DATA_KEYS contains the dev-only key from settings/dev.py; generate a new one.")
if set(SMS_DATA_KEYS) & set(MAIL_TOKEN_KEYS):
    raise RuntimeError("SMS_DATA_KEYS and MAIL_TOKEN_KEYS must not share keys.")
if not SMS_DEVICE_API_URL.startswith("https://"):
    raise RuntimeError("SMS_DEVICE_API_URL (or PUBLIC_APP_URL) must be https://: phones refuse any other server.")
if SMS_ENABLE_SIMULATOR:
    raise RuntimeError("SMS_ENABLE_SIMULATOR must be off in production (simulated phones are for demos and tests).")
if SMS_REQUIRE_KEY_ATTESTATION and not SMS_ATTESTATION_ROOTS_FILE:
    raise RuntimeError("SMS_REQUIRE_KEY_ATTESTATION needs SMS_ATTESTATION_ROOTS_FILE (Google's attestation root certificates).")
if SMS_REQUIRE_PLAY_INTEGRITY and not (env("PLAY_INTEGRITY_PACKAGE_NAME", default="") and env("PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE", default="")):
    raise RuntimeError("SMS_REQUIRE_PLAY_INTEGRITY needs PLAY_INTEGRITY_PACKAGE_NAME and PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE.")
