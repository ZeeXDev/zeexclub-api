"""
Requêtes CRUD complètes pour Supabase
Toutes les opérations base de données
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from postgrest.exceptions import APIError

from database.supabase_client import get_supabase, handle_db_error, DatabaseError

logger = logging.getLogger(__name__)


# ============================================================================
# OPERATIONS SHOWS
# ============================================================================

async def get_all_shows(
    type: Optional[str] = None,
    genre: Optional[str] = None,
    year: Optional[int] = None,
    status: str = "active",
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    order: str = "desc"
) -> Tuple[List[Dict], int]:
    """
    Récupère tous les shows avec filtres et pagination
    
    Returns:
        Tuple (liste des shows, nombre total)
    """
    try:
        supabase = get_supabase()
        
        # Construction de la requête de base
        query = supabase.table("shows").select("*", count="exact")
        
        # Application des filtres
        if type:
            query = query.eq("type", type)
        
        if status:
            query = query.eq("status", status)
        
        if genre:
            # Recherche dans le tableau genres ou string
            query = query.or_(f"genres.cs.{{{genre}}},genres.ilike.%{genre}%")
        
        if year:
            query = query.gte("release_date", f"{year}-01-01")
            query = query.lte("release_date", f"{year}-12-31")
        
        # Tri
        if order.lower() == "desc":
            query = query.order(sort_by, desc=True)
        else:
            query = query.order(sort_by)
        
        # Pagination
        query = query.range(offset, offset + limit - 1)
        
        # Exécution
        response = query.execute()
        
        total = response.count if hasattr(response, 'count') else len(response.data)
        return response.data, total
        
    except Exception as e:
        handle_db_error(e, "récupération des shows")
        return [], 0


async def get_show_by_id(show_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère un show par son UUID
    """
    try:
        supabase = get_supabase()
        response = supabase.table("shows").select("*").eq("id", show_id).maybe_single().execute()
        # CORRECTION: maybe_single() retourne None si pas trouvé, ou un dict
        if response.data:
            return response.data
        return None
        
    except APIError as e:
        if "JSON object requested, multiple (or no) rows returned" in str(e):
            return None
        handle_db_error(e, f"récupération du show {show_id}")
    except Exception as e:
        handle_db_error(e, f"récupération du show {show_id}")


async def get_show_by_tmdb_id(tmdb_id: int) -> Optional[Dict[str, Any]]:
    """
    Récupère un show par son ID TMDB
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single() pour éviter l'erreur JSON
        response = supabase.table("shows").select("*").eq("tmdb_id", tmdb_id).limit(1).execute()
        
        # CORRECTION: response.data est une liste, prendre le premier élément
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        handle_db_error(e, f"récupération par TMDB ID {tmdb_id}")
    except Exception as e:
        handle_db_error(e, f"récupération par TMDB ID {tmdb_id}")


async def create_show(show_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée un nouveau show
    
    Args:
        show_data: Dict avec tmdb_id, title, type, overview, poster_path, etc.
    
    Returns:
        Le show créé avec son UUID généré
    """
    try:
        supabase = get_supabase()
        
        # Vérification doublon TMDB
        existing = await get_show_by_tmdb_id(show_data.get("tmdb_id"))
        if existing:
            raise DatabaseError(f"Un show avec TMDB ID {show_data['tmdb_id']} existe déjà")
        
        # Préparation des données
        insert_data = {
            "id": str(uuid4()),
            "tmdb_id": show_data["tmdb_id"],
            "title": show_data["title"],
            "type": show_data["type"],
            "overview": show_data.get("overview", ""),
            "poster_path": show_data.get("poster_path", ""),
            "backdrop_path": show_data.get("backdrop_path", ""),
            "release_date": show_data.get("release_date"),
            "genres": show_data.get("genres", []),
            "runtime": show_data.get("runtime"),
            "rating": show_data.get("rating"),
            "language": show_data.get("language", "fr"),
            "status": "active",
            "views": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("shows").insert(insert_data).execute()
        
        # CORRECTION: response.data est une liste
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Show créé: {insert_data['title']} (ID: {insert_data['id']})")
            return response.data[0]
        else:
            raise DatabaseError("Erreur lors de la création du show")
            
    except DatabaseError:
        raise
    except Exception as e:
        handle_db_error(e, "création du show")


async def update_show(show_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Met à jour un show existant
    """
    try:
        supabase = get_supabase()
        
        # Filtrer les champs non modifiables
        allowed_fields = ["title", "overview", "poster_path", "backdrop_path", 
                         "release_date", "genres", "runtime", "rating", "status"]
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        filtered_data["updated_at"] = datetime.utcnow().isoformat()
        
        response = supabase.table("shows").update(filtered_data).eq("id", show_id).execute()
        
        # CORRECTION: response.data est une liste
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Show mis à jour: {show_id}")
            return response.data[0]
        return None
        
    except Exception as e:
        handle_db_error(e, f"mise à jour du show {show_id}")


async def delete_show(show_id: str) -> bool:
    """
    Supprime un show et toutes ses données associées (cascade)
    """
    try:
        supabase = get_supabase()
        
        # La suppression en cascade est gérée par les FK en DB
        response = supabase.table("shows").delete().eq("id", show_id).execute()
        
        success = len(response.data) > 0
        if success:
            logger.info(f"🗑️ Show supprimé: {show_id}")
        return success
        
    except Exception as e:
        handle_db_error(e, f"suppression du show {show_id}")
        return False


async def increment_show_views(show_id: str):
    """
    Incrémente le compteur de vues d'un show (async, fire-and-forget)
    """
    try:
        supabase = get_supabase()
        
        # Récupération valeur actuelle
        show = await get_show_by_id(show_id)
        if show:
            new_views = (show.get("views") or 0) + 1
            
            supabase.table("shows").update({
                "views": new_views,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", show_id).execute()
            
    except Exception as e:
        logger.error(f"Erreur incrémentation vues {show_id}: {e}")
        # Ne pas propager l'erreur, ce n'est pas critique


async def search_shows(
    query: str,
    type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Recherche full-text dans les titres et synopsis
    """
    try:
        supabase = get_supabase()
        
        # Recherche dans le titre (principalement)
        # Supabase ilike pour case-insensitive
        search_query = supabase.table("shows").select("*", count="exact").or_(
            f"title.ilike.%{query}%,overview.ilike.%{query}%"
        )
        
        if type:
            search_query = search_query.eq("type", type)
        
        search_query = search_query.order("title").range(offset, offset + limit - 1)
        
        response = search_query.execute()
        total = response.count if hasattr(response, 'count') else len(response.data)
        
        return response.data, total
        
    except Exception as e:
        handle_db_error(e, f"recherche '{query}'")
        return [], 0


async def get_trending_shows(
    type: Optional[str] = None,
    time_window: str = "week",
    limit: int = 20
) -> List[Dict]:
    """
    Récupère les shows tendance (basé sur les vues récentes)
    Pour l'instant: simplement les plus vus globalement
    """
    try:
        supabase = get_supabase()
        
        query = supabase.table("shows").select("*").order("views", desc=True).limit(limit)
        
        if type:
            query = query.eq("type", type)
        
        response = query.execute()
        return response.data
        
    except Exception as e:
        handle_db_error(e, "récupération des tendances")
        return []


async def get_shows_by_genre(
    genres: List[str],
    exclude_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Récupère des shows par genre (OR entre les genres)
    """
    try:
        if not genres:
            return []
        
        supabase = get_supabase()
        
        # Construction de la requête OR pour les genres
        genre_filters = []
        for genre in genres[:3]:  # Limite à 3 genres pour perf
            genre_filters.append(f"genres.cs.{{{genre}}}")
        
        query = supabase.table("shows").select("*").or_(",".join(genre_filters))
        
        if exclude_id:
            query = query.neq("id", exclude_id)
        
        query = query.limit(limit)
        response = query.execute()
        
        return response.data
        
    except Exception as e:
        handle_db_error(e, "récupération par genre")
        return []


# ============================================================================
# OPERATIONS SAISONS
# ============================================================================

async def get_seasons_by_show(show_id: str) -> List[Dict[str, Any]]:
    """
    Récupère toutes les saisons d'un show, ordonnées par numéro
    """
    try:
        supabase = get_supabase()
        response = supabase.table("seasons").select("*").eq("show_id", show_id).order("season_number").execute()
        return response.data
        
    except Exception as e:
        handle_db_error(e, f"récupération des saisons pour {show_id}")
        return []


async def get_season_by_id(season_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère une saison par son UUID
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single()
        response = supabase.table("seasons").select("*").eq("id", season_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        handle_db_error(e, f"récupération saison {season_id}")
    except Exception as e:
        handle_db_error(e, f"récupération saison {season_id}")


async def get_season_by_number(show_id: str, season_number: int) -> Optional[Dict[str, Any]]:
    """
    Récupère une saison spécifique par son numéro
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single()
        response = supabase.table("seasons").select("*").eq("show_id", show_id).eq("season_number", season_number).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        handle_db_error(e, f"récupération saison {season_number}")
    except Exception as e:
        handle_db_error(e, f"récupération saison {season_number}")


async def create_season(season_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée une nouvelle saison
    
    Auto-création si season_number=0 pour les films (saison spéciale)
    """
    try:
        supabase = get_supabase()
        
        # Vérification doublon
        existing = await get_season_by_number(
            season_data["show_id"], 
            season_data["season_number"]
        )
        if existing:
            raise DatabaseError(
                f"La saison {season_data['season_number']} existe déjà pour ce show"
            )
        
        insert_data = {
            "id": str(uuid4()),
            "show_id": season_data["show_id"],
            "season_number": season_data["season_number"],
            "name": season_data.get("name", f"Saison {season_data['season_number']}"),
            "poster": season_data.get("poster"),
            "overview": season_data.get("overview"),
            "air_date": season_data.get("air_date"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("seasons").insert(insert_data).execute()
        
        # CORRECTION: response.data est une liste
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Saison créée: {insert_data['name']} (Show: {season_data['show_id']})")
            return response.data[0]
        raise DatabaseError("Erreur création saison")
        
    except DatabaseError:
        raise
    except Exception as e:
        handle_db_error(e, "création de la saison")


async def update_season(season_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Met à jour une saison
    """
    try:
        supabase = get_supabase()
        
        allowed = ["name", "poster", "overview", "air_date"]
        filtered = {k: v for k, v in update_data.items() if k in allowed}
        
        response = supabase.table("seasons").update(filtered).eq("id", season_id).execute()
        # CORRECTION: response.data est une liste
        return response.data[0] if response.data and len(response.data) > 0 else None
        
    except Exception as e:
        handle_db_error(e, f"mise à jour saison {season_id}")


async def delete_season(season_id: str) -> bool:
    """
    Supprime une saison et tous ses épisodes (cascade)
    """
    try:
        supabase = get_supabase()
        response = supabase.table("seasons").delete().eq("id", season_id).execute()
        success = len(response.data) > 0
        if success:
            logger.info(f"🗑️ Saison supprimée: {season_id}")
        return success
        
    except Exception as e:
        handle_db_error(e, f"suppression saison {season_id}")
        return False


# ============================================================================
# OPERATIONS ÉPISODES
# ============================================================================

async def get_episodes_by_season(season_id: str) -> List[Dict[str, Any]]:
    """
    Récupère tous les épisodes d'une saison
    """
    try:
        supabase = get_supabase()
        response = supabase.table("episodes").select("*").eq("season_id", season_id).order("episode_number").execute()
        return response.data
        
    except Exception as e:
        handle_db_error(e, f"récupération épisodes saison {season_id}")
        return []


async def get_season_episodes(season_id: str) -> List[Dict[str, Any]]:
    """Alias pour cohérence"""
    return await get_episodes_by_season(season_id)


async def get_episode_by_id(episode_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère un épisode par son UUID
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single()
        response = supabase.table("episodes").select("*").eq("id", episode_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        handle_db_error(e, f"récupération épisode {episode_id}")
    except Exception as e:
        handle_db_error(e, f"récupération épisode {episode_id}")


async def get_episode_by_number(season_id: str, episode_number: int) -> Optional[Dict[str, Any]]:
    """
    Récupère un épisode spécifique par son numéro dans une saison
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single()
        response = supabase.table("episodes").select("*").eq("season_id", season_id).eq("episode_number", episode_number).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        handle_db_error(e, f"récupération épisode {episode_number}")
    except Exception as e:
        handle_db_error(e, f"récupération épisode {episode_number}")


async def create_episode(episode_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée un nouvel épisode
    
    Args:
        episode_data: season_id, episode_number, title, overview, etc.
    """
    try:
        supabase = get_supabase()
        
        # Vérification doublon
        existing = await get_episode_by_number(
            episode_data["season_id"],
            episode_data["episode_number"]
        )
        if existing:
            raise DatabaseError(
                f"L'épisode {episode_data['episode_number']} existe déjà dans cette saison"
            )
        
        insert_data = {
            "id": str(uuid4()),
            "season_id": episode_data["season_id"],
            "episode_number": episode_data["episode_number"],
            "title": episode_data.get("title", f"Épisode {episode_data['episode_number']}"),
            "overview": episode_data.get("overview", ""),
            "thumbnail": episode_data.get("thumbnail"),
            "air_date": episode_data.get("air_date"),
            "runtime": episode_data.get("runtime"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("episodes").insert(insert_data).execute()
        
        # CORRECTION: response.data est une liste
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Épisode créé: {insert_data['title']} (Saison: {episode_data['season_id']})")
            return response.data[0]
        raise DatabaseError("Erreur création épisode")
        
    except DatabaseError:
        raise
    except Exception as e:
        handle_db_error(e, "création de l'épisode")


async def update_episode(episode_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Met à jour un épisode
    """
    try:
        supabase = get_supabase()
        
        allowed = ["title", "overview", "thumbnail", "air_date", "runtime"]
        filtered = {k: v for k, v in update_data.items() if k in allowed}
        
        response = supabase.table("episodes").update(filtered).eq("id", episode_id).execute()
        # CORRECTION: response.data est une liste
        return response.data[0] if response.data and len(response.data) > 0 else None
        
    except Exception as e:
        handle_db_error(e, f"mise à jour épisode {episode_id}")


async def delete_episode(episode_id: str) -> bool:
    """
    Supprime un épisode et toutes ses sources (cascade)
    """
    try:
        supabase = get_supabase()
        response = supabase.table("episodes").delete().eq("id", episode_id).execute()
        success = len(response.data) > 0
        if success:
            logger.info(f"🗑️ Épisode supprimé: {episode_id}")
        return success
        
    except Exception as e:
        handle_db_error(e, f"suppression épisode {episode_id}")
        return False


async def get_show_episodes(show_id: str) -> List[Dict[str, Any]]:
    """
    Récupère tous les épisodes d'un show (toutes saisons confondues)
    Avec info de la saison pour chaque épisode
    """
    try:
        supabase = get_supabase()
        
        # Jointure avec saisons pour avoir le season_number
        response = supabase.table("episodes").select(
            "*, seasons!inner(show_id, season_number)"
        ).eq("seasons.show_id", show_id).order("seasons.season_number").order("episode_number").execute()
        
        return response.data
        
    except Exception as e:
        handle_db_error(e, f"récupération épisodes show {show_id}")
        return []


# ============================================================================
# OPERATIONS SOURCES VIDÉO
# ============================================================================

async def get_episode_sources(episode_id: str) -> List[Dict[str, Any]]:
    """
    Récupère toutes les sources vidéo actives d'un épisode
    """
    try:
        supabase = get_supabase()
        response = supabase.table("video_sources").select("*").eq("episode_id", episode_id).eq("is_active", True).execute()
        return response.data
        
    except Exception as e:
        handle_db_error(e, f"récupération sources épisode {episode_id}")
        return []


async def get_source_by_id(source_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère une source par son UUID
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single()
        response = supabase.table("video_sources").select("*").eq("id", source_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        handle_db_error(e, f"récupération source {source_id}")
    except Exception as e:
        handle_db_error(e, f"récupération source {source_id}")


async def create_video_source(source_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée une nouvelle source vidéo
    
    Args:
        source_data: episode_id, server_name, link, file_id/filemoon_code, etc.
    """
    try:
        supabase = get_supabase()
        
        insert_data = {
            "id": str(uuid4()),
            "episode_id": source_data["episode_id"],
            "server_name": source_data["server_name"],
            "link": source_data["link"],
            "file_id": source_data.get("file_id"),
            "filemoon_code": source_data.get("filemoon_code"),
            "quality": source_data.get("quality", "HD"),
            "language": source_data.get("language", "FR"),
            "is_active": source_data.get("is_active", True),
            "file_size": source_data.get("file_size"),
            "duration": source_data.get("duration"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("video_sources").insert(insert_data).execute()
        
        # CORRECTION: response.data est une liste
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Source créée: {source_data['server_name']} pour épisode {source_data['episode_id']}")
            return response.data[0]
        raise DatabaseError("Erreur création source")
        
    except Exception as e:
        handle_db_error(e, "création de la source vidéo")


async def update_video_source(source_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Met à jour une source vidéo
    """
    try:
        supabase = get_supabase()
        
        allowed = ["link", "is_active", "quality", "filemoon_code"]
        filtered = {k: v for k, v in update_data.items() if k in allowed}
        
        response = supabase.table("video_sources").update(filtered).eq("id", source_id).execute()
        # CORRECTION: response.data est une liste
        return response.data[0] if response.data and len(response.data) > 0 else None
        
    except Exception as e:
        handle_db_error(e, f"mise à jour source {source_id}")


async def delete_video_source(source_id: str) -> bool:
    """
    Supprime une source vidéo
    """
    try:
        supabase = get_supabase()
        response = supabase.table("video_sources").delete().eq("id", source_id).execute()
        return len(response.data) > 0
        
    except Exception as e:
        handle_db_error(e, f"suppression source {source_id}")
        return False


async def get_source_by_filemoon_code(filemoon_code: str) -> Optional[Dict[str, Any]]:
    """
    Recherche une source par son code Filemoon
    """
    try:
        supabase = get_supabase()
        # CORRECTION: Utiliser .limit(1) au lieu de .single()
        response = supabase.table("video_sources").select("*").eq("filemoon_code", filemoon_code).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
        
    except APIError as e:
        if "JSON object requested" in str(e):
            return None
        return None
    except Exception:
        return None


# ============================================================================
# OPERATIONS ADMIN & BOT
# ============================================================================

async def get_or_create_bot_session(admin_id: int) -> Dict[str, Any]:
    """
    Récupère ou crée une session bot pour un admin
    """
    try:
        supabase = get_supabase()
        
        # Recherche session existante
        response = supabase.table("bot_sessions").select("*").eq("admin_id", admin_id).limit(1).execute()
        
        # CORRECTION: response.data est une liste
        if response.data and len(response.data) > 0:
            # Mise à jour last_activity
            supabase.table("bot_sessions").update({
                "last_activity": datetime.utcnow().isoformat()
            }).eq("admin_id", admin_id).execute()
            return response.data[0]
        
        # Création nouvelle session
        session_data = {
            "id": str(uuid4()),
            "admin_id": admin_id,
            "state": "idle",
            "temp_data": {},
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        
        insert_response = supabase.table("bot_sessions").insert(session_data).execute()
        return insert_response.data[0] if insert_response.data and len(insert_response.data) > 0 else session_data
        
    except Exception as e:
        logger.error(f"Erreur session bot: {e}")
        # Retourne session temporaire en mémoire si DB fail
        return {
            "admin_id": admin_id,
            "state": "idle",
            "temp_data": {}
        }


async def update_bot_session(admin_id: int, state: str, temp_data: Dict = None):
    """
    Met à jour l'état de la session bot
    """
    try:
        supabase = get_supabase()
        
        update_data = {
            "state": state,
            "last_activity": datetime.utcnow().isoformat()
        }
        
        if temp_data is not None:
            update_data["temp_data"] = temp_data
        
        supabase.table("bot_sessions").update(update_data).eq("admin_id", admin_id).execute()
        
    except Exception as e:
        logger.error(f"Erreur update session bot: {e}")


async def clear_bot_session(admin_id: int):
    """
    Réinitialise la session bot
    """
    await update_bot_session(admin_id, "idle", {})


async def create_upload_task(episode_id: str, file_id: str) -> str:
    """
    Crée une tâche d'upload Filemoon
    """
    try:
        supabase = get_supabase()
        
        task_id = str(uuid4())
        task_data = {
            "id": task_id,
            "episode_id": episode_id,
            "file_id": file_id,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("upload_tasks").insert(task_data).execute()
        return task_id
        
    except Exception as e:
        logger.error(f"Erreur création tâche upload: {e}")
        return None


async def update_upload_task(task_id: str, status: str, progress: int = None, 
                            filemoon_code: str = None, error: str = None):
    """
    Met à jour le statut d'une tâche d'upload
    """
    try:
        supabase = get_supabase()
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if progress is not None:
            update_data["progress"] = progress
        if filemoon_code:
            update_data["filemoon_code"] = filemoon_code
        if error:
            update_data["error_message"] = error
        if status in ["completed", "failed"]:
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        supabase.table("upload_tasks").update(update_data).eq("id", task_id).execute()
        
    except Exception as e:
        logger.error(f"Erreur update tâche upload: {e}")


# ============================================================================
# REQUÊTES COMPLEXES & STATISTIQUES
# ============================================================================

async def get_show_full_details(show_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère tous les détails d'un show avec saisons et épisodes imbriqués
    """
    try:
        # Show de base
        show = await get_show_by_id(show_id)
        if not show:
            return None
        
        # Saisons avec épisodes
        seasons = await get_seasons_by_show(show_id)
        show["seasons"] = []
        
        for season in seasons:
            episodes = await get_episodes_by_season(season["id"])
            season["episodes"] = episodes
            show["seasons"].append(season)
        
        return show
        
    except Exception as e:
        logger.error(f"Erreur get_show_full_details: {e}")
        return None


async def get_stats() -> Dict[str, Any]:
    """
    Statistiques globales de la plateforme
    """
    try:
        supabase = get_supabase()
        
        # Comptages
        shows_count = supabase.table("shows").select("id", count="exact").execute().count or 0
        movies_count = supabase.table("shows").select("id", count="exact").eq("type", "movie").execute().count or 0
        series_count = supabase.table("shows").select("id", count="exact").eq("type", "series").execute().count or 0
        episodes_count = supabase.table("episodes").select("id", count="exact").execute().count or 0
        sources_count = supabase.table("video_sources").select("id", count="exact").execute().count or 0
        
        # Vues totales
        views_result = supabase.table("shows").select("views").execute()
        total_views = sum(s.get("views", 0) for s in views_result.data) if views_result.data else 0
        
        return {
            "shows": {"total": shows_count, "movies": movies_count, "series": series_count},
            "episodes": episodes_count,
            "video_sources": sources_count,
            "total_views": total_views
        }
        
    except Exception as e:
        logger.error(f"Erreur stats: {e}")
        return {}
