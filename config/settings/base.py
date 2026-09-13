import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _read_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    env_values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        env_values[key.strip()] = value.strip().strip('"').strip("'")

    return env_values


def _normalize_env_name(raw_env: str) -> str:
    env_name = raw_env.lower()
    if env_name == "production":
        return "prod"
    return env_name


def _load_env_layers() -> None:
    base_env_path = BASE_DIR / ".env"
    base_env_values = _read_env_file(base_env_path)

    selected_env = _normalize_env_name(
        os.getenv("DJANGO_ENV", base_env_values.get("DJANGO_ENV", "dev"))
    )

    merged_values: dict[str, str] = {}
    env_paths = [
        base_env_path,
        BASE_DIR / f".env.{selected_env}",
        BASE_DIR / ".env.local",
        BASE_DIR / f".env.{selected_env}.local",
    ]

    for env_path in env_paths:
        merged_values.update(_read_env_file(env_path))

    for key, value in merged_values.items():
        os.environ.setdefault(key, value)


def env_list(var_name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(var_name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


_load_env_layers()

ENV = _normalize_env_name(os.getenv("DJANGO_ENV", "dev"))

S3_ENABLED = os.getenv("S3_ENABLED", "false").lower() == "true"

VERSION = "1.1.1"

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-zv(*k=m3yk#i$+2%xgx)1v34i1c@ih7=vvr9y3u3i@$4ee2xh-",
)

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_celery_beat",
    "apps.gerelat",
    "apps.accounts",
]

if S3_ENABLED:
    INSTALLED_APPS.append("storages")

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.gerelat.exceptions.exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

_db_engine = os.getenv("DJANGO_DB_ENGINE", "django.db.backends.postgresql")
_db_sslmode = os.getenv("DJANGO_DB_SSLMODE", "")

_db_config: dict[str, object] = {
    "ENGINE": _db_engine,
    "NAME": os.getenv("DJANGO_DB_NAME", "gerelat"),
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": True,
}

if _db_engine == "django.db.backends.postgresql":
    db_options: dict[str, object] = {
        "pool": {
            "min_size": 2,
            "max_size": 10,
            "timeout": 10,
            "max_lifetime": 900,
        },
    }

    if _db_sslmode:
        db_options["sslmode"] = _db_sslmode

    _db_config["OPTIONS"] = db_options

if _db_engine != "django.db.backends.sqlite3":
    _db_config["USER"] = os.getenv("DJANGO_DB_USER", "")
    _db_config["PASSWORD"] = os.getenv("DJANGO_DB_PASSWORD", "")
    _db_config["HOST"] = os.getenv("DJANGO_DB_HOST", "localhost")
    _db_config["PORT"] = os.getenv("DJANGO_DB_PORT", "5432")

DATABASES = {"default": _db_config}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_REGION_NAME = os.getenv("S3_REGION_NAME", "")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
S3_PUBLIC_BASE_URL = os.getenv("S3_PUBLIC_BASE_URL", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")

if S3_ENABLED:
    AWS_S3_ENDPOINT_URL = S3_ENDPOINT_URL
    AWS_S3_REGION_NAME = S3_REGION_NAME
    AWS_STORAGE_BUCKET_NAME = S3_BUCKET_NAME
    AWS_ACCESS_KEY_ID = S3_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = S3_SECRET_KEY
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ADDRESSING_STYLE = "path"

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {"bucket_name": AWS_STORAGE_BUCKET_NAME},
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    if S3_PUBLIC_BASE_URL:
        MEDIA_URL = f"{S3_PUBLIC_BASE_URL.rstrip('/')}/"

_redis_base = (
    os.getenv("REDIS_URL")
    or os.getenv("CELERY_BROKER_URL", "").rsplit("/", 1)[0]
    or "redis://127.0.0.1:6379"
).rstrip("/")

REDIS_URL = _redis_base
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or f"{_redis_base}/0"
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or f"{_redis_base}/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"{_redis_base}/1",
        "TIMEOUT": 300,
    }
}

_SENTRY_DSN = os.getenv("SENTRY_DSN", "")

if _SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        environment=ENV,
        release=VERSION,
        send_default_pii=True,
        enable_logs=True,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profile_session_sample_rate=float(
            os.getenv("SENTRY_PROFILE_SESSION_SAMPLE_RATE", "0.1")
        ),
        profile_lifecycle="trace",
    )
