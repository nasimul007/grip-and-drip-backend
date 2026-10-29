from decouple import config

# Production unless told otherwise, so a missing variable never ships DEBUG.
# Local machines set DJANGO_ENV=dev in .env.
DJANGO_ENV = config("DJANGO_ENV", default="prod")

if DJANGO_ENV == "dev":
    from .dev import *
else:
    from .prod import *
