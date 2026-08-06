"""Django settings for the RentA-Fleet PRO backend.

Hybrid persistence:
  * PostgreSQL  -> transactional/relational data (users, companies, fleet).
  * ClickHouse  -> append-only, high-volume telemetry (queried via
                   ``backend/infrastructure/clickhouse/client.py``, NOT through the Django ORM).

Secrets and environment-specific values are loaded from a local ``.env``
file (see ``.env.example``). Never commit a real ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# BASE_DIR is the backend/ directory itself (this file's own directory) —
# .env, requirements.txt and db.sqlite3 all live alongside it.
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env (no-op if the file is absent).
load_dotenv(BASE_DIR / ".env")


def _env_bool(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable ('1', 'true', 'yes' => True)."""
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str, default: str = "") -> list[str]:
    """Parse a comma-separated environment variable into a list."""
    return [item.strip() for item in os.getenv(key, default).split(",") if item.strip()]


# --- Core security -----------------------------------------------------
# SECRET_KEY has NO hardcoded fallback on purpose: a working default would
# mean any deployment that forgets to set DJANGO_SECRET_KEY silently runs
# on a key that's public (it would be sitting in source control), which
# breaks session/CSRF integrity and password-reset token security without
# any visible symptom. Fail loudly instead — see .env.example.
try:
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
except KeyError as exc:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY ortam değişkeni tanımlı değil. "
        ".env dosyanıza ekleyin (bkz. .env.example)."
    ) from exc

# Defaults to False (fail closed): DEBUG=True leaks full tracebacks (incl.
# SECRET_KEY, SQL, local variables) to any visitor on a 500, and serves
# MEDIA_ROOT uploads (vehicle documents) unauthenticated. Environments that
# want debug mode must opt in explicitly via DJANGO_DEBUG=true in .env.
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,.localhost,.rentafleetpro.com",
)

# Çok-kiracılı subdomain yapısı için (ör. acme.rentafleetpro.com) — Django
# 4+ CSRF Origin kontrolü artık zorunlu, bu olmadan her tenant subdomain'inde
# oturum tabanlı (browsable API/admin) POST istekleri 403 döner.
CSRF_TRUSTED_ORIGINS = _env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://*.rentafleetpro.com",
)

# DEBUG=True iken (yerel geliştirme) hiçbiri uygulanmaz — bunlar sadece HTTPS
# arkasındaki gerçek dağıtımda anlamlıdır; yerel http://localhost akışını
# bozmamak için DEBUG=False olduğunda devreye girer.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Kurumsal dağıtımlar neredeyse her zaman TLS'i sonlandıran bir ters
    # proxy/load balancer (ALB, nginx, Cloudflare) arkasında çalışır — bu
    # durumda Django'ya gelen dahili istek HER ZAMAN düz HTTP'dir, bu yüzden
    # SECURE_SSL_REDIRECT=True SONSUZ YÖNLENDİRME DÖNGÜSÜNE yol açar (Django
    # her isteği HTTP sanıp HTTPS'e yönlendirir, proxy bunu tekrar HTTP
    # olarak iletir). Varsayılan KAPALI: bu, istemcinin `X-Forwarded-Proto`
    # başlığını doğrudan güvenip sahteciliğe (spoofing) açık hâle getirir —
    # yalnızca GERÇEKTEN güvenilir bir proxy varsa ve o proxy bu başlığı
    # dıştan gelen değerlerle EZİYORSA açılmalıdır.
    if _env_bool("DJANGO_BEHIND_PROXY", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


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
    # Modüler domain app'leri
    "backend.apps.core.apps.CoreConfig",
    "backend.apps.companies.apps.CompanyConfig",
    "backend.apps.vehicles.apps.VehiclesConfig",
    "backend.apps.customer_profiles.apps.CustomerProfilesConfig",
    "backend.apps.rentals.apps.RentalsConfig",
    "backend.apps.vehicle_finance.apps.VehicleFinanceConfig",
    "backend.apps.enuygun.apps.EnuygunConfig",
    "backend.apps.risk_checks.apps.RiskChecksConfig",
    "backend.apps.analytics.apps.AnalyticsConfig",
    "backend.apps.ai.apps.AiConfig",
    "backend.apps.idempotency.apps.IdempotencyConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # SecurityMiddleware'den hemen sonra, her şeyden önce — statik dosya
    # isteklerini (SPA build'i + Django admin statikleri) tek işlemde,
    # ayrı bir web sunucusu/CDN olmadan sunar (bkz. STATIC_ROOT/WHITENOISE_*).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must precede CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "backend.common.middleware.company_router.CompanyRouterMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.apps.core.urls"

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


# Render/Neon/Heroku tarzı barındırıcılar tek bir DATABASE_URL bağlantı
# dizesi verir — ayrı ayrı POSTGRES_* değişkenleri BEKLEMEZLER. Bu varsa
# doğrudan ondan çözümlenir; yoksa aşağıdaki POSTGRES_*/sqlite yoluna
# (yerel geliştirme) düşülür. İki yol da aynı DATABASES sözlüğüne varır.
_database_url = os.getenv("DATABASE_URL", "")
if _database_url:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=int(os.getenv("POSTGRES_CONN_MAX_AGE", "0")),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.getenv("POSTGRES_DB", str(BASE_DIR / "db.sqlite3")),
            "USER": os.getenv("POSTGRES_USER", ""),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", ""),
            "PORT": os.getenv("POSTGRES_PORT", ""),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "0")),
        }
    }

    if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
        DATABASES["default"]["NAME"] = str(BASE_DIR / "db.sqlite3")

        # SQLite tek yazarlıdır (dosya kilidi) — çok kiracılı, eşzamanlı trafik
        # altında güvenli değildir. DB_ENGINE ayarlanmadan yanlışlıkla üretime
        # (DEBUG=False) böyle çıkılmasını engeller (bkz. audit bulgusu #36; aynı
        # "sessiz yanlış-yapılandırma" deseni SECRET_KEY/DEBUG için de uygulandı).
        if not DEBUG:
            raise ImproperlyConfigured(
                "DJANGO_DEBUG=False (üretim modu) iken hâlâ SQLite kullanılıyor. "
                "DATABASE_URL (Render/Neon) ya da DB_ENGINE + POSTGRES_* "
                "ortam değişkenlerini ayarlayın."
            )

# Project-defined user model (roles: FLEET_MANAGER / OPERATIONS_STAFF).
AUTH_USER_MODEL = "companies.CustomUser"


# --- Cache (Redis, opsiyonel) --------------------------------------------
# REDIS_URL ayarlıysa paylaşılan (worker'lar arası) bir Redis önbelleği
# kullanılır — ayarlı değilse (yerel geliştirme/test/CI) süreç-içi,
# paylaşılmayan LocMemCache'e sessizce düşer. Bu, projedeki diğer
# env-gated-yedek desenle (OPENAI_API_KEY, DB_ENGINE) tutarlıdır: Redis
# kurulu olmayan bir ortamda hiçbir şey kırılmaz.
REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


# --- Celery (arka plan işleri, opsiyonel) --------------------------------
# REDIS_URL yoksa CELERY_TASK_ALWAYS_EAGER=True: `.delay()` çağrıları ayrı
# bir worker süreci gerekmeden, o an ÇAĞRILDIĞI yerde senkron çalışır — bu
# yüzden Redis/worker kurulu olmayan bir ortamda (yerel geliştirme/test/CI)
# hiçbir şey kırılmaz, görevler sadece asenkron değil senkron yürür.
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or None
CELERY_TASK_ALWAYS_EAGER = not bool(REDIS_URL)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = "Europe/Istanbul"
CELERY_BEAT_SCHEDULE = {
    "refresh-competitor-prices-every-6-hours": {
        "task": "backend.infrastructure.services.enuygun.tasks.refresh_competitor_prices_task",
        "schedule": 6 * 60 * 60,
    },
}


# --- ClickHouse (analytical / time-series store) -----------------------
# Consumed by backend/infrastructure/clickhouse/client.py. Kept as a plain dict so it stays
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


# --- OpenAI (AI Filo Operasyon Asistanı) --------------------------------
# Anahtar tanımlıysa gerçek model çağrısı yapılır; aksi halde servis
# deterministik, veriye dayalı Türkçe fallback yanıtı üretir.
# Varsayılan model "gpt-4o-mini"den "gpt-4o"ya yükseltildi: asistan artık
# gerçek eylemler (kiralama oluşturma vb.) öneren bir function-calling ajanı
# — yanlış aracı/sürücüyü seçmek gerçek bir hataya yol açabileceğinden,
# tool-seçim doğruluğu maliyet/gecikmeden daha önemli. `OPENAI_MODEL` env
# değişkeniyle hâlâ override edilebilir.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


# --- Django REST Framework ---------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    # Genel oran sınırlaması yoktu — özellikle /api/auth/login/ kaba kuvvet
    # denemelerine açıktı. "login" scope'u LoginView'a ayrıca uygulanır (daha
    # sıkı bir limit); DEFAULT_THROTTLE_RATES'teki diğer ikisi genel API
    # trafiği için makul bir taban.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "1000/minute",
        "login": "10/minute",
    },
}


# --- CORS --------------------------------------------------------------
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)
# Yeni şirket subdomain'leri için yeniden deploy gerekmez.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.rentafleetpro\.com$",
    r"^http://[\w-]+\.localhost:\d+$",
]
CORS_ALLOW_HEADERS = (*default_headers, "x-company-slug")


# --- Password validation ----------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internationalization ----------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# --- Logging -------------------------------------------------------------
# Without this dict, `logging.getLogger(__name__)` calls scattered across
# the codebase (ai_consultant_service, clickhouse client, etc.) fall back to
# Python's unconfigured "handler of last resort" — unformatted, unfiltered,
# and easy to miss. This gives every logger a console handler by default and
# a dedicated, more verbose one for unhandled request exceptions.
#
# DJANGO_LOG_FORMAT=json switches to single-line JSON records (see
# backend/common/json_log_formatter.py) — production log aggregators (ELK,
# Datadog, CloudWatch) parse structured JSON far more reliably than free
# text. Default stays "text" so local development output stays readable.
_LOG_FORMAT = os.getenv("DJANGO_LOG_FORMAT", "text")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
        "json": {
            "()": "backend.common.json_log_formatter.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if _LOG_FORMAT == "json" else "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}


# --- Sentry (hata izleme / APM, opsiyonel) --------------------------------
# SENTRY_DSN boşsa hiçbir şey başlatılmaz (aynı OPENAI_API_KEY/REDIS_URL
# deseni) — bir Sentry hesabı/DSN'i olmayan bir ortamda (bu proje dahil)
# sıfır davranış değişikliği, sıfır hata riski.
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import logging as _logging

    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=None, event_level=_logging.ERROR),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=os.getenv("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development"),
        send_default_pii=False,
    )


# --- Static files (Django'nun kendi statikleri, ör. admin CSS/JS) ------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- SPA (frontend/dist) — WhiteNoise'un STATIC_URL DIŞINDAKİ "kök dizin"
# sunumu. Vue hash-router kullandığı için (`#/overview` — bkz. README)
# tarayıcı sunucudan HER ZAMAN yalnızca `/` ister, alt path'leri asla; bu
# yüzden ayrı bir SPA-fallback URL deseni gerekmez — `WHITENOISE_INDEX_FILE`
# `/`'i doğrudan `index.html`'e çözer, `/assets/...` referansları da aynı
# dizinden gelir. Tek servis: Django hem API'yi hem SPA'yı sunar, CORS
# gerekmez (bkz. `render.yaml`'daki build adımı — `npm run build` bu dizini
# deploy ÖNCESİ üretir, git'e COMMIT EDİLMEZ).
_frontend_dist = BASE_DIR.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    # Yerel geliştirmede `frontend/dist` genelde YOK (Vite dev server
    # kullanılıyor, `npm run build` çalıştırılmadı) — WhiteNoise'a var
    # olmayan bir kök dizin vermemek için sadece build üretilmişse ayarlanır.
    WHITENOISE_ROOT = _frontend_dist
WHITENOISE_INDEX_FILE = True

# --- Media (kullanıcı yüklemeleri — araç dosyaları/ekleri) -------------
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"