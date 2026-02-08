# backend/settings.py
"""
Django settings pour ZeeXClub
"""

from config import (
    SECRET_KEY, DEBUG, ALLOWED_HOSTS, INSTALLED_APPS, MIDDLEWARE,
    DATABASES, REST_FRAMEWORK, CORS_ALLOWED_ORIGINS, CORS_ALLOW_ALL_ORIGINS,
    LANGUAGE_CODE, TIME_ZONE, USE_I18N, USE_TZ, STATIC_URL, STATIC_ROOT,
    MEDIA_URL, MEDIA_ROOT, LOGGING, SECURE_BROWSER_XSS_FILTER,
    SECURE_CONTENT_TYPE_NOSNIFF, X_FRAME_OPTIONS, SECURE_SSL_REDIRECT,
    SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, TEMPLATES
)

# Import tout depuis config.py pour centraliser la configuration
# Ce fichier est nécessaire pour la structure Django standard

# Ajouter les middlewares spécifiques à l'API
MIDDLEWARE = [
    'api.middleware.CORSMiddleware',  # CORS en premier
    'api.middleware.LoggingMiddleware',
    'api.middleware.SupabaseAuthMiddleware',
] + MIDDLEWARE

# Configuration des URLs
ROOT_URLCONF = 'urls'

# Application WSGI
WSGI_APPLICATION = 'wsgi.application'

# Static files
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
