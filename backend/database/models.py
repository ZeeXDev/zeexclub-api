"""
Modèles Pydantic - Validation des données
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, validator


class ShowType(str, Enum):
    movie = "movie"
    series = "series"


class ServerName(str, Enum):
    filemoon = "filemoon"
    telegram = "telegram"


# ============================================================================
# MODÈLES SHOW (Film/Série)
# ============================================================================

class ShowBase(BaseModel):
    """Modèle de base pour un show"""
    tmdb_id: int = Field(..., description="ID TMDB")
    title: str = Field(..., min_length=1, max_length=500)
    type: ShowType
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[date] = None
    genres: Optional[List[str]] = []
    runtime: Optional[int] = None  # Durée en minutes
    rating: Optional[float] = Field(None, ge=0, le=10)
    language: Optional[str] = "fr"
    
    @validator('genres', pre=True)
    def parse_genres(cls, v):
        if isinstance(v, str):
            return [g.strip() for g in v.split(',') if g.strip()]
        return v or []


class ShowCreate(ShowBase):
    """Modèle pour création de show"""
    pass


class ShowUpdate(BaseModel):
    """Modèle pour mise à jour partielle"""
    title: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[date] = None
    genres: Optional[List[str]] = None
    rating: Optional[float] = None


class ShowInDB(ShowBase):
    """Modèle représentant un show en base de données"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    views: int = 0
    status: str = "active"  # active, archived, pending
    
    class Config:
        from_attributes = True


class ShowResponse(ShowInDB):
    """Modèle de réponse API pour un show"""
    seasons_count: Optional[int] = 0
    episodes_count: Optional[int] = 0


# ============================================================================
# MODÈLES SAISON
# ============================================================================

class SeasonBase(BaseModel):
    """Modèle de base pour une saison"""
    show_id: UUID
    season_number: int = Field(..., ge=0)
    name: Optional[str] = None
    poster: Optional[str] = None
    overview: Optional[str] = None
    air_date: Optional[date] = None


class SeasonCreate(SeasonBase):
    pass


class SeasonInDB(SeasonBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class SeasonResponse(SeasonInDB):
    episodes_count: int = 0


# ============================================================================
# MODÈLES ÉPISODE
# ============================================================================

class EpisodeBase(BaseModel):
    """Modèle de base pour un épisode"""
    season_id: UUID
    episode_number: int = Field(..., ge=1)
    title: Optional[str] = None
    overview: Optional[str] = None
    thumbnail: Optional[str] = None
    air_date: Optional[date] = None
    runtime: Optional[int] = None


class EpisodeCreate(EpisodeBase):
    pass


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    overview: Optional[str] = None
    thumbnail: Optional[str] = None


class EpisodeInDB(EpisodeBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class EpisodeResponse(EpisodeInDB):
    sources: List[Dict[str, Any]] = []


# ============================================================================
# MODÈLES SOURCE VIDÉO
# ============================================================================

class VideoSourceBase(BaseModel):
    """Modèle de base pour une source vidéo"""
    episode_id: UUID
    server_name: ServerName
    link: str
    file_id: Optional[str] = None  # Pour Telegram
    filemoon_code: Optional[str] = None  # Pour Filemoon
    quality: Optional[str] = "HD"  # SD, HD, FHD, 4K
    language: Optional[str] = "FR"
    is_active: bool = True
    file_size: Optional[int] = None  # Taille en bytes
    duration: Optional[int] = None  # Durée en secondes


class VideoSourceCreate(VideoSourceBase):
    @validator('link')
    def validate_link(cls, v, values):
        if values.get('server_name') == ServerName.filemoon and not values.get('filemoon_code'):
            raise ValueError("filemoon_code requis pour Filemoon")
        return v


class VideoSourceUpdate(BaseModel):
    link: Optional[str] = None
    is_active: Optional[bool] = None
    quality: Optional[str] = None


class VideoSourceInDB(VideoSourceBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# MODÈLES BOT & ADMIN
# ============================================================================

class BotSession(BaseModel):
    """Session de création via bot"""
    admin_id: int
    current_show_id: Optional[UUID] = None
    current_season_id: Optional[UUID] = None
    current_episode_id: Optional[UUID] = None
    state: str = "idle"  # idle, creating_show, adding_episode, selecting_season
    temp_data: Dict[str, Any] = {}
    last_activity: datetime = Field(default_factory=datetime.utcnow)


class UploadTask(BaseModel):
    """Tâche d'upload Filemoon"""
    id: UUID
    episode_id: UUID
    file_id: str  # Telegram file_id
    status: str = "pending"  # pending, uploading, processing, completed, failed
    progress: int = 0
    filemoon_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ============================================================================
# MODÈLES RÉPONSES API
# ============================================================================

class PaginatedResponse(BaseModel):
    """Réponse paginée standard"""
    success: bool = True
    data: List[Any]
    pagination: Dict[str, Any]
    filters: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Réponse d'erreur standard"""
    error: bool = True
    message: str
    status_code: int
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Réponse succès standard"""
    success: bool = True
    message: str
    data: Optional[Any] = None
