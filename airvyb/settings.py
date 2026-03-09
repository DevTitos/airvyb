import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-c)qre%^$e(j9c_^(va%vhzada_c=s_3h)k4=v8s4uha5-=@oa2'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'airvyb.co.ke', 'www.airvyb.co.ke', 'mail.airvyb.co.ke']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'account',
    'core',
    'finance',
    'activation',
    'deals',
    'webpush',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'activation.middleware.ActivationRequiredMiddleware',
]

ROOT_URLCONF = 'airvyb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'),],
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

WSGI_APPLICATION = 'airvyb.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'airvyb/static')
]
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'officialbotproffesor@gmail.com'
EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = 'Airvyb <noreply@airvyb.co.ke>'

AUTH_USER_MODEL = 'account.User'


# Login URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_SAVE_EVERY_REQUEST = True

# Security settings (for production)
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# PayHero API Configuration (move credentials to settings)
PAYHERO_API_URL = 'https://backend.payhero.co.ke/api/v2/payments'
PAYHERO_AUTH_TOKEN=os.getenv('PAYHERO_AUTH_TOKEN')
PAYHERO_CHANNEL_ID = 947
PAYHERO_CALLBACK_URL = 'https://airvyb.co.ke/payment/mpesa/success/'  # Update with your domain

PAYHERO_ACTIVATION_CALLBACK_URL= 'https://airvyb.co.ke/activation/callback/'

INTASEND_PUBLISHABLE_KEY=os.getenv('INTASEND_PUBLISHABLE_KEY')
INTASEND_TOKEN=os.getenv('INTASEND_TOKEN')
INTASEND_CALLBACK_URL = 'https://airvyb.co.ke/finance/deposit/callback/'


WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEYyfurVipYR0tv53QuJRQzMSsD/OQPLunEqO+gPf430W6CDV3GB8w5fcJPGy3jiYkZcknMgoSxscaU5b4ghXo4A==",
    "VAPID_PRIVATE_KEY": "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg3BNz3ROUlzA5Bd5h8l5ZL8iCUBNdDlG4NfhEA7Nwzs2hRANCAARjJ+6tWKlhHS2/ndC4lFDMxKwP85A8u6cSo76A9/jfRboINXcYHzDl9wk8bLeOJiRlyScyChLGxxpTlviCFejg",
    "VAPID_ADMIN_EMAIL": "admin@airvyb.co.ke"
}


# Hedera Configuration
HEDERA_NETWORK = 'testnet'  # or 'mainnet', 'previewnet'
HEDERA_ENCRYPTION_KEY = os.getenv('SECRET_KEY')
AUTO_CREATE_HEDERA_ACCOUNTS = True  # Auto-create accounts after login