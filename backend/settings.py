# backend/settings.py
"""
Django settings pour ZeeXClub
Configuration standard sans import circulaire
"""

import os
import sys
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent

# =============================================================================
# CONFIGURATION IMPORTÉE (variables simples uniquement)
# =============================================================================

from config import (
    SECRET_KEY,
    DEBUG,
    ALLOWED_HOSTS,
    DATABASES,
    REST_FRAMEWORK,
    CORS_ALLOWED_ORIGINS,
    CORS_ALLOW_ALL_ORIGINS,
    LANGUAGE_CODE,
    TIME_ZONE,
    USE_I18N,
    USE_TZ,
    STATIC_URL,
    STATIC_ROOT,
    MEDIA_URL,
    MEDIA_ROOT,
    LOGGING,
    SECURE_BROWSER_XSS_FILTER,
    SECURE_CONTENT_TYPE_NOSNIFF,
    X_FRAME_OPTIONS,
    SECURE_SSL_REDIRECT,
    SESSION_COOKIE_SECURE,
    CSRF_COOKIE_SECURE,
    TEMPLATES,
)

# =============================================================================
# CONFIGURATION DJANGO (définie ici, pas importée)
# =============================================================================

SECRET_KEY = SECRET_KEY
DEBUG = DEBUG
ALLOWED_HOSTS = ALLOWED_HOSTS

# =============================================================================
# APPLICATIONS DJANGO
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'api.apps.ApiConfig',  # Utilise la classe AppConfig explicite
]

# =============================================================================
# MIDDLEWARE (ordre important!)
# =============================================================================

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # CORS en premier
    'api.middleware.CORSMiddleware',  # Notre middleware CORS custom (complément)
    'api.middleware.LoggingMiddleware',  # Logging avant auth
    'api.middleware.SupabaseAuthMiddleware',  # Auth Supabase
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# =============================================================================
# URLS & WSGI
# =============================================================================

ROOT_URLCONF = 'urls'
WSGI_APPLICATION = 'wsgi.application'

# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = TEMPLATES

# =============================================================================
# BASE DE DONNÉES
# =============================================================================

DATABASES = DATABASES

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = REST_FRAMEWORK

# =============================================================================
# CORS
# =============================================================================

CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS
CORS_ALLOW_ALL_ORIGINS = CORS_ALLOW_ALL_ORIGINS

# =============================================================================
# INTERNATIONALISATION
# =============================================================================

LANGUAGE_CODE = LANGUAGE_CODE
TIME_ZONE = TIME_ZONE
USE_I18N = USE_I18N
USE_TZ = USE_TZ

# =============================================================================
# FICHIERS STATIQUES ET MÉDIAS
# =============================================================================

STATIC_URL = STATIC_URL
STATIC_ROOT = STATIC_ROOT
MEDIA_URL = MEDIA_URL
MEDIA_ROOT = MEDIA_ROOT

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = LOGGING

# =============================================================================
# SÉCURITÉ
# =============================================================================

SECURE_BROWSER_XSS_FILTER = SECURE_BROWSER_XSS_FILTER
SECURE_CONTENT_TYPE_NOSNIFF = SECURE_CONTENT_TYPE_NOSNIFF
X_FRAME_OPTIONS = X_FRAME_OPTIONS

if not DEBUG:
    SECURE_SSL_REDIRECT = SECURE_SSL_REDIRECT
    SESSION_COOKIE_SECURE = SESSION_COOKIE_SECURE
    CSRF_COOKIE_SECURE = CSRF_COOKIE_SECURE
