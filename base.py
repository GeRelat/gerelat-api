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

VERSION = "1.0.0"

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-zv(*k=m3yk#i$+2%xgx)1v34i1c@ih7=vvr9y3u3i@$4ee2xh-",
)

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'jazzmin',
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
    "apps.gerelat",
    "apps.accounts",
    'rest_framework_simplejwt',
    'axes',
]

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'apps.gerelat.middleware.AuditMiddleware',
    'axes.middleware.AxesMiddleware',
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

db_engine = os.getenv("DJANGO_DB_ENGINE", "django.db.backends.postgresql")
db_name = os.getenv("DJANGO_DB_NAME", "gerelat")

DATABASES = {
    "default": {
        "ENGINE": db_engine,
        "NAME": db_name,
    }
}

if db_engine != "django.db.backends.sqlite3":
    DATABASES["default"].update(
        {
            "USER": os.getenv("DJANGO_DB_USER", ""),
            "PASSWORD": os.getenv("DJANGO_DB_PASSWORD", ""),
            "HOST": os.getenv("DJANGO_DB_HOST", "localhost"),
            "PORT": os.getenv("DJANGO_DB_PORT", "5432"),
        }
    )

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

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "https://gerelat-frontend.vercel.app",
]

CORS_ALLOW_CREDENTIALS = True
