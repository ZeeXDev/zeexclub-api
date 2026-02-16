"""
Configuration globale ZeeXClub
Variables d'environnement uniquement - PAS DE HARDCODED SECRETS
"""

import os
import base64
import json
from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Configuration principale - TOUT vient des variables d'environnement"""
    
    # Application
    APP_NAME: str = "ZeeXClub API"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Sécurité - OBLIGATOIRE
    SECRET_KEY: str = Field(..., min_length=32, description="JWT secret key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Supabase - OBLIGATOIRE
    SUPABASE_URL: str = Field(..., description="URL Supabase project")
    SUPABASE_KEY: str = Field(..., description="Service role key (NOT anon!)")
    
    # Telegram Bot - OBLIGATOIRE
    TELEGRAM_BOT_TOKEN: str = Field(...)
    TELEGRAM_API_ID: int = Field(...)
    TELEGRAM_API_HASH: str = Field(...)
    ADMIN_USER_IDS: List[int] = Field(default_factory=list)
    TELEGRAM_SESSION_STRING: Optional[str] = Field(default=None, description="Session string pour Pyrogram")
    
    # TMDB - OBLIGATOIRE
    TMDB_API_KEY: str = Field(...)
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL: str = "https://image.tmdb.org/t/p/original"
    
    # Filemoon - OBLIGATOIRE
    FILEMOON_API_KEY: str = Field(...)
    FILEMOON_BASE_URL: str = "https://filemoon.sx/api"
    FILEMOON_PLAYER_URL: str = "https://filemoon.sx/e/"
    
    # Redis (optionnel)
    REDIS_URL: Optional[str] = None
    
    # Upload & Fichiers
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    CHUNK_SIZE: int = 1024 * 1024  # 1MB chunks
    
    # Streaming
    STREAM_BUFFER_SIZE: int = 256 * 1024  # 256KB
    STREAM_TIMEOUT: int = 300  # 5 minutes
    
    @validator('SUPABASE_KEY')
    def validate_supabase_key(cls, v):
        """Vérifie que c'est bien la service_role key en décodant le JWT"""
        try:
            # Split JWT et décoder payload
            parts = v.split('.')
            if len(parts) != 3:
                raise ValueError("Format JWT invalide")
            
            # Ajouter padding si nécessaire
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            decoded = base64.b64decode(payload)
            data = json.loads(decoded)
            
            if data.get('role') != 'service_role':
                raise ValueError(
                    "SUPABASE_KEY doit être la clé 'service_role', pas 'anon' ! "
                    "Supabase > Settings > API > service_role secret"
                )
            return v
        except Exception as e:
            if 'service_role' in str(e):
                raise
            # Si le décodage échoue, on accepte quand même (fallback)
            return v
    
    @validator('ADMIN_USER_IDS', pre=True)
    def parse_admin_ids(cls, v):
        """Parse les IDs admin depuis string ou liste"""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Singleton des settings"""
    return Settings()


# Instance globale
settings = get_settings()


def validate_config():
    """Valide la configuration au démarrage"""
    required = [
        "SUPABASE_URL",
        "SUPABASE_KEY", 
        "SECRET_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TMDB_API_KEY",
        "FILEMOON_API_KEY"
    ]
    
    missing = [r for r in required if not getattr(settings, r)]
    
    if missing:
        raise ValueError(f"Variables manquantes: {', '.join(missing)}")
    
    return True


# Constantes métier (pas de secrets ici)
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
