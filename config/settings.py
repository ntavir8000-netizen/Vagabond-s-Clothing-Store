"""
Django settings for the Vagabond's store.
"""

from pathlib import Path

import dj_database_url
from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent
ON_RENDER = config("RENDER", default=False, cast=bool)

if ON_RENDER:
    SECRET_KEY = config("DJANGO_SECRET_KEY")
else:
    SECRET_KEY = config(
        "DJANGO_SECRET_KEY",
        default="django-insecure-local-development-key-change-before-deployment",
    )

DEBUG = True

ALLOWED_HOSTS = [
    "vagabond-s-clothing-store-1.onrender.com",
    "127.0.0.1",
    "localhost",
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "store",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"


if ON_RENDER:
    DATABASES = {
        "default": dj_database_url.parse(config("DATABASE_URL")),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_CLOUDINARY_MEDIA = ON_RENDER and config(
    "USE_CLOUDINARY_MEDIA",
    default=False,
    cast=bool,
)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

if USE_CLOUDINARY_MEDIA:
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]
    STORAGES["default"] = {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SSLCOMMERZ_STORE_ID = config("SSLCOMMERZ_STORE_ID", default="")
SSLCOMMERZ_STORE_PASS = config("SSLCOMMERZ_STORE_PASS", default="")
SSLCOMMERZ_IS_SANDBOX = True