# backend/config.py
"""
Configuration centralisée pour ZeeXClub
Toutes les variables d'environnement et constantes du projet
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Chemins de base
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# =============================================================================
# CONFIGURATION SUPABASE
# =============================================================================

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://hxdtaqnfnpzqndhqiopi.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'sb_publishable_LKwjDQ-9Oy9gvpO29YWlCg_vsY7xuyW')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'sb_secret_ijnE_sPpcVJdd5pGLMtg6w_FyHWG46H')

# =============================================================================
# CONFIGURATION TELEGRAM BOT
# =============================================================================

TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', '37641587'))
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '9bce1167e828939f39452795e56202a9')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8588309317:AAHHCc0dRQhQX3awCPRkQK7x4mYwM2syD6U')

# IDs des administrateurs autorisés à utiliser le bot (séparés par virgule)
ADMIN_IDS = [
    int(admin_id.strip()) 
    for admin_id in os.getenv('ADMIN_IDS', '8467461906').split(',') 
    if admin_id.strip().isdigit()
]

# =============================================================================
# CONFIGURATION STREAMING
# =============================================================================

# URL de base pour les liens de streaming (votre domaine Render)
STREAM_BASE_URL = os.getenv('STREAM_BASE_URL', 'https://zeexclub-api.onrender.com')

# Taille des chunks pour le streaming (1 MB)
STREAM_CHUNK_SIZE = 1024 * 1024

# Timeout pour les requêtes de streaming (secondes)
STREAM_TIMEOUT = 30

# =============================================================================
# CONFIGURATION FILEMOON
# =============================================================================

FILEMOON_API_KEY = os.getenv('FILEMOON_API_KEY', '109610tm5s00oygchhhs3u')
FILEMOON_BASE_URL = 'https://api.byse.sx/'

# =============================================================================
# CONFIGURATION DJANGO
# =============================================================================

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'Y7Of_eEWfSPdcd42QGvup-nwXCLR0C2-DRIUFFH-gM_1QHooB6-7y06m6ZeDXIAdtG4')

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'zeexclub-api.onrender.com',
    '.vercel.app',
    '*',  # Temporaire pour le développement
]

# Applications Django installées
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Configuration CORS pour permettre les requêtes depuis le frontend Vercel
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "https://zeexclub.vercel.app",
    "https://*.vercel.app",
]

CORS_ALLOW_ALL_ORIGINS = DEBUG  # En dev uniquement

# Configuration des templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

# Configuration de la base de données (on utilise Supabase, pas SQLite en prod)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Configuration REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Internationalisation
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Fichiers statiques
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Fichiers médias (pour les uploads temporaires si besoin)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Configuration des logs
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
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'zeexclub.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'bot': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'api': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# =============================================================================
# CONFIGURATION SECURITÉ
# =============================================================================

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def validate_config():
    """
    Valide que toutes les configurations critiques sont présentes
    Retourne une liste d'erreurs si des variables manquent
    """
    errors = []
    
    required_vars = [
        ('SUPABASE_URL', SUPABASE_URL),
        ('SUPABASE_KEY', SUPABASE_KEY),
        ('TELEGRAM_API_ID', TELEGRAM_API_ID if TELEGRAM_API_ID != 0 else None),
        ('TELEGRAM_API_HASH', TELEGRAM_API_HASH),
        ('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN),
    ]
    
    for var_name, var_value in required_vars:
        if not var_value:
            errors.append(f"Variable manquante: {var_name}")
    
    if not ADMIN_IDS:
        errors.append("Aucun ADMIN_IDS configuré. Le bot ne sera accessible à personne.")
    
    return errors

def get_supabase_config():
    """
    Retourne la configuration Supabase sous forme de dictionnaire
    """
    return {
        'url': SUPABASE_URL,
        'key': SUPABASE_KEY,
        'service_key': SUPABASE_SERVICE_KEY,
    }

def get_telegram_config():
    """
    Retourne la configuration Telegram sous forme de dictionnaire
    """
    return {
        'api_id': TELEGRAM_API_ID,
        'api_hash': TELEGRAM_API_HASH,
        'bot_token': TELEGRAM_BOT_TOKEN,
        'admin_ids': ADMIN_IDS,
    }

# Point d'entrée pour vérifier la config au démarrage
if __name__ == '__main__':
    errors = validate_config()
    if errors:
        print("❌ Erreurs de configuration:")
        for error in errors:
            print(f"  - {error}")
        exit(1)
    else:
        print("✅ Configuration valide")
