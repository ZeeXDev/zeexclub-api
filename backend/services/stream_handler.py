"""
Gestion du streaming Telegram
Récupération des fichiers et streaming avec support Range Requests
"""

import logging
import asyncio
from typing import Optional, Dict, Any, AsyncGenerator
from io import BytesIO

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, FileIdInvalid, MessageNotModified

from config import settings

logger = logging.getLogger(__name__)


class StreamHandler:
    """
    Gestionnaire de streaming pour fichiers Telegram
    """
    
    def __init__(self):
        self.bot: Optional[Client] = None
        self.chunk_size = settings.STREAM_BUFFER_SIZE  # 256KB par défaut
    
    def set_bot(self, bot: Client):
        """Définit l'instance du bot Pyrogram"""
        self.bot = bot
    
    async def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un fichier sans le télécharger
        
        Returns:
            Dict avec file_size, mime_type, etc.
        """
        if not self.bot:
            logger.error("Bot non initialisé dans StreamHandler")
            return None
        
        try:
            # Récupération des messages contenant ce file_id
            # Note: Pyrogram ne permet pas de get_file_info directement sans message
            # On va utiliser une méthode alternative
            
            # Pour l'instant, on retourne des infos de base
            # Dans une implémentation complète, il faudrait stocker ces infos en DB
            
            return {
                "file_id": file_id,
                "file_size": 0,  # À récupérer depuis la DB
                "mime_type": "video/mp4",
                "supports_streaming": True
            }
            
        except Exception as e:
            logger.error(f"Erreur get_file_info: {e}")
            return None
    
    async def stream_file(
        self, 
        file_id: str, 
        start: int = 0, 
        end: Optional[int] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Générateur de streaming pour un fichier Telegram
        
        Yields:
            Chunks de bytes pour le streaming HTTP
        """
        if not self.bot:
            raise RuntimeError("Bot non initialisé")
        
        try:
            # Téléchargement par chunks
            # Pyrogram ne supporte pas le streaming natif par range,
            # donc on simule en téléchargeant et yieldant par morceaux
            
            # NOTE: Implémentation simplifiée
            # En production, il faudrait utiliser MTProto proxy 
            # ou télécharger le fichier complet puis streamer
            
            downloaded = 0
            current_pos = start
            
            # Cette méthode est un placeholder - l'implémentation réelle
            # nécessite une gestion plus complexe des fichiers Telegram
            
            # Méthode alternative: téléchargement complet puis découpage
            # (pas optimal pour les gros fichiers)
            
            file_path = await self.bot.download_media(
                file_id,
                in_memory=True  # Télécharge en mémoire
            )
            
            if isinstance(file_path, BytesIO):
                file_path.seek(start)
                
                while True:
                    chunk = file_path.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    # Vérifier si on a atteint la fin demandée
                    if end and current_pos + len(chunk) > end:
                        remaining = end - current_pos + 1
                        chunk = chunk[:remaining]
                        yield chunk
                        break
                    
                    yield chunk
                    current_pos += len(chunk)
                    
                    # Petite pause pour ne pas bloquer
                    await asyncio.sleep(0)
            
        except FloodWait as e:
            logger.warning(f"FloodWait streaming: {e.value}s")
            await asyncio.sleep(e.value)
            raise
        except FileIdInvalid:
            logger.error(f"File ID invalide: {file_id}")
            raise
        except Exception as e:
            logger.error(f"Erreur streaming {file_id}: {e}")
            raise
    
    async def get_download_link(self, file_id: str) -> Optional[str]:
        """
        Génère un lien de téléchargement temporaire
        (Si possible avec Pyrogram)
        """
        # Pyrogram ne génère pas de liens directs publics
        # Cette fonction retourne None, le streaming se fait via notre proxy
        return None
    
    async def get_thumbnail(self, file_id: str) -> Optional[bytes]:
        """
        Extrait une miniature de la vidéo
        """
        # À implémenter avec ffmpeg ou similar
        return None


# Instance globale
stream_handler = StreamHandler()


async def get_stream_handler() -> StreamHandler:
    return stream_handler
