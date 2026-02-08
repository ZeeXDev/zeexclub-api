# backend/utils/decorators.py
"""
Décorateurs personnalisés pour ZeeXClub
"""

import logging
import time
from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def require_admin(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est admin
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request, 'user_id') or not request.user_id:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Vérifier dans la liste des admins (à adapter selon votre config)
        from config import ADMIN_IDS
        if request.user_id not in ADMIN_IDS:
            raise PermissionDenied("Admin access required")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def rate_limit(max_requests=100, window=60):
    """
    Décorateur pour limiter le nombre de requêtes par IP
    """
    # Stockage simple en mémoire (utiliser Redis en production)
    requests_cache = {}
    
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            ip = request.META.get('REMOTE_ADDR', 'unknown')
            now = time.time()
            
            # Nettoyer les anciennes entrées
            if ip in requests_cache:
                requests_cache[ip] = [t for t in requests_cache[ip] if now - t < window]
            else:
                requests_cache[ip] = []
            
            # Vérifier limite
            if len(requests_cache[ip]) >= max_requests:
                logger.warning(f"⚠️ Rate limit exceeded for IP: {ip}")
                return JsonResponse(
                    {'error': 'Rate limit exceeded. Try again later.'}, 
                    status=429
                )
            
            requests_cache[ip].append(now)
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def log_execution_time(view_func):
    """
    Décorateur pour logger le temps d'exécution d'une vue
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        start = time.time()
        response = view_func(request, *args, **kwargs)
        elapsed = time.time() - start
        
        logger.info(f"⏱️ {view_func.__name__} executed in {elapsed:.3f}s")
        
        # Ajouter header de timing
        if hasattr(response, 'headers'):
            response['X-Execution-Time'] = f'{elapsed:.3f}s'
        
        return response
    
    return _wrapped_view


def handle_exceptions(view_func):
    """
    Décorateur pour capturer et logger les exceptions
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Exception in {view_func.__name__}: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Internal server error', 'detail': str(e)}, 
                status=500
            )
    
    return _wrapped_view


def cache_response(timeout=300):
    """
    Décorateur pour cacher la réponse (simple, sans Redis)
    """
    cache = {}
    
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Générer une clé de cache basée sur la requête
            cache_key = f"{request.path}:{request.META.get('QUERY_STRING', '')}"
            
            now = time.time()
            
            # Vérifier cache
            if cache_key in cache:
                cached_response, timestamp = cache[cache_key]
                if now - timestamp < timeout:
                    logger.debug(f"💾 Cache hit for {cache_key}")
                    return cached_response
            
            # Exécuter et cacher
            response = view_func(request, *args, **kwargs)
            cache[cache_key] = (response, now)
            
            # Nettoyer ancien cache (simple)
            expired = [k for k, (_, t) in cache.items() if now - t > timeout]
            for k in expired:
                del cache[k]
            
            return response
        
        return _wrapped_view
    
    return decorator


def require_json(view_func):
    """
    Décorateur pour vérifier que la requête contient du JSON valide
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.META.get('CONTENT_TYPE', '')
            
            if 'application/json' not in content_type:
                return JsonResponse(
                    {'error': 'Content-Type must be application/json'}, 
                    status=400
                )
            
            if not request.body:
                return JsonResponse(
                    {'error': 'Empty request body'}, 
                    status=400
                )
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view
