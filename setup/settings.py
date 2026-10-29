from pathlib import Path
from decouple import config, Csv
import dj_database_url

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
    default=config("DEBUG", cast=bool, default=True),
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
    default='www,api,status,admin,app',
)
# Somente para desenvolvimento local/Codespaces; nunca resolve tenant por
# query string quando DEBUG estiver desativado.
DEV_TENANT_QUERY_PARAM = config("DEV_TENANT_QUERY_PARAM", default="tenant")

# Proxy SSL header for Railway/Reverse proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


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
# terminal; em produção, as credenciais SMTP/provedor são obrigatórias.
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
PUBLIC_APP_URL = config("PUBLIC_APP_URL", default="")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "plataforma.middleware.TenantResolutionMiddleware",
    "plataforma.admin_access.InternalAdminAccessMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "setup.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.config(
        default=config('DATABASE_URL', default=''),
        conn_max_age=600,
        conn_health_checks=True
    )
}


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


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}
