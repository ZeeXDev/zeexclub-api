"""
Intégration API Filemoon.sx
Upload et gestion des vidéos
"""

import logging
import asyncio
from typing import Optional, Dict, Any
import httpx
import json

from config import settings

logger = logging.getLogger(__name__)


class FilemoonAPI:
    """Client API Filemoon"""
    
    def __init__(self):
        self.api_key = settings.FILEMOON_API_KEY
        self.base_url = settings.FILEMOON_BASE_URL
        self.player_url = settings.FILEMOON_PLAYER_URL
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout pour uploads
    
    async def close(self):
        await self.client.aclose()
    
    def _build_url(self, action: str, **params) -> str:
        """Construit l'URL API"""
        url = f"{self.base_url}/{self.api_key}/{action}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url += f"?{query}"
        return url
    
    async def upload_remote(self, remote_url: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload une vidéo via URL distante (remote upload)
        
        Args:
            remote_url: URL directe de la vidéo
            title: Titre optionnel
        
        Returns:
            Dict avec status, file_code, etc.
        """
        try:
            logger.info(f"📤 Début upload Filemoon: {title or remote_url[:50]}...")
            
            params = {"url": remote_url}
            if title:
                params["title"] = title
            
            url = self._build_url("upload", **params)
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "success":
                result = data.get("result", {})
                file_code = result.get("filecode")
                
                logger.info(f"✅ Upload Filemoon réussi: {file_code}")
                
                return {
                    "success": True,
                    "file_code": file_code,
                    "file_id": result.get("fileid"),
                    "player_url": f"{self.player_url}{file_code}",
                    "embed_url": f"{self.player_url}{file_code}",
                    "download_url": result.get("download_url"),
                    "status": "completed"
                }
            else:
                error_msg = data.get("msg", "Erreur inconnue")
                logger.error(f"❌ Erreur Filemoon upload: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "status": "failed"
                }
                
        except httpx.HTTPError as e:
            logger.error(f"❌ Erreur HTTP Filemoon: {e}")
            return {
                "success": False,
                "error": f"Erreur HTTP: {str(e)}",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"❌ Erreur Filemoon: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    async def check_status(self, file_code: str) -> Dict[str, Any]:
        """
        Vérifie le statut d'un fichier (encodage, etc.)
        """
        try:
            url = self._build_url("file_info", file=file_code)
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "success":
                result = data.get("result", {})
                return {
                    "success": True,
                    "status": result.get("status"),  # active, processing, etc.
                    "file_size": result.get("size"),
                    "duration": result.get("duration"),
                    "views": result.get("views", 0),
                    "is_active": result.get("status") == "active"
                }
            else:
                return {
                    "success": False,
                    "error": data.get("msg", "Fichier non trouvé")
                }
                
        except Exception as e:
            logger.error(f"Erreur check status Filemoon: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_file(self, file_code: str) -> bool:
        """
        Supprime un fichier de Filemoon
        """
        try:
            url = self._build_url("delete", file=file_code)
            response = await self.client.get(url)
            data = response.json()
            
            return data.get("status") == "success"
            
        except Exception as e:
            logger.error(f"Erreur suppression Filemoon: {e}")
            return False
    
    async def rename_file(self, file_code: str, new_title: str) -> bool:
        """
        Renomme un fichier
        """
        try:
            url = self._build_url("rename", file=file_code, title=new_title)
            response = await self.client.get(url)
            data = response.json()
            
            return data.get("status") == "success"
            
        except Exception as e:
            logger.error(f"Erreur rename Filemoon: {e}")
            return False
    
    async def list_files(self, page: int = 1, per_page: int = 50) -> List[Dict[str, Any]]:
        """
        Liste les fichiers du compte
        """
        try:
            url = self._build_url("list", page=page, per_page=per_page)
            response = await self.client.get(url)
            data = response.json()
            
            if data.get("status") == "success":
                return data.get("result", {}).get("files", [])
            return []
            
        except Exception as e:
            logger.error(f"Erreur list files Filemoon: {e}")
            return []


# Instance globale
_filemoon_client: Optional[FilemoonAPI] = None


async def get_filemoon_client() -> FilemoonAPI:
    global _filemoon_client
    if _filemoon_client is None:
        _filemoon_client = FilemoonAPI()
    return _filemoon_client


# Fonctions utilitaires
async def upload_to_filemoon(remote_url: str, title: str = None) -> Dict[str, Any]:
    """Upload simplifié"""
    client = await get_filemoon_client()
    return await client.upload_remote(remote_url, title)


async def check_filemoon_status(file_code: str) -> Dict[str, Any]:
    """Check status simplifié"""
    client = await get_filemoon_client()
    return await client.check_status(file_code)
