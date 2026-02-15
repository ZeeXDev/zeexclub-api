"""
Configuration globale ZeeXClub
Variables d'environnement et constantes
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Configuration principale de l'application"""
    
    # Application
    APP_NAME: str = "ZeeXClub API"
    DEBUG: bool = Field(default=False, env="DEBUG")
    VERSION: str = "1.0.0"
    FRONTEND_URL: str = Field(default="http://zeexclub.vercel.app", env="FRONTEND_URL")
    
    # Sécurité
    SECRET_KEY: str = Field(default="Y7Of_eEWfSPdcd42QGvup-nwXCLR0C2-DRIUFFH-gM_1QHooB6-7y06m6ZeDXIAdtG4", env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Supabase
    SUPABASE_URL: str = Field(default="https://hxdtaqnfnpzqndhqiopi.supabase.co", env="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh4ZHRhcW5mbnB6cW5kaHFpb3BpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDU3MTkwMiwiZXhwIjoyMDg2MTQ3OTAyfQ.JSekTT6re-zzyf4effXCfqZccAe_d2bmnQ6bVeH45aM", env="SUPABASE_KEY")
    SUPABASE_SERVICE_KEY: str = Field(default="sb_secret_ijnE_sPpcVJdd5pGLMtg6w_FyHWG46H", env="SUPABASE_SERVICE_KEY")
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(default="8588309317:AAHHCc0dRQhQX3awCPRkQK7x4mYwM2syD6U", env="TELEGRAM_BOT_TOKEN")
    TELEGRAM_API_ID: int = Field(default=37641587, env="TELEGRAM_API_ID")
    TELEGRAM_API_HASH: str = Field(default="9bce1167e828939f39452795e56202a9", env="TELEGRAM_API_HASH")
    ADMIN_USER_IDS: list = Field(default=[8467461906], env="ADMIN_USER_IDS")
    
    # TMDB
    TMDB_API_KEY: str = Field(default="f2bed62b5977bce26540055276d0046c", env="TMDB_API_KEY")
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL: str = "https://image.tmdb.org/t/p/original"
    
    # Filemoon
    FILEMOON_API_KEY: str = Field(default="109610tm5s00oygchhhs3u", env="FILEMOON_API_KEY")
    FILEMOON_BASE_URL: str = "https://filemoon.sx/api"
    FILEMOON_PLAYER_URL: str = "https://filemoon.sx/e/"
    
    # Redis (Cache)
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # Upload & Fichiers
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    CHUNK_SIZE: int = 1024 * 1024  # 1MB chunks
    
    # Streaming
    STREAM_BUFFER_SIZE: int = 256 * 1024  # 256KB
    STREAM_TIMEOUT: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Retourne une instance singleton des settings"""
    return Settings()


# Instance globale
settings = get_settings()

# Validation des variables critiques au démarrage
def validate_config():
    """Valide que toutes les configurations critiques sont présentes"""
    required_vars = [
        ("SUPABASE_URL", settings.SUPABASE_URL),
        ("SUPABASE_KEY", settings.SUPABASE_KEY),
        ("TELEGRAM_BOT_TOKEN", settings.TELEGRAM_BOT_TOKEN),
        ("TMDB_API_KEY", settings.TMDB_API_KEY),
        ("FILEMOON_API_KEY", settings.FILEMOON_API_KEY),
    ]
    
    missing = [name for name, value in required_vars if not value]
    
    if missing:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
    
    # Parse ADMIN_USER_IDS si string
    if isinstance(settings.ADMIN_USER_IDS, str):
        settings.ADMIN_USER_IDS = [
            int(x.strip()) 
            for x in settings.ADMIN_USER_IDS.split(",") 
            if x.strip()
        ]
    
    return True


# Constantes métier
ALLOWED_VIDEO_TYPES = ['movie', 'series']
ALLOWED_SERVER_NAMES = ['filemoon', 'telegram']
TMDB_MEDIA_TYPES = ['movie', 'tv']

# Regex pour parsing S01E01, Episode 1, etc.
SEASON_EPISODE_PATTERNS = [
    r'[Ss](\d+)[Ee](\d+)',           # S01E01, s1e1
    r'[Ss]eason\s*(\d+).*?[Ee]pisode\s*(\d+)',  # Season 1 Episode 1
    r'[Ee]pisode\s*(\d+)',            # Episode 1 (saison 1 par défaut)
    r'(\d+)x(\d+)',                   # 1x01
    r'[Ee](\d+)',                     # E01
]

# Messages bot
BOT_MESSAGES = {
    'welcome': """
🎬 **Bienvenue sur ZeeXClub Admin Bot**

Commandes disponibles:
/create <nom> - Créer un nouveau film/série
/add - Ajouter un épisode (envoyer vidéo avec caption S01E01)
/addf - Créer un sous-dossier/saison
/view <id> - Voir l'état d'un show
/docs - Lister tous les shows
/done - Finaliser l'upload vers Filemoon
/help - Aide détaillée
    """,
    'create_start': "🔍 Recherche sur TMDB...",
    'create_success': "✅ Show créé avec succès!\nID: `{show_id}`\nTitre: {title}\nType: {type}",
    'create_multiple': "Plusieurs résultats trouvés. Choisissez:",
    'add_waiting': "📤 Envoyez la vidéo avec caption (ex: S01E01 ou Episode 1)",
    'add_received': "✅ Vidéo reçue!\nFile ID: `{file_id}`\nCaption: {caption}",
    'addf_prompt': "Choisissez le type de dossier:",
    'done_start': "🚀 Début de l'upload vers Filemoon...",
    'done_progress': "⏳ Upload en cours... {percent}%",
    'done_success': "✅ Upload terminé!\nFilemoon Code: `{file_code}`\nLien: {link}",
    'error_generic': "❌ Une erreur est survenue: {error}",
    'error_not_admin': "⛔ Vous n'êtes pas autorisé à utiliser ce bot.",
    'error_no_show': "❌ Show non trouvé. Utilisez /create d'abord.",
}
