import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-development-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "0").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"

# MongoDB almacena los datos de la aplicación mediante PyMongo.
# SQLite queda disponible solo para los mecanismos internos de Django
# si posteriormente se habilitan migraciones, sesiones o autenticación.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "django-internal.sqlite3",
    }
}

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # django.contrib.auth no está instalado: sin esto DRF intenta importar
    # AnonymousUser en cada petición y responde 500.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

MONGO_CONFIG = {
    "host": os.environ.get("MONGO_HOST", "mongodb"),
    "port": int(os.environ.get("MONGO_PORT", "27017")),
    "database": os.environ.get("MONGO_DATABASE", "plataforma"),
    "username": os.environ.get("MONGO_APP_USER", ""),
    "password": os.environ.get("MONGO_APP_PASSWORD", ""),
}

# Clave que Unity envía en la cabecera X-API-Key al subir la partida.
GAME_API_KEY = os.environ.get("GAME_API_KEY", "")
