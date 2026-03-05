"""
Routes API complètes pour ZeeXClub
Endpoints REST pour shows, episodes, streaming et Filemoon remote upload
"""

import logging
import re
import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response, Header, BackgroundTasks, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, HttpUrl, Field
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
# MODÈLES Pydantic
# ============================================================================

class RemoteUploadRequest(BaseModel):
    """Modèle pour la requête de remote upload"""
    url: HttpUrl = Field(..., description="URL directe du fichier à uploader")
    title: Optional[str] = Field(None, max_length=255, description="Titre du fichier")
    description: Optional[str] = Field(None, description="Description optionnelle")
    folder_id: Optional[str] = Field(None, description="ID du dossier Filemoon (optionnel)")


class RemoteUploadResponse(BaseModel):
    """Modèle pour la réponse de remote upload"""
    success: bool
    file_code: Optional[str] = None
    file_id: Optional[str] = None
    player_url: Optional[str] = None
    download_url: Optional[str] = None
    status: str
    message: Optional[str] = None
    encoding_status: Optional[str] = None


class FileStatusResponse(BaseModel):
    """Modèle pour le statut d'un fichier"""
    success: bool
    file_code: str
    status: str  # ready, processing, error
    file_size: Optional[int] = None
    file_duration: Optional[int] = None
    player_url: Optional[str] = None
    download_url: Optional[str] = None
    encoding_status: Optional[str] = None
    message: Optional[str] = None


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
            # Pour les films, récupérer les sources via seasons → episodes
            from database.queries import get_supabase
            
            try:
                supabase = get_supabase()
                
                # Récupérer la saison 0 du film
                season_result = supabase.table("seasons")\
                    .select("id")\
                    .eq("show_id", str(show_id))\
                    .eq("season_number", 0)\
                    .execute()
                
                if not season_result.data:
                    return {
                        "success": True,
                        "type": "movie",
                        "sources": []
                    }
                
                season_id = season_result.data[0]["id"]
                
                # Récupérer l'épisode de la saison 0
                episode_result = supabase.table("episodes")\
                    .select("id")\
                    .eq("season_id", season_id)\
                    .limit(1)\
                    .execute()
                
                if not episode_result.data:
                    return {
                        "success": True,
                        "type": "movie",
                        "sources": []
                    }
                
                episode_id = episode_result.data[0]["id"]
                
                # Récupérer les sources de cet épisode
                sources_result = supabase.table("video_sources")\
                    .select("*")\
                    .eq("episode_id", episode_id)\
                    .eq("is_active", True)\
                    .execute()
                
                # Formater les sources pour le frontend
                sources = []
                for source in sources_result.data:
                    formatted = {
                        "id": source["id"],
                        "server": source["server_name"],
                        "quality": source.get("quality", "HD"),
                        "language": source.get("language", "FR"),
                        "is_active": source.get("is_active", True)
                    }
                    
                    if source["server_name"] == "filemoon" and source.get("filemoon_code"):
                        formatted["embed_url"] = f"{settings.FILEMOON_PLAYER_URL}{source['filemoon_code']}"
                        formatted["direct_link"] = None
                    else:
                        formatted["embed_url"] = None
                        formatted["direct_link"] = source.get("link", f"/api/stream/telegram/{source.get('file_id', '')}")
                    
                    sources.append(formatted)
                
                return {
                    "success": True,
                    "type": "movie",
                    "sources": sources
                }
                
            except Exception as e:
                logger.error(f"Erreur récupération sources film: {str(e)}")
                return {
                    "success": True,
                    "type": "movie",
                    "sources": []
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
# ENDPOINTS FILEMOON REMOTE UPLOAD (CORRIGÉ)
# ============================================================================

@router.post("/upload/remote", response_model=RemoteUploadResponse)
async def remote_upload_to_filemoon(
    request: RemoteUploadRequest,
    background_tasks: BackgroundTasks = None
):
    """
    Remote upload vers Filemoon - CORRIGÉ avec endpoints officiels
    
    Basé sur la documentation Filemoon API:
    - https://filemoon.sx/api/account/info (vérification clé)
    - https://filemoon.sx/api/remote/upload (remote upload direct)
    """
    try:
        logger.info(f"=== REMOTE UPLOAD START ===")
        logger.info(f"URL source: {request.url}")
        logger.info(f"Titre: {request.title}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Étape 1: Vérifier la clé API avec account/info
            logger.info("Étape 1: Vérification de la clé API...")
            
            account_url = "https://filemoon.sx/api/account/info"
            account_response = await client.get(
                account_url,
                params={"key": settings.FILEMOON_API_KEY}
            )
            
            logger.info(f"Account check status: {account_response.status_code}")
            
            if account_response.status_code != 200:
                logger.error(f"Clé API invalide: {account_response.text}")
                raise HTTPException(status_code=502, detail="Clé API Filemoon invalide ou expirée")
            
            try:
                account_data = account_response.json()
                logger.info(f"Account info: {account_data.get('status')}")
            except:
                logger.warning("Impossible de parser account/info, on continue...")
            
            # Étape 2: Lancer le remote upload DIRECTEMENT (pas besoin de server upload)
            # L'API Filemoon permet le remote upload direct avec la clé API
            logger.info("Étape 2: Lancement du remote upload...")
            
            remote_upload_url = "https://filemoon.sx/api/remote/upload"
            
            remote_params = {
                "key": settings.FILEMOON_API_KEY,
                "url": str(request.url)
            }
            
            # Ajouter les métadonnées optionnelles
            if request.title:
                remote_params["title"] = request.title
            if request.description:
                remote_params["description"] = request.description
            if request.folder_id:
                remote_params["fld_id"] = request.folder_id
            
            logger.info(f"POST {remote_upload_url}?key=***&url={str(request.url)[:50]}...")
            
            remote_response = await client.post(
                remote_upload_url, 
                data=remote_params,  # Utiliser data= pour form-encoded
                timeout=60.0
            )
            
            logger.info(f"Status remote upload: {remote_response.status_code}")
            
            if remote_response.status_code != 200:
                error_text = remote_response.text
                logger.error(f"Erreur remote upload HTTP {remote_response.status_code}: {error_text[:500]}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Erreur remote upload (HTTP {remote_response.status_code})"
                )
            
            try:
                remote_data = remote_response.json()
            except Exception as e:
                logger.error(f"Réponse remote upload invalide: {remote_response.text[:500]}")
                raise HTTPException(status_code=502, detail="Réponse invalide de Filemoon")
            
            logger.info(f"Réponse remote upload: {remote_data}")
            
            # Traitement de la réponse
            if remote_data.get("status") == "success":
                result = remote_data.get("result", {})
                
                # Extraction des données selon la structure Filemoon
                file_code = result.get("filecode") or result.get("file_code") or result.get("code")
                file_id = result.get("file_id") or result.get("id")
                
                if not file_code:
                    logger.error(f"Pas de file_code dans la réponse: {result}")
                    raise HTTPException(status_code=502, detail="Réponse Filemoon incomplète (pas de file_code)")
                
                # Construction des URLs
                player_url = f"{settings.FILEMOON_PLAYER_URL}{file_code}"
                download_url = f"https://filemoon.sx/d/{file_code}"
                
                # Déterminer le statut
                is_ready = result.get("is_ready", "1")
                status = "ready" if is_ready == "1" else "processing"
                
                logger.info(f"=== REMOTE UPLOAD SUCCESS ===")
                logger.info(f"File code: {file_code}")
                logger.info(f"Status: {status}")
                logger.info(f"Player URL: {player_url}")
                
                return RemoteUploadResponse(
                    success=True,
                    file_code=file_code,
                    file_id=file_id,
                    player_url=player_url,
                    download_url=download_url,
                    status=status,
                    message="Upload terminé avec succès" if status == "ready" else "Upload lancé, encodage en cours",
                    encoding_status="completed" if status == "ready" else "pending"
                )
            else:
                error_msg = remote_data.get("msg", "Erreur inconnue du remote upload")
                logger.error(f"Remote upload failed: {error_msg}")
                return RemoteUploadResponse(
                    success=False,
                    status="error",
                    message=error_msg
                )
                
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("Timeout lors du remote upload Filemoon")
        raise HTTPException(status_code=504, detail="Timeout - Filemoon met trop de temps à répondre")
    except httpx.RequestError as e:
        logger.error(f"Erreur réseau: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Erreur réseau: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur inattendue remote upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/upload/status/{file_code}", response_model=FileStatusResponse)
async def check_upload_status(file_code: str):
    """
    Vérifier le statut d'un fichier sur Filemoon (encoding, etc.)
    
    Endpoint Filemoon: /api/file/info
    """
    try:
        logger.info(f"Checking status for file_code: {file_code}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://filemoon.sx/api/file/info",
                params={
                    "key": settings.FILEMOON_API_KEY,
                    "file_code": file_code
                }
            )
            
            logger.info(f"Status check HTTP {response.status_code}")
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Filemoon indisponible")
            
            try:
                data = response.json()
            except:
                logger.error(f"Réponse non-JSON: {response.text[:500]}")
                raise HTTPException(status_code=502, detail="Réponse invalide de Filemoon")
            
            logger.info(f"Status response: {data}")
            
            if data.get("status") == "success":
                result_list = data.get("result", [])
                if not result_list or not isinstance(result_list, list):
                    return FileStatusResponse(
                        success=True,
                        file_code=file_code,
                        status="unknown",
                        message="Aucune info disponible"
                    )
                
                result = result_list[0]  # Premier résultat
                
                # Mapping du statut Filemoon
                # status: 0 = en cours, 1 = prêt, 2 = erreur
                file_status_num = result.get("status", "0")
                if file_status_num == "1":
                    status = "ready"
                elif file_status_num == "2":
                    status = "error"
                else:
                    status = "processing"
                
                return FileStatusResponse(
                    success=True,
                    file_code=file_code,
                    status=status,
                    file_size=result.get("file_size"),
                    file_duration=result.get("file_duration"),
                    player_url=f"{settings.FILEMOON_PLAYER_URL}{file_code}",
                    download_url=f"https://filemoon.sx/d/{file_code}",
                    encoding_status=result.get("encoding_status"),
                    message="Fichier prêt" if status == "ready" else "Encodage en cours..." if status == "processing" else "Erreur d'encodage"
                )
            else:
                error_msg = data.get("msg", "Fichier non trouvé")
                return FileStatusResponse(
                    success=False,
                    file_code=file_code,
                    status="error",
                    message=error_msg
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur check status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {str(e)}")


@router.delete("/upload/file/{file_code}")
async def delete_filemoon_file(file_code: str):
    """
    Supprimer un fichier de Filemoon
    
    Endpoint: /api/file/delete
    """
    try:
        logger.info(f"Deleting file: {file_code}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://filemoon.sx/api/file/delete",
                params={
                    "key": settings.FILEMOON_API_KEY,
                    "file_code": file_code
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Filemoon indisponible")
            
            data = response.json()
            
            if data.get("status") == "success":
                logger.info(f"File {file_code} deleted successfully")
                return {
                    "success": True, 
                    "message": "Fichier supprimé avec succès",
                    "file_code": file_code
                }
            else:
                error_msg = data.get("msg", "Erreur de suppression")
                logger.error(f"Delete failed: {error_msg}")
                return {
                    "success": False, 
                    "message": error_msg,
                    "file_code": file_code
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur suppression: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")


@router.get("/filemoon/account/info")
async def get_filemoon_account_info():
    """
    Récupère les informations du compte Filemoon
    Utile pour vérifier que la clé API fonctionne
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://filemoon.sx/api/account/info",
                params={"key": settings.FILEMOON_API_KEY}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Filemoon indisponible")
            
            data = response.json()
            return data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur account info: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des infos compte")


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


# ============================================================================
# FONCTIONS UTILITAIRES (Helpers)
# ============================================================================

async def get_episode_count_by_season(season_id: str) -> int:
    """Compte le nombre d'épisodes dans une saison"""
    from database.queries import get_supabase
    try:
        supabase = get_supabase()
        result = supabase.table("episodes").select("id", count="exact").eq("season_id", season_id).execute()
        return result.count if hasattr(result, 'count') else len(result.data)
    except Exception as e:
        logger.error(f"Erreur comptage épisodes: {e}")
        return 0
