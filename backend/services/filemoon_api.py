# backend/services/filemoon_api.py
"""
API Filemoon pour ZeeXClub
Upload de vidéos vers Filemoon
"""

import logging
import asyncio
import aiohttp
import os
from typing import Optional
from config import FILEMOON_API_KEY

logger = logging.getLogger(__name__)

FILEMOON_BASE_URL = "https://filemoon.sx"
FILEMOON_API_URL = f"{FILEMOON_BASE_URL}/api"

async def upload_to_filemoon_async(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Upload une vidéo sur Filemoon via URL (Remote Upload)
    ⚠️ NE FONCTIONNE PAS avec des URLs de streaming (type API)
    Utiliser uniquement avec des URLs directes (MP4/MKV)
    """
    if not FILEMOON_API_KEY:
        logger.warning("⚠️ FILEMOON_API_KEY non configuré")
        return None
    
    # Payload pour remote upload
    payload = {
        'api_key': FILEMOON_API_KEY,
        'url': video_url
    }
    
    if title:
        payload['title'] = title
    
    try:
        timeout = aiohttp.ClientTimeout(total=600)  # 10 min
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"☁️ Remote upload Filemoon: {video_url[:60]}...")
            
            async with session.post(f"{FILEMOON_API_URL}/upload", data=payload) as response:
                text = await response.text()
                logger.debug(f"Réponse Filemoon: {text[:500]}")
                
                if response.status != 200:
                    logger.error(f"❌ HTTP {response.status}: {text[:500]}")
                    return None
                
                try:
                    data = await response.json()
                except Exception as e:
                    logger.error(f"❌ JSON invalide: {e}")
                    return None
                
                # Vérification statut
                if data.get('status') != 'success':
                    msg = data.get('msg', 'Unknown error')
                    logger.error(f"❌ Erreur API: {msg}")
                    return None
                
                # Extraction file_code
                result = data.get('result', {})
                file_code = result.get('filecode') or result.get('file_code')
                
                if not file_code:
                    logger.error(f"❌ Pas de file_code: {result}")
                    return None
                
                player_url = f"{FILEMOON_BASE_URL}/e/{file_code}"
                logger.info(f"✅ Remote upload OK: {player_url}")
                
                return player_url
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout Filemoon (10min)")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur remote upload: {e}")
        return None


async def upload_file_to_filemoon_async(file_path: str, title: Optional[str] = None) -> Optional[str]:
    """
    Upload un fichier local vers Filemoon (méthode recommandée)
    
    Args:
        file_path: Chemin vers le fichier local
        title: Titre optionnel pour la vidéo
    
    Returns:
        str: URL du player Filemoon ou None
    """
    if not FILEMOON_API_KEY:
        logger.warning("⚠️ FILEMOON_API_KEY non configuré")
        return None
    
    if not os.path.exists(file_path):
        logger.error(f"❌ Fichier introuvable: {file_path}")
        return None
    
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    logger.info(f"📤 Upload fichier vers Filemoon: {file_name} ({file_size / 1024 / 1024:.2f} MB)")
    
    try:
        timeout = aiohttp.ClientTimeout(total=1800)  # 30 min pour gros fichiers
        
        # Préparer le multipart form-data
        data = aiohttp.FormData()
        data.add_field('api_key', FILEMOON_API_KEY)
        
        if title:
            data.add_field('title', title[:100])  # Limiter à 100 caractères
        
        # Ouvrir le fichier en binary
        with open(file_path, 'rb') as f:
            data.add_field('file', f, filename=file_name)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{FILEMOON_API_URL}/upload", data=data) as response:
                    text = await response.text()
                    logger.debug(f"Réponse Filemoon upload: {text[:500]}")
                    
                    if response.status != 200:
                        logger.error(f"❌ HTTP {response.status}: {text[:500]}")
                        return None
                    
                    try:
                        result = await response.json()
                    except Exception as e:
                        logger.error(f"❌ JSON invalide: {e} | Réponse: {text[:200]}")
                        return None
                    
                    # Vérification statut
                    if result.get('status') != 'success':
                        msg = result.get('msg', 'Unknown error')
                        logger.error(f"❌ Erreur API Filemoon: {msg}")
                        return None
                    
                    # Extraction file_code
                    result_data = result.get('result', {})
                    file_code = result_data.get('filecode') or result_data.get('file_code')
                    
                    if not file_code:
                        logger.error(f"❌ Pas de file_code dans: {result_data}")
                        return None
                    
                    player_url = f"{FILEMOON_BASE_URL}/e/{file_code}"
                    logger.info(f"✅ Upload fichier OK: {player_url}")
                    
                    return player_url
                    
    except asyncio.TimeoutError:
        logger.error("❌ Timeout Filemoon upload (30min)")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur upload fichier Filemoon: {e}", exc_info=True)
        return None


def upload_to_filemoon_sync(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """Version synchrone pour remote upload"""
    try:
        return asyncio.run(upload_to_filemoon_async(video_url, title))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(upload_to_filemoon_async(video_url, title))
        finally:
            loop.close()


def upload_file_to_filemoon_sync(file_path: str, title: Optional[str] = None) -> Optional[str]:
    """Version synchrone pour upload fichier local"""
    try:
        return asyncio.run(upload_file_to_filemoon_async(file_path, title))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(upload_file_to_filemoon_async(file_path, title))
        finally:
            loop.close()
