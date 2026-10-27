from .base import *  # noqa: F401,F403
from .base import DATABASES, MAIL_TOKEN_KEYS, SMS_DATA_KEYS, env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# runserver handles each request in a new thread; persistent connections would pile up until Postgres refuses more.
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Dev-only key so `docker compose up` works without a .env. Production refuses to start with it.
DEV_ONLY_MAIL_TOKEN_KEY = "0LpZ_qn1Yk97rlZ_Hj-OXpLgd5x9zFfgjTL3rvbNhKg="
if not MAIL_TOKEN_KEYS:
    MAIL_TOKEN_KEYS = [DEV_ONLY_MAIL_TOKEN_KEY]

# Dev-only SMS data key. Production refuses it.
DEV_ONLY_SMS_DATA_KEY = "q0V6c3Vw8m1yFh3m0dZ8b6m0n3m8sYk2XHkqvQ9QeK4="
if not SMS_DATA_KEYS:
    SMS_DATA_KEYS = [DEV_ONLY_SMS_DATA_KEY]
