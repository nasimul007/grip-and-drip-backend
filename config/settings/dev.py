from .base import *
from decouple import config

DEBUG = True

DATABASES = {
    "default": config(
        "DATABASE_URL",
        default="postgresql://postgres:postgres@localhost:5432/grip_and_drip",
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


