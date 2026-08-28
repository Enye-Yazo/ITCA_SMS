# itca_portal/settings.py

from pathlib import Path
from decouple import config

# ─── Base Directory ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')


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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ─── Default Primary Key ──────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'