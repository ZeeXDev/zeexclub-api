# REMPLACER TOUT LE FICHIER par :

import logging
import asyncio
import aiohttp
from typing import Optional
from config import FILEMOON_API_KEY

logger = logging.getLogger(__name__)

# ✅ URLs CORRECTES selon doc Filemoon officielle
FILEMOON_BASE_URL = "https://filemoon.sx"
FILEMOON_API_URL = f"{FILEMOON_BASE_URL}/api"

async def upload_to_filemoon_async(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Upload une vidéo sur Filemoon via URL (Remote Upload)
    """
    if not FILEMOON_API_KEY:
        logger.warning("⚠️ FILEMOON_API_KEY non configuré")
        return None
    
    # ✅ Payload correct selon doc Filemoon
    payload = {
        'api_key': FILEMOON_API_KEY,  # ✅ 'api_key' pas 'key'
        'url': video_url
    }
    
    if title:
        payload['title'] = title
    
    try:
        timeout = aiohttp.ClientTimeout(total=600)  # 10 min pour gros fichiers
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"☁️ Upload Filemoon: {video_url[:60]}...")
            
            # ✅ Endpoint correct : /api/upload (pas /api/upload/url)
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
                
                # ✅ Vérification statut Filemoon
                if data.get('status') != 'success':
                    msg = data.get('msg', 'Unknown error')
                    logger.error(f"❌ Erreur API: {msg}")
                    return None
                
                # ✅ Extraction file_code
                result = data.get('result', {})
                file_code = result.get('filecode') or result.get('file_code')
                
                if not file_code:
                    logger.error(f"❌ Pas de file_code: {result}")
                    return None
                
                # ✅ URL player Filemoon
                player_url = f"{FILEMOON_BASE_URL}/e/{file_code}"
                logger.info(f"✅ Upload OK: {player_url}")
                
                return player_url
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout Filemoon (10min)")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur upload: {e}")
        return None


def upload_to_filemoon_sync(video_url: str, title: Optional[str] = None) -> Optional[str]:
    """Version synchrone"""
    try:
        return asyncio.run(upload_to_filemoon_async(video_url, title))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(upload_to_filemoon_async(video_url, title))
        finally:
            loop.close()
