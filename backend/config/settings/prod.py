from .base import *  # noqa: F401,F403
from .base import MAIL_TOKEN_KEYS, SECRET_KEY, env

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
MAIL_ENABLE_FAKE_PROVIDER = env.bool("MAIL_ENABLE_FAKE_PROVIDER", default=False)
# Nginx redirects to HTTPS (a Django redirect would break the internal http health check and proxy hop), and
# HSTS for subdomains / preload would bind the company's other subdomains, so those are left to the operator.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]

if SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
if not MAIL_TOKEN_KEYS:
    raise RuntimeError("MAIL_TOKEN_KEYS must be set in production.")
if "0LpZ_qn1Yk97rlZ_Hj-OXpLgd5x9zFfgjTL3rvbNhKg=" in MAIL_TOKEN_KEYS:
    raise RuntimeError("MAIL_TOKEN_KEYS contains the dev-only key from settings/dev.py; generate a new one.")
