import os

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")  # noqa: F405

CORS_ALLOW_ALL_ORIGINS = (
    os.getenv("DJANGO_CORS_ALLOW_ALL_ORIGINS", "true").lower() == "true"
)

if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = env_list(  # noqa: F405
        "DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:3000"
    )
