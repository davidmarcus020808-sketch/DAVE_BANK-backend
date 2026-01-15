from pathlib import Path
from datetime import timedelta
import os
from pathlib import Path
import os
from dotenv import load_dotenv

# --------------------------
# Load .env file
# --------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # Load environment variables from .env


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-&o+5eesu@09u-0qazi@@od2@ajpq$-8qrof%g3d7s4+p7*lxn&")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

# --------------------------
# Installed apps
# --------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'backdave_app',                                # your app
    'rest_framework',                              # Django REST Framework
    'rest_framework_simplejwt.token_blacklist',    # JWT token blacklist
    'corsheaders',                                 # CORS headers
]

# --------------------------
# Middleware
# --------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# --------------------------
# URLs and templates
# --------------------------
ROOT_URLCONF = 'backdave_bank.urls'

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

WSGI_APPLICATION = 'backdave_bank.wsgi.application'

# --------------------------
# Database
# --------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --------------------------
# Custom User Model
# --------------------------
AUTH_USER_MODEL = 'backdave_app.User'

# --------------------------
# Password validation
# --------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --------------------------
# Internationalization
# --------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --------------------------
# Django REST Framework + JWT
# --------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv("ACCESS_TOKEN_LIFETIME_MINUTES", 30))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", 7))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# Ensure admin can log in with custom user
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True



# --------------------------
# Static files
# --------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# --------------------------
# --------------------------
# Flutterwave keys
# --------------------------
FLUTTERWAVE_KEYS = {
    "VITE_FLUTTERWAVE_PUBLIC_KEY": os.getenv("VITE_FLUTTERWAVE_PUBLIC_KEY"),
    "REACT_APP_FLUTTERWAVE_SECRET_KEY": os.getenv("REACT_APP_FLUTTERWAVE_SECRET_KEY"),
    "REACT_APP_FLUTTERWAVE_ENCRYPTION_KEY": os.getenv("REACT_APP_FLUTTERWAVE_ENCRYPTION_KEY"),
}

# Assign individual variables for convenience
FLUTTERWAVE_PUBLIC_KEY = FLUTTERWAVE_KEYS["VITE_FLUTTERWAVE_PUBLIC_KEY"]
FLUTTERWAVE_SECRET_KEY = FLUTTERWAVE_KEYS["REACT_APP_FLUTTERWAVE_SECRET_KEY"]
FLUTTERWAVE_ENCRYPTION_KEY = FLUTTERWAVE_KEYS["REACT_APP_FLUTTERWAVE_ENCRYPTION_KEY"]

# --------------------------
# Check for missing keys
# --------------------------
missing_keys = [name for name, value in FLUTTERWAVE_KEYS.items() if not value]

if missing_keys:
    print(f"⚠️ Warning: Missing Flutterwave keys in .env: {', '.join(missing_keys)}")
else:
    print("✅ All Flutterwave keys loaded successfully")