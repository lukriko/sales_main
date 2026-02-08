"""
Django settings for my_project project.
FIXED VERSION for Render deployment with Redis fallback
"""
import dj_database_url
from pathlib import Path
from decouple import config, Csv
import os


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
# FIX 1: Use environment variable in production
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-v-0&*qo7n3i7b!a4vm@m)=7ia)v!&(e&v*inwolo6^g4zom$l3'
)

# FIX 2: Environment detection - simplified
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local")
DEBUG = ENVIRONMENT != "production"

IS_RENDER = os.environ.get('RENDER', 'false').lower() == 'true'
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production" if IS_RENDER else "local")

DEBUG = ENVIRONMENT != "production"

# ALLOWED_HOSTS configuration
if ENVIRONMENT == "production" or IS_RENDER:
    # Production mode or on Render
    ALLOWED_HOSTS = [
        'yr-dep-ss.onrender.com',
        '.onrender.com',  # Allow all Render subdomains
        '127.0.0.1',      # Keep localhost for health checks
        'localhost'
    ]
else:
    # Local development
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

print(f"🔧 ENVIRONMENT: {ENVIRONMENT}")
print(f"🔧 IS_RENDER: {IS_RENDER}")
print(f"🔧 DEBUG: {DEBUG}")
print(f"🔧 ALLOWED_HOSTS: {ALLOWED_HOSTS}")



# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'sales_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'sales_app.middleware.QueryTimingMiddleware', 
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'sales_app.middleware.LocationAccessMiddleware',
]

# Make login required by default
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'

ROOT_URLCONF = 'my_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'my_project.wsgi.application'


# Database
# FIX 4: Proper database configuration with fallback
# Database
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Production
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True
        )
    }
    DATABASES['default']['OPTIONS'] = {
        'connect_timeout': 10,
        'options': '-c statement_timeout=300000',
    }
else:
    # Local development - use .env variables
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('PGDATABASE', default='main_db'),
            'USER': config('PGUSER', default='postgres'),
            'PASSWORD': config('PGPASSWORD', default='overall'),
            'HOST': config('PGHOST', default='localhost'),
            'PORT': config('PGPORT', default='5432'),
        }
    }


# FIX 5: Database optimization (moved after DATABASES definition)
if 'default' in DATABASES:
    DATABASES['default'].setdefault('CONN_MAX_AGE', 60)
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['connect_timeout'] = 10
    
    # Only add statement_timeout for PostgreSQL
    if DATABASES['default'].get('ENGINE') == 'django.db.backends.postgresql':
        DATABASES['default']['OPTIONS']['options'] = '-c statement_timeout=30000'


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


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# FIX 6: Proper static files configuration for Whitenoise
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# FIX 7: Add STATICFILES_DIRS if you have a static folder in your project
# Uncomment if you have a 'static' folder at project root:
# STATICFILES_DIRS = [BASE_DIR / 'static']


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Jazzmin settings
JAZZMIN_SETTINGS = {
    "site_title": "Sales Admin",
    "site_header": "Sales Dashboard",
    "site_brand": "Sales Data Pro",
    "welcome_sign": "Welcome to the 2026 Sales Manager",
    "search_model": ["sales_app.Sales"],
    "show_ui_builder": True,
}


# ============================================================================
# FIX 8: REDIS CACHING - WITH SAFE FALLBACK
# ============================================================================

if ENVIRONMENT == "production":
    REDIS_URL = os.environ.get("REDIS_URL")
    
    if REDIS_URL:
        # Redis is available - use it
        print("✓ Redis URL found - using Redis for caching")
        try:
            CACHES = {
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": REDIS_URL,
                    "OPTIONS": {
                        "CLIENT_CLASS": "django_redis.client.DefaultClient",
                        "CONNECTION_POOL_KWARGS": {
                        "max_connections": 50,  # Changed from 20
                        "retry_on_timeout": True,
                    },
                        "SOCKET_CONNECT_TIMEOUT": 5,  # Add timeout
                        "SOCKET_TIMEOUT": 5,
                    },
                    "KEY_PREFIX": "sales_dashboard",
                    "TIMEOUT": 900, 
                }
            }
            SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
            SESSION_CACHE_ALIAS = "default"
        except Exception as e:
            # Fallback if Redis fails
            print(f"⚠ Redis connection failed: {e} - falling back to in-memory cache")
            CACHES = {
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "unique-snowflake",
                }
            }
            SESSION_ENGINE = "django.contrib.sessions.backends.db"
    else:
        # Redis not configured - use in-memory cache
        print("⚠ Redis URL not found - using in-memory cache (slower)")
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            }
        }
        SESSION_ENGINE = "django.contrib.sessions.backends.db"
else:
    # Local development: No Redis required
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"


# FIX 9: Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if DEBUG else 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'WARNING',
            'propagate': False,
        },
    },
}


# FIX 10: Security settings for production
if ENVIRONMENT == "production":
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'


# FIX 11: Add these if missing
CSRF_TRUSTED_ORIGINS = [
    'https://yr-dep-ss.onrender.com',
    'https://*.onrender.com',
]


# At the bottom of settings.py
if os.environ.get('LOG_QUERIES', 'false').lower() == 'true':
    LOGGING['loggers']['django.db.backends'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False,
    }

# File upload settings (if you handle file uploads)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB