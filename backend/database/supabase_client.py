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

    # Debug - Voir quelle clé est utilisée
    logger.info(f"SUPABASE_URL from settings: {settings.SUPABASE_URL}")
    logger.info(f"SUPABASE_KEY length: {len(settings.SUPABASE_KEY) if settings.SUPABASE_KEY else 0}")
    logger.info(f"SUPABASE_SERVICE_KEY length: {len(settings.SUPABASE_SERVICE_KEY) if settings.SUPABASE_SERVICE_KEY else 0}")

    # Déterminer quelle clé utiliser (priorité à SERVICE_KEY si définie)
    key_to_use = settings.SUPABASE_SERVICE_KEY if settings.SUPABASE_SERVICE_KEY else settings.SUPABASE_KEY

    if not key_to_use:
        raise ValueError("Aucune clé Supabase définie (ni SUPABASE_SERVICE_KEY ni SUPABASE_KEY)")

    # Vérifier que c'est la bonne clé
    if "service_role" not in key_to_use:
        logger.warning("⚠️ La clé ne semble pas être une service_role key !")

    try:
        # ⚠️ Arguments positionnels pour create_client
        supabase = create_client(settings.SUPABASE_URL, key_to_use)

        # Test de connexion simple, sécurisé
        try:
            response = supabase.table("shows").select("count", count="exact").limit(1).execute()
            count_shows = getattr(response, "count", "N/A")
            logger.info(f"✅ Connexion Supabase établie - {count_shows} shows dans la base")
        except Exception as e:
            logger.warning(f"⚠️ Connexion OK mais test table 'shows' échoué: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur connexion Supabase: {str(e)}")
        logger.error(f"URL utilisée: {settings.SUPABASE_URL}")
        logger.error(f"Clé utilisée (début): {key_to_use[:50]}...")
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