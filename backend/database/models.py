# backend/database/models.py
"""
Modèles de données (schémas) pour documentation et validation
Note: Les vraies tables sont gérées par Supabase, ce sont des dataclasses
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Folder:
    """Représente un dossier (film ou série)"""
    id: str
    folder_name: str
    parent_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Champs TMDB enrichis
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    poster_url: Optional[str] = None
    poster_url_small: Optional[str] = None
    backdrop_url: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    genres: List[str] = field(default_factory=list)
    media_type: Optional[str] = None  # 'movie' ou 'tv'
    
    # Pour séries
    season_number: Optional[int] = None
    season_overview: Optional[str] = None
    season_poster: Optional[str] = None
    episode_count: Optional[int] = None


@dataclass
class Video:
    """Représente une vidéo (film ou épisode)"""
    id: str
    folder_id: str
    title: str
    file_id: str
    zeex_url: str
    created_at: Optional[str] = None
    
    # Métadonnées
    description: Optional[str] = None
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    filemoon_url: Optional[str] = None
    caption: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[int] = None
    poster_url: Optional[str] = None
    year: Optional[int] = None
    genre: List[str] = field(default_factory=list)
    rating: Optional[float] = None
    views_count: int = 0
    
    # Champs techniques
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    
    # Champs TMDB
    tmdb_episode_id: Optional[int] = None
    still_path: Optional[str] = None
    air_date: Optional[str] = None


@dataclass
class Comment:
    """Représente un commentaire"""
    id: str
    video_id: str
    user_id: str
    comment_text: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    likes: int = 0
    
    # Jointure avec users
    user_email: Optional[str] = None
    user_display_name: Optional[str] = None
    user_avatar_url: Optional[str] = None


@dataclass
class WatchlistItem:
    """Représente un élément de la liste de l'utilisateur"""
    id: str
    user_id: str
    video_id: str
    added_at: Optional[str] = None
    
    # Jointure
    video: Optional[Video] = None


@dataclass
class WatchHistoryItem:
    """Représente un élément d'historique de visionnage"""
    id: str
    user_id: str
    video_id: str
    progress: int = 0  # En secondes
    completed: bool = False
    last_watched: Optional[str] = None
    
    # Jointure
    video: Optional[Video] = None


@dataclass
class StreamMapping:
    """Mapping entre unique_id et file_id Telegram"""
    id: str
    unique_id: str
    file_id: str
    created_at: Optional[str] = None


@dataclass
class User:
    """Représente un utilisateur (depuis Supabase Auth)"""
    id: str
    email: str
    created_at: Optional[str] = None
    
    # Métadonnées
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None
