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
                # Vérifier le token avec Supabase
                from database.supabase_client import supabase_manager
                
                # Note: Supabase Python client ne gère pas nativement la vérif JWT
                # En production, utilisez pyjwt ou une validation côté Supabase
                user = supabase_manager.client.auth.get_user(token)
                
                if user and user.user:
                    request.user = user.user
                    request.user_id = user.user.id
                    
            except Exception as e:
                logger.warning(f"⚠️ Token invalide: {e}")
                request.user = None
                request.user_id = None
        else:
            request.user = None
            request.user_id = None
        
        response = self.get_response(request)
        return response


class CORSMiddleware:
    """
    Middleware CORS simple (complément à django-cors-headers si besoin)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Headers CORS
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return response


class LoggingMiddleware:
    """
    Middleware pour logger toutes les requêtes API
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Logger la requête
        logger.info(f"📥 {request.method} {request.path} - User: {getattr(request, 'user_id', 'anonymous')}")
        
        response = self.get_response(request)
        
        # Logger la réponse
        logger.info(f"📤 {response.status_code} {request.path}")
        
        return response
