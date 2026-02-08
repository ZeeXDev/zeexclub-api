# backend/services/filemoon_api.py
"""
Intégration API Filemoon pour backup des vidéos
Upload automatique des fichiers vers Filemoon
"""

import os
import logging
import asyncio
import aiohttp
from typing import Optional
from config import FILEMOON_API_KEY

logger = logging.getLogger(__name__)

FILEMOON_UPLOAD_URL = "https://filemoon.sx/api/upload"
FILEMOON_STATUS_URL = "https://filemoon.sx/api/folder/list"

async def upload_to_filemoon_async(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Upload une vidéo sur Filemoon de manière asynchrone
    
    Args:
        video_url: URL directe de la vidéo (lien ZeeX/stream)
        title: Titre optionnel pour le fichier
    
    Returns:
        str: URL Filemoon de la vidéo ou None si échec
    """
    if not FILEMOON_API_KEY:
        logger.warning("⚠️ FILEMOON_API_KEY non configuré, upload ignoré")
        return None
    
    params = {
        'api_key': FILEMOON_API_KEY,
        'url': video_url
    }
    
    if title:
        params['title'] = title
    
    try:
        timeout = aiohttp.ClientTimeout(total=600)  # 10 minutes timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"☁️ Upload Filemoon démarré pour: {video_url[:50]}...")
            
            async with session.post(FILEMOON_UPLOAD_URL, data=params) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"❌ Erreur HTTP {response.status}: {text[:200]}")
                    return None
                
                data = await response.json()
                
                if data.get('status') != 'success':
                    logger.error(f"❌ Erreur API Filemoon: {data.get('msg', 'Unknown error')}")
                    return None
                
                # Extraire l'URL du player
                file_code = data.get('file_code')
                if not file_code:
                    logger.error("❌ Pas de file_code dans la réponse Filemoon")
                    return None
                
                filemoon_url = f"https://filemoon.sx/e/{file_code}"
                logger.info(f"✅ Upload Filemoon réussi: {filemoon_url}")
                
                return filemoon_url
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout lors de l'upload Filemoon (10min)")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur upload Filemoon: {e}")
        return None


def upload_to_filemoon_sync(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Version synchrone de l'upload Filemoon
    
    Args:
        video_url: URL de la vidéo
        title: Titre optionnel
    
    Returns:
        str: URL Filemoon ou None
    """
    return asyncio.run(upload_to_filemoon_async(video_url, title))


async def check_filemoon_status() -> bool:
    """
    Vérifie si l'API Filemoon est accessible
    
    Returns:
        bool: True si OK
    """
    if not FILEMOON_API_KEY:
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': FILEMOON_API_KEY, 'fld_id': '0'}
            async with session.get(FILEMOON_STATUS_URL, params=params) as response:
                return response.status == 200
    except:
        return False
