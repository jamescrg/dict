"""Settings for dict (dict.darmok.link).

Runs behind nginx and the devauth gate, which is the only login. The
dictionary database and the secret key live in data/, which is not committed.
The site keeps nothing of its own: no Django database, no cookies.
"""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

_key_file = DATA_DIR / "secret_key"
if not _key_file.exists():
    _key_file.write_text(secrets.token_urlsafe(50))
    _key_file.chmod(0o600)
SECRET_KEY = _key_file.read_text().strip()

DEBUG = False
ALLOWED_HOSTS = ["dict.darmok.link", "127.0.0.1", "localhost"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The SQLite file tools/build_db.py writes. Opened read-only (lookup/dict.py).
DICT_DB = Path(os.environ.get("DICT_DB", DATA_DIR / "dict.db"))

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "lookup",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
