# backend/api/views.py
"""
Vues API REST pour ZeeXClub
Endpoints pour le frontend et le streaming
"""

import logging
import asyncio
import threading
from django.http import StreamingHttpResponse, JsonResponse, Http404
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
    STREAM_CHUNK_SIZE
)
from services.stream_handler import get_file_id_from_stream_id, validate_stream_token
from database.supabase_client import supabase_manager

logger = logging.getLogger(__name__)

# Client Pyrogram global pour le streaming (singleton)
_stream_client = None
_stream_lock = threading.Lock()

def get_stream_client():
    """Singleton pour le client de streaming"""
    global _stream_client
    if _stream_client is None:
        with _stream_lock:
            if _stream_client is None:
                try:
                    from pyrogram import Client
                    _stream_client = Client(
                        "zeex_streamer",
                        api_id=TELEGRAM_API_ID,
                        api_hash=TELEGRAM_API_HASH,
                        bot_token=TELEGRAM_BOT_TOKEN,
                        in_memory=True,
                        no_updates=True
                    )
                    # Démarrer le client de manière synchrone
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_stream_client.start())
                    logger.info("✅ Client de streaming Pyrogram démarré")
                except Exception as e:
                    logger.error(f"❌ Erreur démarrage client streaming: {e}")
                    raise
    return _stream_client

# =============================================================================
# ENDPOINTS DE STREAMING
# =============================================================================

class StreamVideoView(APIView):
    """
    Vue pour streamer une vidéo depuis Telegram
    URL: /api/stream/<stream_id>/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, stream_id):
        """Gère le streaming d'une vidéo"""
        try:
            # Valider le format du stream_id
            if not validate_stream_token(stream_id):
                return Response({'error': 'Invalid stream ID format'}, status=400)
            
            # Récupérer le file_id
            file_id = get_file_id_from_stream_id(stream_id)
            if not file_id:
                raise Http404("Stream not found")
            
            # Récupérer les infos de la vidéo
            video = supabase_manager.get_video_by_file_id(file_id)
            
            logger.info(f"📺 Streaming demandé: {stream_id[:8]}... -> {video.get('title', 'Unknown')[:30] if video else 'Unknown'}...")
            
            return self._stream_video(file_id, video)
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"❌ Erreur streaming {stream_id}: {e}", exc_info=True)
            return Response({'error': 'Streaming error'}, status=500)
    
    def _stream_video(self, file_id, video_info):
        """Stream le fichier depuis Telegram"""
        try:
            client = get_stream_client()
            
            # Générateur asynchrone pour les chunks
            async def chunk_generator():
                try:
                    # Télécharger par chunks depuis Telegram
                    async for chunk in client.stream_media(file_id, limit=STREAM_CHUNK_SIZE):
                        yield chunk
                except Exception as e:
                    logger.error(f"❌ Erreur pendant le streaming: {e}")
                    raise
            
            # Wrapper synchrone pour Django
            def sync_generator():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    async_gen = chunk_generator()
                    while True:
                        try:
                            chunk = loop.run_until_complete(async_gen.__anext__())
                            yield chunk
                        except StopAsyncIteration:
                            break
                finally:
                    loop.close()
            
            # Déterminer le content-type
            content_type = 'video/mp4'
            if video_info and video_info.get('mime_type'):
                content_type = video_info['mime_type']
            
            response = StreamingHttpResponse(
                sync_generator(),
                content_type=content_type
            )
            
            # Headers pour le streaming
            response['Accept-Ranges'] = 'bytes'
            response['Cache-Control'] = 'public, max-age=3600'
            
            if video_info:
                if video_info.get('file_size'):
                    response['Content-Length'] = str(video_info['file_size'])
                if video_info.get('title'):
                    safe_title = video_info['title'].replace('"', '\\"')[:50]
                    response['Content-Disposition'] = f'inline; filename="{safe_title}.mp4"'
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Erreur _stream_video: {e}", exc_info=True)
            return Response({'error': 'Stream failed'}, status=500)


# =============================================================================
# ENDPOINTS API POUR LE FRONTEND
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_recent_videos(request):
    """Récupère les vidéos récentes pour la page d'accueil"""
    try:
        limit = int(request.query_params.get('limit', 12))
        videos = supabase_manager.get_recent_videos(limit=limit)
        return Response({'data': videos})
    except Exception as e:
        logger.error(f"❌ Erreur get_recent_videos: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_video_detail(request, video_id):
    """Récupère les détails d'une vidéo spécifique"""
    try:
        video = supabase_manager.get_video_by_id(video_id, use_service=False)
        if not video:
            return Response({'error': 'Video not found'}, status=404)
        
        # Incrémenter le compteur de vues
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
        year = request.query_params.get('year')
        rating = request.query_params.get('rating')
        limit = int(request.query_params.get('limit', 20))
        
        filters = {}
        if genre:
            filters['genre'] = genre
        if year:
            filters['year'] = int(year)
        if rating:
            filters['rating'] = float(rating)
        
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
# ENDPOINTS PROTÉGÉS (UTILISATEUR CONNECTÉ)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_watch_history(request):
    """Récupère l'historique de visionnage de l'utilisateur"""
    try:
        user_id = request.user.id
        completed = request.query_params.get('completed', 'false').lower() == 'true'
        
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
        progress = request.data.get('progress', 0)
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
        limit = int(request.query_params.get('limit', 50))
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
        year = request.query_params.get('year')
        
        if not query:
            return Response({'error': 'Query parameter required'}, status=400)
        
        year_int = int(year) if year else None
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(search_and_suggest(query, year_int))
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
