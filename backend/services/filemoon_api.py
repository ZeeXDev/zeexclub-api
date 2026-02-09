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

# ✅ URLs corrigées selon la doc
FILEMOON_UPLOAD_URL = "https://api.byse.sx/api/upload/url"
FILEMOON_FILE_INFO_URL = "https://api.byse.sx/api/file/info"
FILEMOON_STATUS_URL = "https://api.byse.sx/api/account/stats"

async def upload_to_filemoon_async(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Upload une vidéo sur Filemoon via URL (Remote Upload)
    
    Args:
        video_url: URL directe de la vidéo (lien ZeeX/stream)
        title: Titre optionnel pour le fichier
    
    Returns:
        str: URL Filemoon de la vidéo ou None si échec
    """
    if not FILEMOON_API_KEY:
        logger.warning("⚠️ FILEMOON_API_KEY non configuré, upload ignoré")
        return None
    
    # ✅ Payload corrigé selon la doc
    payload = {
        'key': FILEMOON_API_KEY,  # 'key' pas 'api_key'
        'url': video_url
    }
    
    if title:
        payload['title'] = title
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=300)  # 5 min pour l'upload initial
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"☁️ Upload Filemoon démarré pour: {video_url[:50]}...")
            
            # ✅ POST avec JSON payload
            async with session.post(FILEMOON_UPLOAD_URL, json=payload, headers=headers) as response:
                text = await response.text()
                logger.debug(f"Réponse Filemoon: {text}")
                
                if response.status != 200:
                    logger.error(f"❌ Erreur HTTP {response.status}: {text[:500]}")
                    return None
                
                try:
                    data = await response.json()
                except:
                    logger.error(f"❌ Réponse JSON invalide: {text[:500]}")
                    return None
                
                # ✅ Vérification du status selon la doc
                if not data.get('status'):  # status: true/false
                    logger.error(f"❌ Erreur API Filemoon: {data.get('msg', 'Unknown error')}")
                    return None
                
                # ✅ Extraction correcte du résultat
                result = data.get('result', {})
                filecode = result.get('filecode')  # 'filecode' pas 'file_code'
                
                if not filecode:
                    logger.error(f"❌ Pas de filecode dans la réponse: {result}")
                    return None
                
                filemoon_url = f"https://filemoon.sx/e/{filecode}"
                logger.info(f"✅ Upload Filemoon accepté: {filemoon_url}")
                logger.info(f"⏳ Statut: {result.get('status')} (peut nécessiter du temps de traitement)")
                
                # Optionnel: attendre que le fichier soit prêt
                # await wait_for_file_ready(filecode)
                
                return filemoon_url
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout lors de l'upload Filemoon")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur upload Filemoon: {e}")
        return None


async def check_file_status(filecode: str) -> Optional[dict]:
    """
    Vérifie le statut d'un fichier sur Filemoon
    
    Args:
        filecode: Code du fichier Filemoon
    
    Returns:
        dict: Informations du fichier ou None
    """
    if not FILEMOON_API_KEY:
        return None
    
    params = {
        'key': FILEMOON_API_KEY,
        'filecode': filecode
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FILEMOON_FILE_INFO_URL, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get('status'):
                    return data.get('result')
                return None
                
    except Exception as e:
        logger.error(f"❌ Erreur vérification statut: {e}")
        return None


async def wait_for_file_ready(filecode: str, max_attempts: int = 10, delay: int = 5) -> bool:
    """
    Attend que le fichier soit prêt (status != processing)
    
    Args:
        filecode: Code du fichier
        max_attempts: Nombre max de tentatives
        delay: Délai entre chaque tentative (secondes)
    
    Returns:
        bool: True si prêt, False si timeout
    """
    for attempt in range(max_attempts):
        info = await check_file_status(filecode)
        
        if not info:
            logger.warning(f"⚠️ Tentative {attempt+1}: Impossible de récupérer le statut")
            await asyncio.sleep(delay)
            continue
        
        status = info.get('status')
        logger.info(f"⏳ Tentative {attempt+1}/{max_attempts}: Statut = {status}")
        
        if status == 'active':  # ✅ Fichier prêt
            logger.info(f"✅ Fichier prêt: {info.get('url')}")
            return True
        
        if status == 'error':  # ❌ Erreur de traitement
            logger.error(f"❌ Erreur de traitement Filemoon")
            return False
        
        # 'processing' ou autres = attendre
        await asyncio.sleep(delay)
    
    logger.warning(f"⏰ Timeout en attendant le fichier {filecode}")
    return False


def upload_to_filemoon_sync(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """Version synchrone de l'upload Filemoon"""
    return asyncio.run(upload_to_filemoon_async(video_url, title))


async def check_filemoon_status() -> bool:
    """Vérifie si l'API Filemoon est accessible"""
    if not FILEMOON_API_KEY:
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {'key': FILEMOON_API_KEY, 'fld_id': '0'}
            async with session.get(FILEMOON_STATUS_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('status') == True
                return False
    except:
        return False
