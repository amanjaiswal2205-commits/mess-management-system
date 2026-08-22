import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import pymysql
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-_2ufcvuw4m3724szst$v_*o%4zc&@3@')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = ['*']
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # django-allauth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # 👇 apna app yahan add karo
    'core.apps.CoreConfig',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'messmgt.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'messmgt.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('MYSQL_NAME', 'mess_db'),
        'USER': os.environ.get('MYSQL_USER', 'root'),
        'PASSWORD': os.environ.get('MYSQL_PASSWORD', 'Aman@123'),
        'HOST': os.environ.get('MYSQL_HOST', '127.0.0.1'),
        'PORT': os.environ.get('MYSQL_PORT', '3306'),
    }
}
_db_url = os.environ.get('DATABASE_URL')
if _db_url:
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(_db_url, conn_max_age=600)


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# django-allauth configuration
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# --- Login identity configuration -------------------------------------------
# Installed django-allauth: 65.19.1 -> use the *new style* settings
# (ACCOUNT_LOGIN_METHODS / ACCOUNT_SIGNUP_FIELDS). The legacy
# ACCOUNT_AUTHENTICATION_METHOD / ACCOUNT_EMAIL_REQUIRED / ACCOUNT_USERNAME_REQUIRED
# settings are deprecated in this version and must NOT be used.

# Email (Gmail) is the ONLY accepted login identifier. Username login is off:
# with a single login method allauth builds the `login` form field as an
# EmailField (type="email", trimmed + lowercased) and authenticates purely via
# allauth.account.auth_backends.AuthenticationBackend._authenticate_by_email().
ACCOUNT_LOGIN_METHODS = {'email'}

# 'username' intentionally removed so no username is ever asked/required.
# NOTE: 'password1' MUST stay listed here -- allauth's LoginForm deletes its own
# password field when 'password1' is absent from ACCOUNT_SIGNUP_FIELDS.
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']

# The project keeps Django's default User model, which still owns a `username`
# column (the OTP registration flow fills it with the email). allauth therefore
# still needs to know the field name, it is simply never used to log in.
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'

# Mandatory when email is a login method (allauth raises a Critical check error
# otherwise) and makes the email a real unique login identifier.
ACCOUNT_UNIQUE_EMAIL = True

ACCOUNT_EMAIL_VERIFICATION = 'none'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

_google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
_google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
if _google_client_id and _google_client_secret:
    SOCIALACCOUNT_PROVIDERS['google']['APPS'] = [
        {
            'client_id': _google_client_id,
            'secret': _google_client_secret,
        }
    ]

CSRF_TRUSTED_ORIGINS = [
    'https://lynell-uncomposed-amiya.ngrok-free.dev',
    'http://localhost:8000',
]
_csrf_trusted = os.environ.get('CSRF_TRUSTED_ORIGINS')
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in _csrf_trusted.split(',') if o.strip()])


# --- Email / SMTP (central Gmail sender) ----------------------------------
# Credentials are read from the environment only (.env / hosting env). They are
# NEVER hard-coded in source code.
#
# Sending strategy (the "real email even in DEBUG" config):
#   * If EMAIL_HOST_USER + EMAIL_HOST_PASSWORD are set -> REAL Gmail SMTP is
#     used to deliver OTP emails. This happens even when DEBUG=True, so the
#     registration / password-reset OTPs actually reach the user's Gmail during
#     development.
#   * If no email credentials are configured -> fall back to the console backend
#     (OTP printed to the terminal) so local runs still work without a mailbox.
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', '') or EMAIL_HOST_USER
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '10'))

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    # Real Gmail SMTP sending (works in DEBUG too when credentials are present).
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    # Dev fallback: print OTP emails to the console instead of sending.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'