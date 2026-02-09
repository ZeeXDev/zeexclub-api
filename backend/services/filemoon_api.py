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

# ✅ URLs corrigées selon la documentation Filemoon officielle
FILEMOON_API_BASE = "https://api.byse.sx/api"
FILEMOON_UPLOAD_URL = f"{FILEMOON_API_BASE}/upload/url"  # Remote upload via URL
FILEMOON_UPLOAD_SERVER_URL = f"{FILEMOON_API_BASE}/upload/server"  # Upload direct
FILEMOON_FILE_INFO_URL = f"{FILEMOON_API_BASE}/file/info"
FILEMOON_FILE_LIST_URL = f"{FILEMOON_API_BASE}/file/list"
FILEMOON_ACCOUNT_INFO_URL = f"{FILEMOON_API_BASE}/account/info"

async def upload_to_filemoon_async(video_url: str, title: Optional[str] = None, 
                                   folder_id: Optional[str] = None) -> Optional[str]:
    """
    Upload une vidéo sur Filemoon via URL (Remote Upload)
    
    Args:
        video_url: URL directe de la vidéo (lien ZeeX/stream)
        title: Titre optionnel pour le fichier
        folder_id: ID du dossier Filemoon (optionnel)
    
    Returns:
        str: URL Filemoon de la vidéo ou None si échec
    """
    if not FILEMOON_API_KEY:
        logger.warning("⚠️ FILEMOON_API_KEY non configuré, upload ignoré")
        return None
    
    # Payload selon la doc Filemoon
    payload = {
        'key': FILEMOON_API_KEY,  # 'key' pas 'api_key'
        'url': video_url
    }
    
    if title:
        payload['title'] = title
    
    if folder_id:
        payload['fld_id'] = folder_id
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=300)  # 5 min pour l'upload initial
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"☁️ Upload Filemoon démarré pour: {video_url[:50]}...")
            
            async with session.post(FILEMOON_UPLOAD_URL, json=payload, headers=headers) as response:
                text = await response.text()
                logger.debug(f"Réponse Filemoon (status {response.status}): {text[:500]}")
                
                if response.status != 200:
                    logger.error(f"❌ Erreur HTTP {response.status}: {text[:500]}")
                    return None
                
                try:
                    data = await response.json()
                except Exception as e:
                    logger.error(f"❌ Réponse JSON invalide: {e} - Texte: {text[:500]}")
                    return None
                
                # Vérification du status
                if not data.get('status'):  # status: true/false
                    error_msg = data.get('msg', 'Unknown error')
                    error_code = data.get('code', 'Unknown code')
                    logger.error(f"❌ Erreur API Filemoon: {error_msg} (code: {error_code})")
                    return None
                
                # Extraction du résultat
                result = data.get('result', {})
                filecode = result.get('filecode')  # 'filecode' pas 'file_code'
                player_url = result.get('player_url')  # URL directe player si dispo
                
                if not filecode:
                    logger.error(f"❌ Pas de filecode dans la réponse: {result}")
                    return None
                
                # Construire l'URL player
                if player_url:
                    filemoon_url = player_url
                else:
                    filemoon_url = f"https://filemoon.sx/e/{filecode}"
                
                logger.info(f"✅ Upload Filemoon accepté: {filemoon_url}")
                logger.info(f"⏳ Statut traitement: {result.get('status', 'unknown')}")
                
                return filemoon_url
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout lors de l'upload Filemoon (5min)")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"❌ Erreur réseau Filemoon: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur inattendue upload Filemoon: {e}")
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
                    logger.warning(f"⚠️ Statut HTTP {response.status} lors vérification fichier")
                    return None
                
                try:
                    data = await response.json()
                except:
                    return None
                
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
        bool: True si prêt, False si timeout ou erreur
    """
    for attempt in range(max_attempts):
        info = await check_file_status(filecode)
        
        if not info:
            logger.warning(f"⚠️ Tentative {attempt+1}/{max_attempts}: Impossible de récupérer le statut")
            await asyncio.sleep(delay)
            continue
        
        status = info.get('status')
        logger.info(f"⏳ Tentative {attempt+1}/{max_attempts}: Statut = {status}")
        
        if status == 'active':  # Fichier prêt
            logger.info(f"✅ Fichier prêt: {info.get('url', 'URL non dispo')}")
            return True
        
        if status == 'error':  # Erreur de traitement
            logger.error(f"❌ Erreur de traitement Filemoon pour {filecode}")
            return False
        
        if status == 'deleted':  # Fichier supprimé
            logger.error(f"❌ Fichier supprimé sur Filemoon: {filecode}")
            return False
        
        # 'processing', 'pending', etc. = attendre
        await asyncio.sleep(delay)
    
    logger.warning(f"⏰ Timeout en attendant le fichier {filecode} après {max_attempts} tentatives")
    return False


def upload_to_filemoon_sync(video_url: str, title: Optional[str] = None,
                            folder_id: Optional[str] = None) -> Optional[str]:
    """Version synchrone de l'upload Filemoon"""
    try:
        return asyncio.run(upload_to_filemoon_async(video_url, title, folder_id))
    except RuntimeError:
        # Si déjà dans un event loop (ex: Django), créer un nouveau
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(upload_to_filemoon_async(video_url, title, folder_id))
        finally:
            loop.close()


async def get_account_info() -> Optional[dict]:
    """
    Récupère les informations du compte Filemoon
    
    Returns:
        dict: Infos compte ou None
    """
    if not FILEMOON_API_KEY:
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {'key': FILEMOON_API_KEY}
            async with session.get(FILEMOON_ACCOUNT_INFO_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status'):
                        return data.get('result')
                return None
    except Exception as e:
        logger.error(f"❌ Erreur récupération infos compte: {e}")
        return None


async def list_files(folder_id: str = '0', page: int = 1) -> Optional[list]:
    """
    Liste les fichiers dans un dossier Filemoon
    
    Args:
        folder_id: ID du dossier (0 = racine)
        page: Numéro de page
    
    Returns:
        list: Liste des fichiers ou None
    """
    if not FILEMOON_API_KEY:
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                'key': FILEMOON_API_KEY,
                'fld_id': folder_id,
                'page': page
            }
            async with session.get(FILEMOON_FILE_LIST_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status'):
                        return data.get('result', {}).get('files', [])
                return None
    except Exception as e:
        logger.error(f"❌ Erreur liste fichiers: {e}")
        return None


async def check_filemoon_status() -> bool:
    """Vérifie si l'API Filemoon est accessible et la clé valide"""
    if not FILEMOON_API_KEY:
        return False
    
    try:
        info = await get_account_info()
        return info is not None
    except:
        return False
