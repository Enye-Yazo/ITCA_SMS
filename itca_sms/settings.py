# itca_portal/settings.py

from pathlib import Path
from decouple import config

# ─── Base Directory ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

# Container Apps' ingress terminates HTTPS and forwards to the container
# over plain HTTP, adding this header to say so. Without telling Django
# that, it thinks every request is insecure — breaking secure cookies,
# redirect handling, and request.is_secure() everywhere. Harmless locally
# since runserver never sends this header itself.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Needed because CSRF checks validate the request's Origin/Referer against
# this explicit list once a scheme is involved — ALLOWED_HOSTS alone isn't
# enough. Reuses the same env var so one place controls both.
CSRF_TRUSTED_ORIGINS = [
    f'https://{host}' for host in ALLOWED_HOSTS if host not in ('localhost', '127.0.0.1')
]

# Only force HTTPS-only cookies once DEBUG is off — a local runserver
# session over plain http would otherwise silently drop cookies.
# Deliberately not setting SECURE_SSL_REDIRECT here: Container Apps'
# ingress already enforces HTTPS for external traffic, and its internal
# health probes hit the container directly over plain HTTP without the
# forwarded-proto header — an app-level redirect would break those.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# ─── Applications ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'mozilla_django_oidc',  # Microsoft Entra ID authentication

    # Our apps
    'accounts',
    'academics',
    'admissions',
    'assessments',
    'dashboard',
]


# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Serves collected static files directly from the app container —
    # no separate storage account/CDN needed for a site this size.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ─── URLs & WSGI ──────────────────────────────────────────────────────────────
ROOT_URLCONF = 'itca_sms.urls'
WSGI_APPLICATION = 'itca_sms.wsgi.application'


# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Global templates folder at the project root
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ─── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        # Azure Database for PostgreSQL Flexible Server requires SSL by
        # default; the local Docker container doesn't have SSL configured
        # at all, so this is opt-in via env var rather than always-on.
        'OPTIONS': (
            {'sslmode': 'require'} if config('DB_SSL_REQUIRE', default=False, cast=bool) else {}
        ),
    }
}


# ─── Custom User Model ────────────────────────────────────────────────────────
# Tells Django to use our custom user model instead of the built-in one
# This must be set before the first migration — cannot be changed later
AUTH_USER_MODEL = 'accounts.SystemUser'


# ─── Microsoft Entra ID (OIDC) ────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    # Allows Django admin login with email and password
    'django.contrib.auth.backends.ModelBackend',
    # Handles Microsoft Entra ID SSO for regular users — our own subclass,
    # since the default backend's create_user() doesn't match our custom
    # SystemUserManager signature (see accounts/auth.py).
    'accounts.auth.ITCAOIDCAuthenticationBackend',
]

TENANT_ID = config('AZURE_AD_TENANT_ID', default='')

# OIDC endpoints — constructed from your Entra tenant ID
OIDC_RP_CLIENT_ID = config('AZURE_AD_CLIENT_ID', default='')
OIDC_RP_CLIENT_SECRET = config('AZURE_AD_CLIENT_SECRET', default='')
OIDC_RP_SIGN_ALGO = 'RS256'
OIDC_RP_SCOPES = 'openid email profile'

OIDC_OP_AUTHORIZATION_ENDPOINT = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize'
OIDC_OP_TOKEN_ENDPOINT = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'
OIDC_OP_USER_ENDPOINT = 'https://graph.microsoft.com/oidc/userinfo'
OIDC_OP_JWKS_ENDPOINT = f'https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys'

# Where to send users after login and logout.
# LOGIN_REDIRECT_URL and LOGOUT_REDIRECT_URL both point at the landing
# page ('/'), which routes an authenticated user straight to the page
# appropriate for their role (accounts.views.landing) — a logged-out
# visitor sees the "Sign in with Microsoft" screen there instead.
# LOGIN_URL goes straight into the Microsoft sign-in redirect, since a
# deep link hit while logged out (e.g. a bookmarked page) should not
# have to bounce through the landing page first.
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/oidc/authenticate/'

# The nav's "Sign out" link is a plain GET <a> tag, not a POST form —
# mozilla-django-oidc's logout view otherwise only accepts POST.
ALLOW_LOGOUT_GET_METHOD = True


# ─── Password Validation ──────────────────────────────────────────────────────
# Kept for admin use — Entra ID handles actual user passwords
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True


# ─── Static & Media Files ─────────────────────────────────────────────────────
STATIC_URL = '/static/'
# Where Django collects static files for production
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise serves these with cache-busting hashed filenames and gzip/br
# compression baked in at collectstatic time — no CDN or storage account
# needed. Falls back to plain serving if a referenced file is missing
# from the manifest, rather than hard-erroring the whole page.
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ─── Default Primary Key ──────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'