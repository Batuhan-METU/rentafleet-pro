"""Django settings for the RentA-Fleet PRO backend.

Hybrid persistence:
  * PostgreSQL  -> transactional/relational data (users, companies, fleet).
  * ClickHouse  -> append-only, high-volume telemetry (queried via
                   ``api/clickhouse_client.py``, NOT through the Django ORM).

Secrets and environment-specific values are loaded from a local ``.env``
file (see ``.env.example``). Never commit a real ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env (no-op if the file is absent).
load_dotenv(BASE_DIR / ".env")


def _env_bool(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable ('1', 'true', 'yes' => True)."""
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str, default: str = "") -> list[str]:
    """Parse a comma-separated environment variable into a list."""
    return [item.strip() for item in os.getenv(key, default).split(",") if item.strip()]


# --- Core security -----------------------------------------------------
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-@1-prw@%%dojwcc5oz4p5+je13(y+7=a@6!gpm--q=gjof=o@y",
)
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")


# --- Applications ------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    # Local
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must precede CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "backend.wsgi.application"


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Project-defined user model (roles: FLEET_MANAGER / OPERATIONS_STAFF).
AUTH_USER_MODEL = "api.CustomUser"


# --- ClickHouse (analytical / time-series store) -----------------------
# Consumed by api/clickhouse_client.py. Kept as a plain dict so it stays
# decoupled from the Django ORM / DATABASES routing.
CLICKHOUSE = {
    "HOST": os.getenv("CLICKHOUSE_HOST", "127.0.0.1"),
    "PORT": int(os.getenv("CLICKHOUSE_PORT", "8123")),
    "USER": os.getenv("CLICKHOUSE_USER", "default"),
    "PASSWORD": os.getenv("CLICKHOUSE_PASSWORD", ""),
    "DATABASE": os.getenv("CLICKHOUSE_DB", "rentafleet_analytics"),
    "SECURE": _env_bool("CLICKHOUSE_SECURE", False),
    "CONNECT_TIMEOUT": int(os.getenv("CLICKHOUSE_CONNECT_TIMEOUT", "10")),
}


# --- OpenAI (AI Filo Danışmanı) ----------------------------------------
# Anahtar tanımlıysa gerçek model çağrısı yapılır; aksi halde servis
# deterministik, veriye dayalı Türkçe fallback yanıtı üretir.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# --- Django REST Framework ---------------------------------------------
# URL-path versioning (/api/v1/...) lays the groundwork for the next step.
REST_FRAMEWORK = {
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "VERSION_PARAM": "version",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}


# --- CORS --------------------------------------------------------------
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    # Vite dev server defaults to :5173; :3000 kept for alternative setups.
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)


# --- Password validation ----------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internationalization ----------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Static files ------------------------------------------------------
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
