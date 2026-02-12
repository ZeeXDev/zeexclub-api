# backend/api/views.py
"""
Vues API REST pour ZeeXClub
Endpoints pour le frontend et le streaming
"""

import logging
import threading
import requests
import re
import os
import mimetypes
from django.http import StreamingHttpResponse, JsonResponse, Http404, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from config import (
    TELEGRAM_API_ID, 
    TELEGRAM_API_HASH, 
    TELEGRAM_BOT_TOKEN,
    STREAM_CHUNK_SIZE,
    STREAM_BASE_URL
)
from services.stream_handler import get_file_id_from_stream_id, validate_stream_token
from database.supabase_client import supabase_manager

logger = logging.getLogger(__name__)


# =============================================================================
# FONCTION UTILITAIRE POUR CONVERSION SÉCURISÉE
# =============================================================================

def safe_int(value, default=None):
    """
    Convertit une valeur en int en gérant les cas 'null', '', None, 'undefined'
    """
    if value in (None, '', 'null', 'undefined'):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# =============================================================================
# ENDPOINTS DE STREAMING - VERSION FONCTIONNELLE WSGI
# =============================================================================

class StreamVideoView(APIView):
    """
    Vue pour streamer une vidéo depuis Telegram
    URL: /api/stream/<stream_id>/
    Utilise l'API HTTP directe de Telegram (compatible WSGI)
    """
    permission_classes = [AllowAny]
    
    def get(self, request, stream_id):
        """Gère le streaming d'une vidéo avec support des Range Requests"""
        try:
            # Valider le format du stream_id
            if not validate_stream_token(stream_id):
                return Response({'error': 'Invalid stream ID format'}, status=400)
            
            # Récupérer le file_id depuis la base de données
            file_id = get_file_id_from_stream_id(stream_id)
            if not file_id:
                raise Http404("Stream not found")
            
            # Récupérer les infos de la vidéo
            video = supabase_manager.get_video_by_file_id(file_id)
            video_title = video.get('title', 'video') if video else 'video'
            mime_type = video.get('mime_type', 'video/mp4') if video else 'video/mp4'
            
            logger.info(f"📺 Streaming demandé: {stream_id[:8]}... -> {video_title[:30]}...")
            
            # Récupérer le fichier depuis Telegram via HTTP API
            return self._stream_from_telegram(file_id, video_title, mime_type, request)
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"❌ Erreur streaming {stream_id}: {e}", exc_info=True)
            return Response({'error': 'Streaming error', 'details': str(e)}, status=500)
    
    def _stream_from_telegram(self, file_id, video_title, mime_type, request):
        """
        Stream le fichier depuis Telegram via l'API HTTP Bot
        Supporte les Range Requests pour la lecture progressive
        """
        try:
            # Étape 1: Obtenir le chemin du fichier via getFile
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
            file_info_response = requests.post(file_info_url, json={'file_id': file_id}, timeout=30)
            
            if file_info_response.status_code != 200:
                logger.error(f"❌ Erreur getFile: {file_info_response.text}")
                return Response({'error': 'Cannot access file'}, status=404)
            
            file_info = file_info_response.json()
            if not file_info.get('ok'):
                logger.error(f"❌ Telegram API error: {file_info}")
                return Response({'error': 'File not found on Telegram'}, status=404)
            
            file_path = file_info['result']['file_path']
            file_size = file_info['result'].get('file_size', 0)
            
            # Étape 2: Construire l'URL de téléchargement
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            
            # Étape 3: Gérer les Range Requests (pour lecture progressive)
            range_header = request.META.get('HTTP_RANGE', '')
            
            if range_header:
                # Parse Range header (ex: "bytes=0-1023")
                return self._handle_range_request(download_url, range_header, file_size, mime_type, video_title)
            else:
                # Stream complet
                return self._stream_full_file(download_url, file_size, mime_type, video_title)
                
        except Exception as e:
            logger.error(f"❌ Erreur _stream_from_telegram: {e}", exc_info=True)
            return Response({'error': 'Stream failed'}, status=500)
    
    def _handle_range_request(self, download_url, range_header, file_size, mime_type, video_title):
        """
        Gère les requêtes Range pour la lecture progressive (seek)
        """
        try:
            # Parser le header Range (ex: "bytes=0-1023" ou "bytes=1024-")
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if not range_match:
                return Response({'error': 'Invalid Range header'}, status=400)
            
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
            
            # Vérifier les limites
            if start >= file_size:
                return Response({'error': 'Range not satisfiable'}, status=416)
            
            end = min(end, file_size - 1)
            length = end - start + 1
            
            # Faire une requête range à Telegram
            headers = {'Range': f'bytes={start}-{end}'}
            telegram_response = requests.get(download_url, headers=headers, stream=True, timeout=30)
            
            if telegram_response.status_code not in (200, 206):
                logger.error(f"❌ Telegram range request failed: {telegram_response.status_code}")
                return Response({'error': 'Source unavailable'}, status=502)
            
            # Créer la réponse Django avec le bon statut 206 Partial Content
            response = StreamingHttpResponse(
                telegram_response.iter_content(chunk_size=STREAM_CHUNK_SIZE),
                status=206,
                content_type=mime_type
            )
            
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Content-Length'] = str(length)
            response['Accept-Ranges'] = 'bytes'
            response['Content-Disposition'] = f'inline; filename="{video_title}.mp4"'
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Erreur range request: {e}")
            return Response({'error': 'Range request failed'}, status=500)
    
    def _stream_full_file(self, download_url, file_size, mime_type, video_title):
        """
        Stream le fichier complet (sans Range)
        """
        try:
            telegram_response = requests.get(download_url, stream=True, timeout=30)
            
            if telegram_response.status_code != 200:
                logger.error(f"❌ Telegram request failed: {telegram_response.status_code}")
                return Response({'error': 'Source unavailable'}, status=502)
            
            # Créer la réponse de streaming
            response = StreamingHttpResponse(
                telegram_response.iter_content(chunk_size=STREAM_CHUNK_SIZE),
                content_type=mime_type
            )
            
            response['Content-Length'] = str(file_size) if file_size else telegram_response.headers.get('Content-Length', '')
            response['Accept-Ranges'] = 'bytes'
            response['Content-Disposition'] = f'inline; filename="{video_title}.mp4"'
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Erreur stream full file: {e}")
            return Response({'error': 'Stream failed'}, status=500)


# =============================================================================
# ENDPOINTS API POUR LE FRONTEND
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_recent_videos(request):
    """Récupère les vidéos récentes pour la page d'accueil"""
    try:
        limit = safe_int(request.query_params.get('limit'), 12)
        videos = supabase_manager.get_recent_videos(limit=limit)
        return Response({'data': videos})
    except Exception as e:
        logger.error(f"❌ Erreur get_recent_videos: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_trending_videos(request):
    """
    Récupère les vidéos les plus vues (trending par popularité)
    GET /api/videos/trending/?limit=12
    """
    try:
        limit = safe_int(request.query_params.get('limit'), 12)
        
        # Récupère les vidéos les plus vues, ordonnées par vues décroissantes
        # Utilise service_client pour contourner les RLS si nécessaire
        response = supabase_manager.service_client.table('videos')\
            .select('*,folders(folder_name)')\
            .order('views_count', desc=True)\
            .limit(limit)\
            .execute()
        
        videos = response.data if response.data else []
        
        return Response({
            'success': True,
            'data': videos,
            'count': len(videos)
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur get_trending_videos: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_video_detail(request, video_id):
    """Récupère les détails d'une vidéo spécifique"""
    try:
        video = supabase_manager.get_video_by_id(video_id, use_service=False)
        if not video:
            return Response({'error': 'Video not found'}, status=404)
        
        # Incrémenter le compteur de vues (fire-and-forget)
        try:
            new_count = (video.get('views_count', 0) or 0) + 1
            supabase_manager.update_video(video_id, {'views_count': new_count}, use_service=True)
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'incrémenter les vues: {e}")
        
        return Response({'data': video})
    except Exception as e:
        logger.error(f"❌ Erreur get_video_detail: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_videos(request):
    """Recherche de vidéos avec filtres"""
    try:
        query = request.query_params.get('q', '')
        genre = request.query_params.get('genre')
        year = safe_int(request.query_params.get('year'), None)
        rating = request.query_params.get('rating')
        limit = safe_int(request.query_params.get('limit'), 20)
        
        filters = {}
        if genre and genre not in ('null', '', 'undefined'):
            filters['genre'] = genre
        if year is not None:
            filters['year'] = year
        if rating and rating not in ('null', '', 'undefined'):
            try:
                filters['rating'] = float(rating)
            except (ValueError, TypeError):
                pass
        
        results = supabase_manager.search_videos(query, filters, limit)
        return Response({'data': results})
    except Exception as e:
        logger.error(f"❌ Erreur search_videos: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_folder_contents(request, folder_id):
    """Récupère le contenu d'un dossier (vidéos + sous-dossiers)"""
    try:
        folder = supabase_manager.get_folder_by_id(folder_id, use_service=False)
        if not folder:
            return Response({'error': 'Folder not found'}, status=404)
        
        videos = supabase_manager.get_videos_by_folder(folder_id)
        subfolders = supabase_manager.get_subfolders(folder_id)
        
        return Response({
            'folder': folder,
            'videos': videos,
            'subfolders': subfolders
        })
    except Exception as e:
        logger.error(f"❌ Erreur get_folder_contents: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_folders(request):
    """Récupère tous les dossiers racine"""
    try:
        folders = supabase_manager.get_all_folders(parent_id='null')
        return Response({'data': folders})
    except Exception as e:
        logger.error(f"❌ Erreur get_all_folders: {e}")
        return Response({'error': str(e)}, status=500)


# =============================================================================
# NOUVEAUX ENDPOINTS NETFLIX-STYLE (Séries → Saisons → Épisodes)
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def search_folders_netflix(request):
    """
    Recherche de SÉRIES/FILMS (dossiers) - pas d'épisodes individuels
    GET /api/search?q=loki
    """
    try:
        query = request.query_params.get('q', '').strip()
        genre = request.query_params.get('genre')
        year = safe_int(request.query_params.get('year'), None)
        media_type = request.query_params.get('type')
        limit = safe_int(request.query_params.get('limit'), 20)
        
        # Base query : dossiers racine uniquement (parent_id IS NULL)
        db_query = supabase_manager.service_client.table('folders').select('*').is_('parent_id', 'null')
        
        # Filtre recherche par nom
        if query:
            # Recherche insensible à la casse sur folder_name OU title (TMDB)
            db_query = db_query.or_(f"folder_name.ilike.%{query}%,title.ilike.%{query}%")
        
        # Filtre genre (si enrichi TMDB)
        if genre and genre not in ('null', '', 'undefined'):
            db_query = db_query.contains('genres', [genre])
        
        # Filtre année
        if year is not None:
            db_query = db_query.eq('year', year)
        
        # Filtre type (movie/tv) si enrichi TMDB
        if media_type and media_type not in ('null', '', 'undefined'):
            db_query = db_query.eq('media_type', media_type)
        
        # Trier par date création (plus récent d'abord)
        result = db_query.order('created_at', desc=True).limit(limit).execute()
        
        folders = result.data if result.data else []
        
        # Enrichir avec compteur de vidéos/saisons
        for folder in folders:
            # Compter sous-dossiers (saisons)
            subfolders = supabase_manager.get_subfolders(folder['id'])
            folder['season_count'] = len(subfolders)
            
            # Compter vidéos totales (toutes saisons confondues)
            total_videos = supabase_manager.get_videos_by_folder(folder['id'])
            # + vidéos dans sous-dossiers
            for sub in subfolders:
                total_videos.extend(supabase_manager.get_videos_by_folder(sub['id']))
            
            folder['total_episodes'] = len(total_videos)
            folder['has_subfolders'] = len(subfolders) > 0
        
        return Response({
            'success': True,
            'query': query,
            'count': len(folders),
            'results': folders
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur search_folders: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_folder_details_netflix(request, folder_id):
    """
    Récupère détails d'une série/film avec structure saisons/épisodes
    GET /api/folders/{folder_id}/details/
    """
    try:
        # 1. Récupérer le dossier principal
        folder = supabase_manager.get_folder_by_id(folder_id)
        if not folder:
            return Response({'error': 'Dossier introuvable'}, status=404)
        
        # 2. Récupérer sous-dossiers (saisons) s'ils existent
        subfolders = supabase_manager.get_subfolders(folder_id)
        
        # Structure de réponse
        response_data = {
            'folder': folder,
            'is_series': len(subfolders) > 0,
            'seasons': []
        }
        
        if subfolders:
            # C'est une série avec saisons
            for subfolder in subfolders:
                season_num = extract_season_number(subfolder['folder_name'])
                
                # Récupérer épisodes de cette saison
                episodes = supabase_manager.get_videos_by_folder(subfolder['id'])
                
                # Trier par numéro d'épisode
                episodes.sort(key=lambda x: x.get('episode_number') or 0)
                
                season_data = {
                    'season_id': subfolder['id'],
                    'season_name': subfolder['folder_name'],
                    'season_number': season_num,
                    'episode_count': len(episodes),
                    'episodes': episodes,
                    'poster_url': subfolder.get('season_poster') or folder.get('poster_url')
                }
                
                response_data['seasons'].append(season_data)
            
            # Trier saisons par numéro
            response_data['seasons'].sort(key=lambda x: x['season_number'] or 0)
            
        else:
            # C'est un film ou série sans structure de saisons
            # Récupérer vidéos directement dans le dossier
            videos = supabase_manager.get_videos_by_folder(folder_id)
            videos.sort(key=lambda x: (x.get('season_number') or 0, x.get('episode_number') or 0))
            
            response_data['episodes'] = videos
            response_data['episode_count'] = len(videos)
        
        return Response({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur get_folder_details: {e}")
        return Response({'error': str(e)}, status=500)


def extract_season_number(folder_name: str):
    """Extrait le numéro de saison d'un nom de dossier"""
    patterns = [
        r'saison\s*(\d+)',
        r'season\s*(\d+)',
        r's(\d+)',
        r'(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, folder_name, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
    return None


@api_view(['GET'])
@permission_classes([AllowAny])
def get_episode_details(request, video_id):
    """
    Récupère détails d'un épisode spécifique avec liens de streaming
    GET /api/episodes/{video_id}/
    """
    try:
        video = supabase_manager.get_video_by_id(video_id)
        if not video:
            return Response({'error': 'Épisode introuvable'}, status=404)
        
        # Récupérer infos du dossier parent (série/saison)
        folder = supabase_manager.get_folder_by_id(video['folder_id'])
        series_name = "Inconnu"
        season_number = None
        
        if folder:
            if folder.get('parent_id'):
                # C'est un sous-dossier (saison), récupérer la série parente
                season_number = extract_season_number(folder['folder_name'])
                series = supabase_manager.get_folder_by_id(folder['parent_id'])
                series_name = series.get('title') or series.get('folder_name') if series else "Inconnu"
            else:
                series_name = folder.get('title') or folder.get('folder_name')
        
        # Construire réponse enrichie
        episode_data = {
            **video,
            'series_name': series_name,
            'season_number': season_number or video.get('season_number'),
            'stream_urls': {
                'zeex': video.get('zeex_url'),
                'filemoon': video.get('filemoon_url')
            },
            'next_episode': get_adjacent_episode(video, 'next'),
            'prev_episode': get_adjacent_episode(video, 'prev')
        }
        
        return Response({
            'success': True,
            'data': episode_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur get_episode: {e}")
        return Response({'error': str(e)}, status=500)


def get_adjacent_episode(current_video: dict, direction: str) -> dict:
    """Récupère l'épisode précédent ou suivant"""
    try:
        folder_id = current_video['folder_id']
        current_ep = current_video.get('episode_number', 0)
        current_season = current_video.get('season_number', 0)
        
        # Récupérer tous les épisodes du même dossier
        episodes = supabase_manager.get_videos_by_folder(folder_id)
        
        # Trier par saison puis épisode
        episodes.sort(key=lambda x: (x.get('season_number') or 0, x.get('episode_number') or 0))
        
        # Trouver index actuel
        current_index = None
        for i, ep in enumerate(episodes):
            if ep['id'] == current_video['id']:
                current_index = i
                break
        
        if current_index is None:
            return None
        
        if direction == 'next' and current_index < len(episodes) - 1:
            next_ep = episodes[current_index + 1]
            return {
                'id': next_ep['id'],
                'title': next_ep['title'],
                'episode_number': next_ep.get('episode_number'),
                'season_number': next_ep.get('season_number')
            }
        elif direction == 'prev' and current_index > 0:
            prev_ep = episodes[current_index - 1]
            return {
                'id': prev_ep['id'],
                'title': prev_ep['title'],
                'episode_number': prev_ep.get('episode_number'),
                'season_number': prev_ep.get('season_number')
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Erreur adjacent episode: {e}")
        return None


# =============================================================================
# ENDPOINTS PROTÉGÉS (UTILISATEUR CONNECTÉ)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_watch_history(request):
    """Récupère l'historique de visionnage de l'utilisateur"""
    try:
        user_id = request.user.id
        completed_param = request.query_params.get('completed', 'false')
        completed = completed_param.lower() == 'true'
        
        history = supabase_manager.get_watch_history(user_id, completed_only=completed)
        return Response({'data': history})
    except Exception as e:
        logger.error(f"❌ Erreur get_watch_history: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_watch_progress(request):
    """Met à jour la progression de visionnage"""
    try:
        user_id = request.user.id
        video_id = request.data.get('video_id')
        progress = safe_int(request.data.get('progress'), 0)
        completed = request.data.get('completed', False)
        
        if not video_id:
            return Response({'error': 'video_id required'}, status=400)
        
        result = supabase_manager.update_watch_history(user_id, video_id, progress, completed)
        return Response({'data': result})
    except Exception as e:
        logger.error(f"❌ Erreur update_watch_progress: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_watchlist(request):
    """Récupère la liste de l'utilisateur"""
    try:
        user_id = request.user.id
        watchlist = supabase_manager.get_watchlist(user_id)
        return Response({'data': watchlist})
    except Exception as e:
        logger.error(f"❌ Erreur get_watchlist: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_watchlist(request):
    """Ajoute une vidéo à la liste"""
    try:
        user_id = request.user.id
        video_id = request.data.get('video_id')
        
        if not video_id:
            return Response({'error': 'video_id required'}, status=400)
        
        result = supabase_manager.add_to_watchlist(user_id, video_id)
        return Response({'data': result}, status=201)
    except Exception as e:
        logger.error(f"❌ Erreur add_to_watchlist: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_watchlist(request, video_id):
    """Retire une vidéo de la liste"""
    try:
        user_id = request.user.id
        success = supabase_manager.remove_from_watchlist(user_id, video_id)
        return Response({'success': success})
    except Exception as e:
        logger.error(f"❌ Erreur remove_from_watchlist: {e}")
        return Response({'error': str(e)}, status=500)


# =============================================================================
# ENDPOINTS COMMENTAIRES
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_comments(request, video_id):
    """Récupère les commentaires d'une vidéo"""
    try:
        limit = safe_int(request.query_params.get('limit'), 50)
        comments = supabase_manager.get_comments_by_video(video_id, limit)
        return Response({'data': comments})
    except Exception as e:
        logger.error(f"❌ Erreur get_comments: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_comment(request):
    """Publie un nouveau commentaire"""
    try:
        user_id = request.user.id
        video_id = request.data.get('video_id')
        text = request.data.get('text', '').strip()
        
        if not video_id or not text:
            return Response({'error': 'video_id and text required'}, status=400)
        
        if len(text) > 1000:
            return Response({'error': 'Comment too long (max 1000 chars)'}, status=400)
        
        comment = supabase_manager.create_comment(video_id, user_id, text)
        return Response({'data': comment}, status=201)
    except Exception as e:
        logger.error(f"❌ Erreur post_comment: {e}")
        return Response({'error': str(e)}, status=500)


# =============================================================================
# ENDPOINTS TMDB ENRICHISSEMENT
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def enrich_folder(request, folder_id):
    """Déclenche l'enrichissement TMDB d'un dossier"""
    try:
        from services.tmdb_api import enrich_folder_sync
        
        force = request.data.get('force', False)
        result = enrich_folder_sync(folder_id)
        
        if result.get('success'):
            return Response({'data': result})
        else:
            return Response({'error': result.get('error')}, status=404)
    except Exception as e:
        logger.error(f"❌ Erreur enrich_folder: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_tmdb(request):
    """Recherche sur TMDB pour suggestions"""
    try:
        from services.tmdb_api import search_and_suggest
        import asyncio
        
        query = request.query_params.get('q', '')
        year = safe_int(request.query_params.get('year'), None)
        
        if not query:
            return Response({'error': 'Query parameter required'}, status=400)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(search_and_suggest(query, year))
        loop.close()
        
        return Response({'data': results})
    except Exception as e:
        logger.error(f"❌ Erreur search_tmdb: {e}")
        return Response({'error': str(e)}, status=500)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Vérifie l'état de l'API"""
    return Response({
        'status': 'ok',
        'service': 'ZeeXClub API',
        'version': '1.0.0'
    })
