# backend/services/stream_handler.py
"""
Gestionnaire de streaming pour ZeeXClub
Génération des liens streamables et proxy de contenu
"""

import hashlib
import logging
from typing import Optional
from database.supabase_client import supabase_manager
from config import STREAM_BASE_URL

logger = logging.getLogger(__name__)

def generate_stream_link(file_id: str) -> str:
    """
    Génère un lien de streaming unique à partir d'un file_id Telegram
    
    Le lien est de la forme: https://votre-api.com/stream/abc123...
    
    Args:
        file_id: file_id unique de Telegram
    
    Returns:
        str: URL complète de streaming
    """
    # Générer un hash unique déterministe (même file_id = même hash)
    unique_id = hashlib.md5(file_id.encode('utf-8')).hexdigest()
    
    # Vérifier si le mapping existe déjà
    existing = supabase_manager.get_stream_mapping(unique_id)
    
    if not existing:
        # Créer le mapping en base
        try:
            supabase_manager.create_stream_mapping(unique_id, file_id)
            logger.info(f"✅ Mapping créé: {unique_id} -> {file_id[:20]}...")
        except Exception as e:
            logger.error(f"❌ Erreur création mapping: {e}")
            # On continue quand même, le lien sera fonctionnel
    
    # Retourner l'URL complète
    return f"{STREAM_BASE_URL}/stream/{unique_id}"


def get_file_id_from_stream_id(stream_id: str) -> Optional[str]:
    """
    Récupère le file_id Telegram depuis un ID de stream
    
    Args:
        stream_id: ID unique du stream (hash)
    
    Returns:
        str: file_id Telegram ou None si introuvable
    """
    mapping = supabase_manager.get_stream_mapping(stream_id)
    
    if mapping:
        return mapping.get('file_id')
    
    logger.warning(f"⚠️ Aucun mapping trouvé pour stream_id: {stream_id}")
    return None


def validate_stream_token(token: str) -> bool:
    """
    Valide un token de streaming (pour futures fonctionnalités de sécurité)
    
    Args:
        token: Token à valider
    
    Returns:
        bool: True si valide
    """
    # Pour l'instant, simple vérification de format
    if not token or len(token) != 32:
        return False
    
    # Vérifier que c'est bien un hexadécimal
    try:
        int(token, 16)
        return True
    except ValueError:
        return False
