from .base import *
from decouple import config

DEBUG = False

DATABASES = {
    "default": config(
        "DATABASE_URL",
        cast=lambda url: {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.split("/")[-1],
            "USER": url.split("//")[1].split(":")[0],
            "PASSWORD": url.split(":")[2].split("@")[0],
            "HOST": url.split("@")[1].split(":")[0],
            "PORT": url.split(":")[3].split("/")[0] if ":" in url.split("@")[1] else "5432",
        },
    )
}

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# TLS ends at the reverse proxy; it must send X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

REST_FRAMEWORK["NUM_PROXIES"] = config("NUM_PROXIES", default=1, cast=int)
# Browsable API is a debugging aid; JSON only in production.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = ("rest_framework.renderers.JSONRenderer",)
