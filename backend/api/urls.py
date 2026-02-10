# backend/api/urls.py
"""
Configuration des URLs API pour ZeeXClub
"""

from django.urls import path
from . import views

urlpatterns = [
    # Health check
    path('health/', views.health_check, name='health'),
    
    # Streaming
    path('stream/<str:stream_id>/', views.StreamVideoView.as_view(), name='stream'),
    
    # ========== ANCIENS ENDPOINTS (gardés pour compatibilité) ==========
    path('videos/recent/', views.get_recent_videos, name='recent_videos'),
    path('videos/search/', views.search_videos, name='search_videos'),
    path('videos/<str:video_id>/', views.get_video_detail, name='video_detail'),
    path('folders/', views.get_all_folders, name='all_folders'),
    path('folders/<str:folder_id>/', views.get_folder_contents, name='folder_contents'),
    
    # ========== NOUVEAUX ENDPOINTS NETFLIX-STYLE ==========
    # Recherche de séries/films (dossiers)
    path('search/', views.search_folders_netflix, name='search_folders'),
    
    # Détails d'une série/film avec saisons/épisodes
    path('folders/<str:folder_id>/details/', views.get_folder_details_netflix, name='folder_details_netflix'),
    
    # Détails d'un épisode spécifique (avec next/prev)
    path('episodes/<str:video_id>/', views.get_episode_details, name='episode_details'),
    
    # ========== USER (inchangé) ==========
    path('user/history/', views.get_watch_history, name='watch_history'),
    path('user/history/update/', views.update_watch_progress, name='update_progress'),
    path('user/watchlist/', views.get_watchlist, name='get_watchlist'),
    path('user/watchlist/add/', views.add_to_watchlist, name='add_watchlist'),
    path('user/watchlist/<str:video_id>/', views.remove_from_watchlist, name='remove_watchlist'),
    
    # ========== COMMENTAIRES (inchangé) ==========
    path('comments/<str:video_id>/', views.get_comments, name='get_comments'),
    path('comments/post/', views.post_comment, name='post_comment'),
    
    # ========== TMDB (inchangé) ==========
    path('tmdb/enrich/<str:folder_id>/', views.enrich_folder, name='enrich_folder'),
    path('tmdb/search/', views.search_tmdb, name='search_tmdb'),
]
