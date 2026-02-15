"""
Intégration API TMDB (The Movie Database)
Récupération des métadonnées films/séries
"""

import logging
from typing import List, Dict, Any, Optional
import httpx

from config import settings

logger = logging.getLogger(__name__)


class TMDBClient:
    """Client pour l'API TMDB"""
    
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_BASE_URL
        self.image_base_url = settings.TMDB_IMAGE_BASE_URL
        self.language = "fr-FR"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Ferme le client HTTP"""
        await self.client.aclose()
    
    def _build_url(self, endpoint: str, params: Dict = None) -> str:
        """Construit l'URL avec clé API"""
        url = f"{self.base_url}{endpoint}?api_key={self.api_key}&language={self.language}"
        if params:
            for key, value in params.items():
                url += f"&{key}={value}"
        return url
    
    async def search(self, query: str, media_type: str = "movie", page: int = 1) -> List[Dict[str, Any]]:
        """
        Recherche de films ou séries
        
        Args:
            query: Terme de recherche
            media_type: 'movie' ou 'tv'
            page: Numéro de page
        """
        try:
            endpoint = f"/search/{media_type}"
            url = self._build_url(endpoint, {"query": query, "page": page})
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            # Formatage des résultats
            formatted = []
            for item in results:
                formatted.append({
                    "tmdb_id": item.get("id"),
                    "title": item.get("title") or item.get("name"),
                    "original_title": item.get("original_title") or item.get("original_name"),
                    "overview": item.get("overview", ""),
                    "poster_path": item.get("poster_path", ""),
                    "backdrop_path": item.get("backdrop_path", ""),
                    "release_date": item.get("release_date") or item.get("first_air_date"),
                    "vote_average": item.get("vote_average", 0),
                    "genre_ids": item.get("genre_ids", []),
                    "media_type": media_type
                })
            
            return formatted
            
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP TMDB search: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur TMDB search: {e}")
            return []
    
    async def get_details(self, tmdb_id: int, media_type: str = "movie") -> Optional[Dict[str, Any]]:
        """
        Récupère les détails complets d'un film ou série
        
        Args:
            tmdb_id: ID TMDB
            media_type: 'movie' ou 'tv'
        """
        try:
            endpoint = f"/{media_type}/{tmdb_id}"
            url = self._build_url(endpoint, {
                "append_to_response": "credits,keywords,videos,images",
                "include_image_language": "fr,null"
            })
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # Extraction des genres
            genres = [g["name"] for g in data.get("genres", [])]
            
            # Extraction des trailers YouTube
            videos = data.get("videos", {}).get("results", [])
            trailers = [
                f"https://youtube.com/watch?v={v['key']}"
                for v in videos
                if v["site"] == "YouTube" and v["type"] in ["Trailer", "Teaser"]
            ]
            
            result = {
                "tmdb_id": data.get("id"),
                "title": data.get("title") or data.get("name"),
                "original_title": data.get("original_title") or data.get("original_name"),
                "overview": data.get("overview", ""),
                "tagline": data.get("tagline", ""),
                "poster_path": data.get("poster_path", ""),
                "backdrop_path": data.get("backdrop_path", ""),
                "release_date": data.get("release_date") or data.get("first_air_date"),
                "runtime": data.get("runtime") or (data.get("episode_run_time", [None])[0]),
                "genres": genres,
                "vote_average": data.get("vote_average", 0),
                "vote_count": data.get("vote_count", 0),
                "popularity": data.get("popularity", 0),
                "status": data.get("status"),
                "homepage": data.get("homepage"),
                "trailers": trailers[:3],  # Max 3 trailers
                
                # Spécifique séries
                "number_of_seasons": data.get("number_of_seasons"),
                "number_of_episodes": data.get("number_of_episodes"),
                "seasons": data.get("seasons", []) if media_type == "tv" else None
            }
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP TMDB details {tmdb_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur TMDB details {tmdb_id}: {e}")
            return None
    
    async def get_season_details(self, tmdb_id: int, season_number: int) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails d'une saison spécifique (séries uniquement)
        """
        try:
            endpoint = f"/tv/{tmdb_id}/season/{season_number}"
            url = self._build_url(endpoint)
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            episodes = []
            for ep in data.get("episodes", []):
                episodes.append({
                    "episode_number": ep.get("episode_number"),
                    "title": ep.get("name"),
                    "overview": ep.get("overview", ""),
                    "air_date": ep.get("air_date"),
                    "runtime": ep.get("runtime"),
                    "still_path": ep.get("still_path"),
                    "vote_average": ep.get("vote_average", 0)
                })
            
            return {
                "season_number": data.get("season_number"),
                "name": data.get("name"),
                "overview": data.get("overview", ""),
                "poster_path": data.get("poster_path", ""),
                "air_date": data.get("air_date"),
                "episodes": episodes
            }
            
        except Exception as e:
            logger.error(f"Erreur TMDB season {season_number}: {e}")
            return None
    
    async def get_popular(self, media_type: str = "movie", page: int = 1) -> List[Dict[str, Any]]:
        """
        Récupère les films/séries populaires
        """
        try:
            endpoint = f"/{media_type}/popular"
            url = self._build_url(endpoint, {"page": page})
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("results", [])[:10]:  # Top 10
                results.append({
                    "tmdb_id": item.get("id"),
                    "title": item.get("title") or item.get("name"),
                    "poster_path": item.get("poster_path", ""),
                    "vote_average": item.get("vote_average", 0),
                    "media_type": media_type
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur TMDB popular: {e}")
            return []
    
    def get_image_url(self, path: str, size: str = "original") -> str:
        """
        Construit l'URL complète d'une image
        """
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return f"{self.image_base_url}/{size}{path}"


# Instance globale du client
_tmdb_client: Optional[TMDBClient] = None


async def get_tmdb_client() -> TMDBClient:
    """Singleton pour le client TMDB"""
    global _tmdb_client
    if _tmdb_client is None:
        _tmdb_client = TMDBClient()
    return _tmdb_client


# Fonctions utilitaires simplifiées
async def search_tmdb(query: str, media_type: str = "movie") -> List[Dict[str, Any]]:
    """Recherche simplifiée"""
    client = await get_tmdb_client()
    return await client.search(query, media_type)


async def get_tmdb_details(tmdb_id: int, media_type: str = "movie") -> Optional[Dict[str, Any]]:
    """Détails simplifiés"""
    client = await get_tmdb_client()
    return await client.get_details(tmdb_id, media_type)


async def get_tmdb_season(tmdb_id: int, season_number: int) -> Optional[Dict[str, Any]]:
    """Saison simplifiée"""
    client = await get_tmdb_client()
    return await client.get_season_details(tmdb_id, season_number)
