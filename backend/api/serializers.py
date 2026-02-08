# backend/api/serializers.py
"""
Sérializers Django REST Framework pour ZeeXClub
Validation et transformation des données API
"""

from rest_framework import serializers
from datetime import datetime
from typing import Dict, Any, Optional


class VideoSerializer(serializers.Serializer):
    """
    Sérializer pour les vidéos
    """
    id = serializers.UUIDField(read_only=True)
    folder_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    
    # Numérotation
    episode_number = serializers.IntegerField(required=False, allow_null=True)
    season_number = serializers.IntegerField(required=False, allow_null=True)
    
    # URLs
    zeex_url = serializers.URLField()
    filemoon_url = serializers.URLField(required=False, allow_null=True)
    poster_url = serializers.URLField(required=False, allow_null=True)
    still_path = serializers.URLField(required=False, allow_null=True)
    
    # Métadonnées
    caption = serializers.CharField(required=False, allow_blank=True)
    file_size = serializers.IntegerField(required=False, allow_null=True)
    duration = serializers.IntegerField(required=False, allow_null=True)
    width = serializers.IntegerField(required=False, allow_null=True)
    height = serializers.IntegerField(required=False, allow_null=True)
    mime_type = serializers.CharField(required=False, allow_blank=True)
    
    # Enrichissement
    year = serializers.IntegerField(required=False, allow_null=True)
    genre = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        required=False,
        allow_null=True
    )
    tmdb_episode_id = serializers.IntegerField(required=False, allow_null=True)
    air_date = serializers.DateField(required=False, allow_null=True)
    
    # Stats
    views_count = serializers.IntegerField(read_only=True, default=0)
    created_at = serializers.DateTimeField(read_only=True)
    
    def validate_title(self, value: str) -> str:
        """Valide et nettoie le titre"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Le titre doit contenir au moins 2 caractères")
        return value.strip()
    
    def validate_duration(self, value: Optional[int]) -> Optional[int]:
        """Valide la durée"""
        if value is not None and value < 0:
            raise serializers.ValidationError("La durée ne peut pas être négative")
        return value
    
    def validate_file_size(self, value: Optional[int]) -> Optional[int]:
        """Valide la taille du fichier"""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError("La taille ne peut pas être négative")
            if value > 10 * 1024 * 1024 * 1024:  # 10 GB
                raise serializers.ValidationError("Fichier trop volumineux (max 10 GB)")
        return value
    
    def validate_rating(self, value: Optional[float]) -> Optional[float]:
        """Valide la note"""
        if value is not None:
            if not 0 <= value <= 10:
                raise serializers.ValidationError("La note doit être entre 0 et 10")
        return value
    
    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Transforme les données pour la sortie"""
        data = super().to_representation(instance)
        
        # Ajouter des champs calculés
        if data.get('duration'):
            data['duration_formatted'] = self._format_duration(data['duration'])
        
        if data.get('file_size'):
            data['file_size_formatted'] = self._format_file_size(data['file_size'])
        
        # Déterminer le type
        data['type'] = 'series' if data.get('episode_number') or data.get('season_number') else 'movie'
        
        return data
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Formate une durée en secondes"""
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {mins}min"
        return f"{mins}min {secs}s" if secs > 0 else f"{mins}min"
    
    @staticmethod
    def _format_file_size(bytes_val: int) -> str:
        """Formate une taille en bytes"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} TB"


class FolderSerializer(serializers.Serializer):
    """
    Sérializer pour les dossiers
    """
    id = serializers.UUIDField(read_only=True)
    folder_name = serializers.CharField(max_length=100)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Enrichissement TMDB
    tmdb_id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    poster_url = serializers.URLField(required=False, allow_null=True)
    poster_url_small = serializers.URLField(required=False, allow_null=True)
    backdrop_url = serializers.URLField(required=False, allow_null=True)
    year = serializers.IntegerField(required=False, allow_null=True)
    rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        required=False,
        allow_null=True
    )
    genres = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    media_type = serializers.ChoiceField(
        choices=['movie', 'tv'],
        required=False,
        allow_null=True
    )
    
    # Pour séries
    season_number = serializers.IntegerField(required=False, allow_null=True)
    season_overview = serializers.CharField(required=False, allow_blank=True)
    season_poster = serializers.URLField(required=False, allow_null=True)
    episode_count = serializers.IntegerField(required=False, allow_null=True)
    
    # Stats calculées
    video_count = serializers.IntegerField(read_only=True, default=0)
    total_size = serializers.IntegerField(read_only=True, default=0)
    
    def validate_folder_name(self, value: str) -> str:
        """Valide le nom du dossier"""
        value = value.strip()
        
        if len(value) < 2:
            raise serializers.ValidationError("Le nom doit contenir au moins 2 caractères")
        
        if len(value) > 100:
            raise serializers.ValidationError("Le nom ne doit pas dépasser 100 caractères")
        
        # Caractères interdits
        forbidden = '<>:"/\\|?*'
        for char in forbidden:
            if char in value:
                raise serializers.ValidationError(f"Caractère interdit: '{char}'")
        
        return value


class CommentSerializer(serializers.Serializer):
    """
    Sérializer pour les commentaires
    """
    id = serializers.UUIDField(read_only=True)
    video_id = serializers.UUIDField()
    user_id = serializers.UUIDField(read_only=True)
    comment_text = serializers.CharField(max_length=1000)
    likes = serializers.IntegerField(read_only=True, default=0)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Jointure utilisateur
    user_email = serializers.EmailField(read_only=True, source='users.email')
    user_display_name = serializers.CharField(
        read_only=True,
        source='users.display_name',
        default=''
    )
    user_avatar_url = serializers.URLField(
        read_only=True,
        source='users.avatar_url',
        default=''
    )
    
    def validate_comment_text(self, value: str) -> str:
        """Valide et nettoie le commentaire"""
        value = value.strip()
        
        if len(value) < 3:
            raise serializers.ValidationError("Le commentaire est trop court")
        
        if len(value) > 1000:
            raise serializers.ValidationError("Le commentaire ne doit pas dépasser 1000 caractères")
        
        # Détecter les liens (optionnel: les supprimer ou marquer)
        import re
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', value)
        
        return value


class WatchHistorySerializer(serializers.Serializer):
    """
    Sérializer pour l'historique de visionnage
    """
    id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    video_id = serializers.UUIDField()
    progress = serializers.IntegerField(min_value=0, default=0)
    completed = serializers.BooleanField(default=False)
    last_watched = serializers.DateTimeField(read_only=True)
    
    # Jointure vidéo
    video = VideoSerializer(read_only=True, source='videos')
    
    # Champ calculé
    progress_percent = serializers.SerializerMethodField()
    
    def get_progress_percent(self, obj: Dict[str, Any]) -> int:
        """Calcule le pourcentage de progression"""
        video = obj.get('videos', {})
        duration = video.get('duration', 0)
        progress = obj.get('progress', 0)
        
        if not duration:
            return 0
        
        return min(int((progress / duration) * 100), 100)


class WatchlistSerializer(serializers.Serializer):
    """
    Sérializer pour la liste de l'utilisateur
    """
    id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    video_id = serializers.UUIDField()
    added_at = serializers.DateTimeField(read_only=True)
    
    # Jointure vidéo
    video = VideoSerializer(read_only=True, source='videos')


class StreamMappingSerializer(serializers.Serializer):
    """
    Sérializer pour les mappings de stream
    """
    id = serializers.UUIDField(read_only=True)
    unique_id = serializers.CharField(read_only=True)
    file_id = serializers.CharField(write_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    # Champ calculé
    stream_url = serializers.SerializerMethodField()
    
    def get_stream_url(self, obj: Dict[str, Any]) -> str:
        """Génère l'URL de streaming"""
        from config import STREAM_BASE_URL
        return f"{STREAM_BASE_URL}/stream/{obj['unique_id']}"


class TMDBSearchSerializer(serializers.Serializer):
    """
    Sérializer pour les résultats de recherche TMDB
    """
    query = serializers.CharField(required=True, min_length=2)
    year = serializers.IntegerField(required=False, allow_null=True)
    media_type = serializers.ChoiceField(
        choices=['movie', 'tv', 'all'],
        default='all'
    )


class ErrorSerializer(serializers.Serializer):
    """
    Sérializer standardisé pour les erreurs
    """
    error = serializers.CharField()
    code = serializers.CharField(required=False)
    details = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(default=datetime.utcnow)
