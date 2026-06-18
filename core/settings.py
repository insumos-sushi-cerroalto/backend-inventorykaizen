from pathlib import Path
from datetime import timedelta
import os
import socket
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG") == "True"

ALLOWED_HOSTS = [
    'backend-inventorykaizen.onrender.com',
    'localhost',
    '127.0.0.1',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary',
    'cloudinary_storage',
    'rest_framework',
    'corsheaders',
    'inventory',
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'core.wsgi.application'


# Database
import os
import socket

def resolve_postgres_host(hostname):
    """Force IPv4 resolution for Supabase hostnames when IPv6 is not reachable."""
    try:
        addrinfos = socket.getaddrinfo(hostname, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
        if addrinfos:
            return addrinfos[0][4][0]
    except OSError:
        pass
    return hostname

# 1. Carga limpia de variables de entorno
DB_HOST = os.getenv('DB_HOST', 'localhost').strip()
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'postgres').strip()
DB_USER = os.getenv('DB_USER', 'postgres').strip()
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# 2. Extraer el ID del proyecto automáticamente desde el usuario postgres.ID
DB_PROJECT = ''
if '.' in DB_USER:
    DB_PROJECT = DB_USER.split('.', 1)[1]

DB_HOSTNAME = DB_HOST
DB_RESOLVED_HOST = resolve_postgres_host(DB_HOSTNAME)

# 3. Configuración estricta de opciones para Supabase Pooler
options = {
    'connect_timeout': 10,
    'sslmode': 'require' if not DEBUG else 'prefer',
}

# Forzar el ID del proyecto en las opciones (CRÍTICO para que Supavisor funcione)
if DB_PROJECT:
    options['options'] = f'-c project={DB_PROJECT}'

if DB_RESOLVED_HOST != DB_HOSTNAME:
    options['hostaddr'] = DB_RESOLVED_HOST

# Imprimir en consola de Render para verificar que todo viaje correcto
if not DEBUG:
    print('DB CONFIG FIX:', {
        'HOST': DB_HOSTNAME,
        'PORT': DB_PORT,
        'NAME': DB_NAME,
        'USER': DB_USER,
        'OPTIONS': options,
    })

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': DB_HOSTNAME,
        'PORT': DB_PORT,
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'CONN_MAX_AGE': 600,
        'OPTIONS': options,
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "https://frontend-inventorykaizen.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# Cloudinary Storage
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# STATIC FILES (NO cloudinary para estáticos)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

