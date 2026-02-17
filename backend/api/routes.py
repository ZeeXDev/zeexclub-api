"""
Routes API complètes pour ZeeXClub
Endpoints REST pour shows, episodes, streaming
"""

import logging
import re
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response, Header
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

from config import settings
from api.dependencies import get_pagination_params, verify_origin, rate_limit
from database.queries import (
    get_all_shows, get_show_by_id, get_show_episodes,
    get_episode_sources, search_shows, get_episode_by_id,
    get_seasons_by_show, get_season_episodes, increment_show_views,
    get_trending_shows, get_shows_by_genre
)
from services.stream_handler import StreamHandler
from services.tmdb_api import search_tmdb, get_tmdb_details

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialisation du gestionnaire de streaming
stream_handler = StreamHandler()


# ============================================================================
# ENDPOINTS SHOWS (Films & Séries)
# ============================================================================

@router.get("/shows", response_model=Dict[str, Any])
async def list_shows(
    request: Request,
    pagination: dict = Depends(get_pagination_params),
    type: Optional[str] = Query(None, regex="^(movie|series)$"),
    genre: Optional[str] = None,
    year: Optional[int] = None,
    search: Optional[str] = None,
    trending: bool = False
):
    """
    Liste tous les shows avec filtres et pagination
    
    Paramètres:
    - type: 'movie' ou 'series'
    - genre: filtre par genre
    - year: année de sortie
    - search: recherche textuelle
    - trending: shows populaires
    """
    try:
        if trending:
            shows = await get_trending_shows(pagination["limit"])
            total = len(shows)
        elif search:
            shows, total = await search_shows(
                query=search,
                type=type,
                limit=pagination["limit"],
                offset=pagination["offset"]
            )
        else:
            shows, total = await get_all_shows(
                type=type,
                genre=genre,
                year=year,
                limit=pagination["limit"],
                offset=pagination["offset"],
                sort_by=pagination["sort_by"],
                order=pagination["order"]
            )
        
        # Construction réponse avec métadonnées de pagination
        total_pages = (total + pagination["limit"] - 1) // pagination["limit"]
        
        return {
            "success": True,
            "data": shows,
            "pagination": {
                "page": pagination["page"],
                "limit": pagination["limit"],
                "total": total,
                "total_pages": total_pages,
                "has_next": pagination["page"] < total_pages,
                "has_prev": pagination["page"] > 1
            },
            "filters": {
                "type": type,
                "genre": genre,
                "year": year,
                "search": search
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur list_shows: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des shows: {str(e)}")


@router.get("/shows/search")
async def search_shows_endpoint(
    q: str = Query(..., min_length=2, max_length=100),
    type: Optional[str] = Query(None, regex="^(movie|series)$"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Recherche rapide de shows par titre
    """
    try:
        shows, total = await search_shows(query=q, type=type, limit=limit, offset=0)
        return {
            "success": True,
            "query": q,
            "results": shows,
            "total": total
        }
    except Exception as e:
        logger.error(f"Erreur recherche: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur de recherche")


@router.get("/shows/{show_id}")
async def get_show_details(
    show_id: UUID,
    request: Request
):
    """
    Récupère les détails complets d'un show avec ses saisons
    """
    try:
        # Récupération du show
        show = await get_show_by_id(str(show_id))
        if not show:
            raise HTTPException(status_code=404, detail="Show non trouvé")
        
        # Incrémentation des vues (async, ne bloque pas la réponse)
        asyncio.create_task(increment_show_views(str(show_id)))
        
        # Récupération des saisons si c'est une série
        seasons = []
        if show.get("type") == "series":
            seasons = await get_seasons_by_show(str(show_id))
            
            # Pour chaque saison, compter les épisodes
            for season in seasons:
                season["episode_count"] = await get_episode_count_by_season(season["id"])
        
        # Construction de la réponse
        response = {
            "success": True,
            "data": {
                **show,
                "seasons": seasons,
                "poster_url": f"{settings.TMDB_IMAGE_BASE_URL}{show.get('poster_path', '')}" if show.get('poster_path') else None,
                "backdrop_url": f"{settings.TMDB_IMAGE_BASE_URL}{show.get('backdrop_path', '')}" if show.get('backdrop_path') else None
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_show_details {show_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des détails")


@router.get("/shows/{show_id}/episodes")
async def get_show_episodes_endpoint(
    show_id: UUID,
    season: Optional[int] = Query(None, ge=1, description="Numéro de saison spécifique")
):
    """
    Récupère tous les épisodes d'un show, groupés par saison
    """
    try:
        # Vérification existence du show
        show = await get_show_by_id(str(show_id))
        if not show:
            raise HTTPException(status_code=404, detail="Show non trouvé")
        
        if show["type"] == "movie":
            # Pour les films, retourner les sources directement
            sources = await get_episode_sources(str(show_id))
            return {
                "success": True,
                "type": "movie",
                "sources": sources
            }
        
        # Pour les séries, récupérer par saison
        if season:
            # Récupérer une saison spécifique
            seasons_data = await get_seasons_by_show(str(show_id))
            target_season = next((s for s in seasons_data if s["season_number"] == season), None)
            
            if not target_season:
                raise HTTPException(status_code=404, detail="Saison non trouvée")
            
            episodes = await get_season_episodes(target_season["id"])
            return {
                "success": True,
                "type": "series",
                "season": season,
                "season_id": target_season["id"],
                "episodes": episodes
            }
        else:
            # Toutes les saisons
            seasons = await get_seasons_by_show(str(show_id))
            result = []
            
            for season_data in seasons:
                episodes = await get_season_episodes(season_data["id"])
                result.append({
                    "season_number": season_data["season_number"],
                    "season_id": season_data["id"],
                    "name": season_data.get("name", f"Saison {season_data['season_number']}"),
                    "poster": season_data.get("poster"),
                    "episodes": episodes
                })
            
            return {
                "success": True,
                "type": "series",
                "seasons": result
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_show_episodes {show_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des épisodes")


@router.get("/shows/{show_id}/related")
async def get_related_shows(
    show_id: UUID,
    limit: int = Query(6, ge=1, le=20)
):
    """
    Récupère des shows similaires basés sur les genres
    """
    try:
        show = await get_show_by_id(str(show_id))
        if not show:
            raise HTTPException(status_code=404, detail="Show non trouvé")
        
        # Récupérer par genre similaire
        genres = show.get("genres", [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",")]
        
        related = await get_shows_by_genre(
            genres=genres,
            exclude_id=str(show_id),
            limit=limit
        )
        
        return {
            "success": True,
            "data": related
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_related_shows: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des suggestions")


# ============================================================================
# ENDPOINTS ÉPISODES
# ============================================================================

@router.get("/episodes/{episode_id}")
async def get_episode_details(episode_id: UUID):
    """
    Détails d'un épisode spécifique
    """
    try:
        episode = await get_episode_by_id(str(episode_id))
        if not episode:
            raise HTTPException(status_code=404, detail="Épisode non trouvé")
        
        # Récupérer les sources
        sources = await get_episode_sources(str(episode_id))
        
        return {
            "success": True,
            "data": {
                **episode,
                "sources": sources
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_episode_details {episode_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération de l'épisode")


@router.get("/episodes/{episode_id}/sources")
async def get_episode_sources_endpoint(
    episode_id: UUID,
    request: Request
):
    """
    Récupère toutes les sources vidéo disponibles pour un épisode
    """
    try:
        sources = await get_episode_sources(str(episode_id))
        
        if not sources:
            raise HTTPException(status_code=404, detail="Aucune source trouvée pour cet épisode")
        
        # Formater les liens pour le frontend
        formatted_sources = []
        for source in sources:
            formatted = {
                "id": source["id"],
                "server": source["server_name"],
                "quality": source.get("quality", "HD"),
                "language": source.get("language", "FR"),
                "is_active": source.get("is_active", True)
            }
            
            if source["server_name"] == "filemoon":
                formatted["embed_url"] = f"{settings.FILEMOON_PLAYER_URL}{source['filemoon_code']}"
                formatted["direct_link"] = None  # Filemoon n'a pas de lien direct
            else:
                # Telegram - lien via notre proxy
                formatted["embed_url"] = None
                formatted["direct_link"] = f"/api/stream/telegram/{source['file_id']}"
            
            formatted_sources.append(formatted)
        
        return {
            "success": True,
            "episode_id": str(episode_id),
            "sources": formatted_sources
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_episode_sources {episode_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des sources")


# ============================================================================
# ENDPOINTS STREAMING
# ============================================================================

@router.get("/stream/telegram/{file_id}")
async def stream_telegram_file(
    file_id: str,
    request: Request,
    range: Optional[str] = Header(None)
):
    """
    Endpoint de streaming pour les fichiers Telegram
    Supporte les Range Requests pour la lecture vidéo
    """
    try:
        # Validation du file_id
        if not re.match(r'^[A-Za-z0-9_-]+$', file_id):
            raise HTTPException(status_code=400, detail="File ID invalide")
        
        # Récupération des infos du fichier via le bot
        file_info = await stream_handler.get_file_info(file_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Fichier non trouvé sur Telegram")
        
        file_size = file_info.get("file_size", 0)
        mime_type = file_info.get("mime_type", "video/mp4")
        
        # Gestion des Range Requests (pour la lecture vidéo)
        start = 0
        end = file_size - 1
        
        if range:
            # Parse Range header: bytes=start-end
            range_match = re.match(r'bytes=(\d+)-(\d*)', range)
            if range_match:
                start = int(range_match.group(1))
                if range_match.group(2):
                    end = int(range_match.group(2))
        
        # Calcul de la taille du chunk
        chunk_size = end - start + 1
        
        # Headers pour le streaming
        headers = {
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Cache-Control": "public, max-age=31536000",
            "Access-Control-Allow-Origin": "*"
        }
        
        if range:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            status_code = 206
        else:
            status_code = 200
        
        # Générateur de streaming
        async def file_stream():
            try:
                async for chunk in stream_handler.stream_file(file_id, start, end):
                    yield chunk
            except Exception as e:
                logger.error(f"Erreur streaming {file_id}: {str(e)}")
                raise
        
        return StreamingResponse(
            file_stream(),
            status_code=status_code,
            headers=headers,
            media_type=mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur stream_telegram_file: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur de streaming")


@router.head("/stream/telegram/{file_id}")
async def stream_telegram_file_head(file_id: str):
    """
    Endpoint HEAD pour vérifier l'existence et la taille d'un fichier
    (Utilisé par les lecteurs vidéo avant de commencer le streaming)
    """
    try:
        file_info = await stream_handler.get_file_info(file_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Fichier non trouvé")
        
        headers = {
            "Content-Type": file_info.get("mime_type", "video/mp4"),
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_info.get("file_size", 0)),
            "Access-Control-Allow-Origin": "*"
        }
        
        return Response(headers=headers)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur head stream: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur")


# ============================================================================
# ENDPOINTS CATALOGUE & DÉCOUVERTE
# ============================================================================

@router.get("/genres")
async def list_genres():
    """
    Liste tous les genres disponibles
    """
    genres = [
        {"id": 28, "name": "Action"},
        {"id": 12, "name": "Aventure"},
        {"id": 16, "name": "Animation"},
        {"id": 35, "name": "Comédie"},
        {"id": 80, "name": "Crime"},
        {"id": 99, "name": "Documentaire"},
        {"id": 18, "name": "Drame"},
        {"id": 10751, "name": "Famille"},
        {"id": 14, "name": "Fantastique"},
        {"id": 36, "name": "Histoire"},
        {"id": 27, "name": "Horreur"},
        {"id": 10402, "name": "Musique"},
        {"id": 9648, "name": "Mystère"},
        {"id": 10749, "name": "Romance"},
        {"id": 878, "name": "Science-Fiction"},
        {"id": 10770, "name": "Téléfilm"},
        {"id": 53, "name": "Thriller"},
        {"id": 10752, "name": "Guerre"},
        {"id": 37, "name": "Western"}
    ]
    
    return {"success": True, "data": genres}


@router.get("/trending")
async def trending(
    type: Optional[str] = Query(None, regex="^(movie|series|all)$"),
    time_window: str = Query("week", regex="^(day|week)$"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Shows tendance (basé sur les vues récentes)
    """
    try:
        shows = await get_trending_shows(
            type=type,
            time_window=time_window,
            limit=limit
        )
        
        return {
            "success": True,
            "data": shows,
            "time_window": time_window
        }
        
    except Exception as e:
        logger.error(f"Erreur trending: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des tendances")


@router.get("/recent")
async def recently_added(
    type: Optional[str] = Query(None, regex="^(movie|series)$"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Derniers ajouts à la plateforme
    """
    try:
        shows = await get_all_shows(
            type=type,
            limit=limit,
            offset=0,
            sort_by="created_at",
            order="desc"
        )
        
        return {
            "success": True,
            "data": shows[0] if isinstance(shows, tuple) else shows
        }
        
    except Exception as e:
        logger.error(f"Erreur recent: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur")


# ============================================================================
# ENDPOINTS TMDB (Proxy)
# ============================================================================

@router.get("/tmdb/search")
async def tmdb_search_proxy(
    q: str = Query(..., min_length=2),
    type: str = Query("movie", regex="^(movie|tv)$")
):
    """
    Proxy pour recherche TMDB (évite d'exposer la clé API côté client)
    """
    try:
        results = await search_tmdb(query=q, media_type=type)
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        logger.error(f"Erreur TMDB search: {str(e)}")
        raise HTTPException(status_code=502, detail="Erreur TMDB")


@router.get("/tmdb/{tmdb_id}")
async def tmdb_details_proxy(
    tmdb_id: int,
    type: str = Query("movie", regex="^(movie|tv)$")
):
    """
    Proxy pour détails TMDB
    """
    try:
        details = await get_tmdb_details(tmdb_id=tmdb_id, media_type=type)
        return {
            "success": True,
            "data": details
        }
    except Exception as e:
        logger.error(f"Erreur TMDB details: {str(e)}")
        raise HTTPException(status_code=502, detail="Erreur TMDB")


# Import manquant
import asyncio

# Fonction helper manquante
async def get_episode_count_by_season(season_id: str) -> int:
    """Compte le nombre d'épisodes dans une saison"""
    from database.queries import get_supabase
    try:
        supabase = get_supabase()
        result = supabase.table("episodes").select("id", count="exact").eq("season_id", season_id).execute()
        return result.count if hasattr(result, 'count') else len(result.data)
    except:
        return 0
