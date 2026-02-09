# backend/api/middleware.py
"""
Middleware personnalisé pour ZeeXClub API
"""

import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class SupabaseAuthMiddleware:
    """
    Middleware pour authentifier les requêtes via Supabase JWT
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Vérifier le header Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                # Import local pour éviter les dépendances circulaires au démarrage
                from database.supabase_client import supabase_manager
                
                # Vérifier le token avec Supabase
                # Note: En production, utilisez pyjwt pour décoder localement
                # ou faites une requête à l'API Supabase
                try:
                    user_response = supabase_manager.client.auth.get_user(token)
                    
                    if user_response and user_response.user:
                        request.user = user_response.user
                        request.user_id = user_response.user.id
                        request.auth_token = token
                    else:
                        request.user = None
                        request.user_id = None
                        request.auth_token = None
                        
                except Exception as e:
                    logger.warning(f"⚠️ Token invalide ou expiré: {e}")
                    request.user = None
                    request.user_id = None
                    request.auth_token = None
                    
            except ImportError as e:
                logger.error(f"❌ Impossible d'importer supabase_manager: {e}")
                request.user = None
                request.user_id = None
                request.auth_token = None
            except Exception as e:
                logger.warning(f"⚠️ Erreur auth: {e}")
                request.user = None
                request.user_id = None
                request.auth_token = None
        else:
            request.user = None
            request.user_id = None
            request.auth_token = None
        
        response = self.get_response(request)
        return response


class CORSMiddleware:
    """
    Middleware CORS simple (complément à django-cors-headers si besoin)
    Ajoute les headers CORS aux réponses d'erreur aussi
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Gérer les requêtes OPTIONS (preflight)
        if request.method == 'OPTIONS':
            response = JsonResponse({})
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
            response['Access-Control-Max-Age'] = '86400'
            return response
        
        response = self.get_response(request)
        
        # Headers CORS (s'ils ne sont pas déjà présents)
        if 'Access-Control-Allow-Origin' not in response:
            response['Access-Control-Allow-Origin'] = '*'
        if 'Access-Control-Allow-Methods' not in response:
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        if 'Access-Control-Allow-Headers' not in response:
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        
        return response


class LoggingMiddleware:
    """
    Middleware pour logger toutes les requêtes API
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Logger la requête
        user_info = getattr(request, 'user_id', 'anonymous')
        logger.info(f"📥 {request.method} {request.path} - User: {user_info}")
        
        response = self.get_response(request)
        
        # Logger la réponse
        logger.info(f"📤 {response.status_code} {request.path}")
        
        return response
