"""
Client Supabase - Gestion de la connexion PostgreSQL
"""

import logging
from typing import Optional
from supabase import create_client, Client
from postgrest.exceptions import APIError

from config import settings

logger = logging.getLogger(__name__)

# Client Supabase global
supabase: Optional[Client] = None


async def init_supabase():
    """Initialise la connexion Supabase"""
    global supabase
    
    try:
        supabase = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
        )
        
        # Test de connexion
        response = supabase.table("shows").select("count", count="exact").limit(1).execute()
        logger.info(f"✅ Connexion Supabase établie - Tables accessibles")
        
    except Exception as e:
        logger.error(f"❌ Erreur connexion Supabase: {str(e)}")
        raise


async def close_supabase():
    """Ferme la connexion Supabase"""
    global supabase
    supabase = None
    logger.info("🔌 Connexion Supabase fermée")


def get_supabase() -> Client:
    """Retourne l'instance client Supabase"""
    if supabase is None:
        raise RuntimeError("Supabase n'est pas initialisé. Appelez init_supabase() d'abord.")
    return supabase


class DatabaseError(Exception):
    """Exception personnalisée pour les erreurs DB"""
    pass


def handle_db_error(error: Exception, operation: str = "opération"):
    """
    Gestion centralisée des erreurs DB
    """
    if isinstance(error, APIError):
        logger.error(f"Erreur API Supabase ({operation}): {error.message}")
        if "23505" in str(error):  # Unique violation
            raise DatabaseError("Conflit: cet élément existe déjà")
        elif "23503" in str(error):  # Foreign key violation
            raise DatabaseError("Référence invalide: l'élément parent n'existe pas")
        else:
            raise DatabaseError(f"Erreur base de données: {error.message}")
    else:
        logger.error(f"Erreur inattendue ({operation}): {str(error)}")
        raise DatabaseError(f"Erreur lors de {operation}")
