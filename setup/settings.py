from pathlib import Path
from decouple import config, Csv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

import os


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config(
    "DJANGO_DEBUG",
    cast=bool,
    # Padrão seguro: DEBUG só liga quando o ambiente pede explicitamente.
    # Com DEBUG ligado, o tenant pode ser escolhido por ?tenant= ou cookie.
    default=config("DEBUG", cast=bool, default=False),
)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv(), default='localhost,127.0.0.1')

# CSRF trusted origins for production (required for HTTPS origins)
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv(), default='')

# Resolução institucional: o wildcard DNS aponta para a aplicação e o banco
# decide se o hostname está cadastrado e ativo.
PALACIO_BASE_DOMAIN = config('PALACIO_BASE_DOMAIN', default='palaciomental.com.br').lower().strip('.')
TENANT_RESERVED_HOSTS = config(
    'TENANT_RESERVED_HOSTS',
    cast=Csv(),
    default='www,api,status,admin,app,media',
)
# Somente para desenvolvimento local/Codespaces; nunca resolve tenant por
# query string quando DEBUG estiver desativado.
DEV_TENANT_QUERY_PARAM = config("DEV_TENANT_QUERY_PARAM", default="tenant")

# Proxy SSL header for Railway/Reverse proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Endurecimento de produção (DEBUG=False). O redirect HTTPS e o HSTS ficam
# opt-in porque dependem do proxy/healthcheck e afetam todos os subdomínios.
if not DEBUG:
    SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", cast=bool, default=True)
    CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", cast=bool, default=True)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", cast=bool, default=False)
SECURE_REDIRECT_EXEMPT = [r"^saude$"]
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", cast=int, default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", cast=bool, default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CSRF_FAILURE_VIEW = "plataforma.error_views.csrf_failure"


# Application definition

INSTALLED_APPS = [
    "core.apps.CoreConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "plataforma.apps.PlataformaConfig"
]

SITE_ID = 1
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
LOGIN_URL = "plataforma:login"
LOGIN_REDIRECT_URL = "plataforma:projects"
LOGOUT_REDIRECT_URL = "core:index"

# O Django Admin é uma superfície técnica interna do PM. Gestores de tenants
# usam o portal institucional, não recebem acesso ao catálogo administrativo.
PM_INTERNAL_ADMIN_GROUPS = tuple(
    group.strip() for group in config("PM_INTERNAL_ADMIN_GROUPS", default="Equipe PM").split(",") if group.strip()
)

# Endpoint externo usado somente pela página pública de status. O timeout curto
# garante que uma indisponibilidade da API não afete as demais páginas.
STATUS_API_URL = config(
    "STATUS_API_URL",
    default="https://api.palaciomental.com.br/v1/status",
)
STATUS_API_TIMEOUT = config("STATUS_API_TIMEOUT", cast=float, default=3.0)

# E-mail transacional de convites. Em desenvolvimento, o conteúdo aparece no
# terminal; em produção, selecionar explicitamente o backend do provedor.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Palácio Mental <convites@palaciomental.com.br>")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool, default=True)
RESEND_API_KEY = config("RESEND_API_KEY", default="")
RESEND_TIMEOUT = config("RESEND_TIMEOUT", cast=float, default=10.0)
PUBLIC_APP_URL = config("PUBLIC_APP_URL", default="")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "plataforma.middleware.TenantResolutionMiddleware",
    "plataforma.admin_access.InternalAdminAccessMiddleware",
    "plataforma.middleware.RowLevelSecurityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "setup.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "plataforma.context_processors.inbox_unread_count",
                "plataforma.context_processors.tenant_branding",
            ],
        },
    },
]

WSGI_APPLICATION = "setup.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

# RLS: escopo aplicado a conexões novas, antes de qualquer requisição.
# "deny" (padrão) falha fechado em comandos e jobs sem contexto. Para um
# comando administrativo auditado use PM_RLS_DEFAULT_MODE=system.
PM_RLS_DEFAULT_MODE = config("PM_RLS_DEFAULT_MODE", default="deny")

DATABASES = {
    "default": dj_database_url.config(
        default=config('DATABASE_URL', default=''),
        conn_max_age=600,
        conn_health_checks=True
    )
}

# Redis é uma camada de aceleração; o PostgreSQL continua sendo a fonte oficial.
# Fora do Compose, REDIS_URL pode ser omitida e o cache local será utilizado.
REDIS_URL = config("REDIS_URL", default="")
TENANT_CACHE_TTL = config("TENANT_CACHE_TTL", cast=int, default=300)
TENANT_BRANDING_CACHE_TTL = config("TENANT_BRANDING_CACHE_TTL", cast=int, default=300)
TENANT_PUBLIC_CONFIG_CACHE_TTL = config("TENANT_PUBLIC_CONFIG_CACHE_TTL", cast=int, default=120)
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
            "KEY_PREFIX": config("CACHE_KEY_PREFIX", default="pm"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "palacio-mental-local",
            "TIMEOUT": 300,
        }
    }
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
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


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

BASE_DIR = Path(__file__).resolve().parent.parent

# Arquivos estáticos
STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Mídia enviada pelos tenants. Em produção, substituir o storage por S3/R2
# através de STORAGES sem alterar os modelos ou os caminhos dos arquivos.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Mídia persistente: Docker/local usa o filesystem; Railway/homologação pode
# habilitar R2 sem mudar modelos ou views. Nunca faça fallback silencioso para
# MEDIA_ROOT quando R2_ENABLED estiver ativo.
R2_ENABLED = config("R2_ENABLED", cast=bool, default=False)
if R2_ENABLED:
    R2_ACCOUNT_ID = config("R2_ACCOUNT_ID", default="").strip()
    R2_BUCKET_NAME = config("R2_BUCKET_NAME", default="").strip()
    R2_ACCESS_KEY_ID = config("R2_ACCESS_KEY_ID", default="").strip()
    R2_SECRET_ACCESS_KEY = config("R2_SECRET_ACCESS_KEY", default="").strip()
    R2_PUBLIC_URL = config("R2_PUBLIC_URL", default="").strip().rstrip("/")
    if not all((R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_PUBLIC_URL)):
        raise ImproperlyConfigured(
            "R2_ENABLED=True exige R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY e R2_PUBLIC_URL."
        )
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": R2_BUCKET_NAME,
                "endpoint_url": f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
                "access_key": R2_ACCESS_KEY_ID,
                "secret_key": R2_SECRET_ACCESS_KEY,
                "region_name": "auto",
                "location": "media",
                "querystring_auth": False,
                "custom_domain": R2_PUBLIC_URL.removeprefix("https://").removeprefix("http://"),
                "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
            },
        },
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }


# A suíte cria dados de teste fora de requisições; o runner usa escopo system
# e cada requisição do client aplica tenant/global pelo middleware.
TEST_RUNNER = "setup.test_runner.PalacioTestRunner"
