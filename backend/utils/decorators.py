"""
Décorateurs utilitaires pour FastAPI
Auth, cache, rate limiting, etc.
"""

import logging
import functools
import time
from typing import Callable, Optional, Any
from functools import wraps

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# DÉCORATEURS D'AUTHENTIFICATION
# ============================================================================

def require_api_key(func: Callable) -> Callable:
    """
    Décorateur qui requiert une clé API valide
    
    Usage:
        @require_api_key
        async def my_endpoint(request: Request):
            ...
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            raise HTTPException(status_code=401, detail="Clé API manquante (header X-API-Key)")
        
        # Vérification (à adapter selon votre logique d'API key)
        expected_key = settings.SECRET_KEY[:32]
        
        if api_key != expected_key:
            logger.warning(f"Tentative avec clé API invalide: {request.client.host}")
            raise HTTPException(status_code=403, detail="Clé API invalide")
        
        return await func(request, *args, **kwargs)
    
    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    Décorateur qui vérifie si l'utilisateur est admin
    Pour les endpoints sensibles
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Extraction user_id du token ou session
        # Cette implémentation est simplifiée
        
        admin_token = request.headers.get('X-Admin-Token')
        
        if not admin_token:
            raise HTTPException(status_code=401, detail="Authentification requise")
        
        # Vérification (à adapter avec vraie logique JWT)
        if admin_token != settings.SECRET_KEY:
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        return await func(request, *args, **kwargs)
    
    return wrapper


# ============================================================================
# DÉCORATEURS DE CACHE
# ============================================================================

def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Décorateur de cache simple (en mémoire)
    
    Args:
        ttl: Temps de vie en secondes
        key_prefix: Préfixe pour la clé de cache
    
    Usage:
        @cached(ttl=600, key_prefix="shows")
        async def get_shows():
            ...
    """
    cache = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Construction de la clé de cache
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Vérification cache
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl:
                    logger.debug(f"Cache hit: {cache_key}")
                    return result
            
            # Exécution et mise en cache
            result = await func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            
            # Nettoyage périodique (simple)
            if len(cache) > 1000:
                now = time.time()
                expired = [k for k, v in cache.items() if now - v[1] > ttl]
                for k in expired:
                    del cache[k]
            
            return result
        
        # Fonction pour invalider le cache
        wrapper.invalidate = lambda: cache.clear()
        
        return wrapper
    return decorator


def cache_response(ttl: int = 300):
    """
    Décorateur pour cacher les réponses HTTP
    Version pour FastAPI avec gestion Request
    """
    def decorator(func: Callable) -> Callable:
        cache_store = {}
        
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            cache_key = f"{request.url.path}:{request.query_params}"
            
            # Vérification cache
            if cache_key in cache_store:
                result, timestamp = cache_store[cache_key]
                if time.time() - timestamp < ttl:
                    return result
            
            # Exécution
            result = await func(request, *args, **kwargs)
            
            # Mise en cache si succès
            if isinstance(result, dict) and not result.get('error'):
                cache_store[cache_key] = (result, time.time())
            
            return result
        
        return wrapper
    return decorator


# ============================================================================
# DÉCORATEURS DE LOGGING & MONITORING
# ============================================================================

def log_execution_time(func: Callable) -> Callable:
    """
    Décorateur qui log le temps d'exécution d'une fonction
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"{func.__name__} exécuté en {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"{func.__name__} échoué après {duration:.3f}s: {e}")
            raise
    
    return wrapper


def log_requests(func: Callable) -> Callable:
    """
    Décorateur qui log les détails des requêtes
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        
        logger.info(f"→ {method} {path} from {client_ip}")
        
        start = time.time()
        try:
            response = await func(request, *args, **kwargs)
            duration = time.time() - start
            logger.info(f"← {method} {path} - OK ({duration:.3f}s)")
            return response
        except HTTPException as e:
            duration = time.time() - start
            logger.warning(f"← {method} {path} - HTTP {e.status_code} ({duration:.3f}s)")
            raise
        except Exception as e:
            duration = time.time() - start
            logger.error(f"← {method} {path} - ERROR: {e} ({duration:.3f}s)")
            raise
    
    return wrapper


# ============================================================================
# DÉCORATEURS DE GESTION D'ERREURS
# ============================================================================

def handle_errors(default_message: str = "Erreur serveur", 
                  log_errors: bool = True):
    """
    Décorateur qui capture et formate les erreurs
    
    Args:
        default_message: Message par défaut en cas d'erreur
        log_errors: Si True, log les erreurs
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                if log_errors:
                    logger.error(f"Erreur dans {func.__name__}: {e}", exc_info=True)
                
                raise HTTPException(
                    status_code=500,
                    detail=f"{default_message}: {str(e)}" if settings.DEBUG else default_message
                )
        
        return wrapper
    return decorator


def retry_on_error(max_retries: int = 3, 
                   exceptions: tuple = (Exception,),
                   delay: float = 1.0):
    """
    Décorateur qui retry en cas d'erreur
    
    Args:
        max_retries: Nombre maximum de tentatives
        exceptions: Tuple d'exceptions à capturer
        delay: Délai entre les tentatives (secondes)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Tentative {attempt + 1}/{max_retries} échouée pour {func.__name__}: {e}")
                        time.sleep(delay * (attempt + 1))  # Backoff exponentiel simple
                    else:
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator


# ============================================================================
# DÉCORATEURS DE RATE LIMITING (SIMPLE)
# ============================================================================

class SimpleRateLimiter:
    """
    Rate limiter simple en mémoire
    Pour production, utiliser Redis
    """
    def __init__(self, max_requests: int = 60, window: int = 60):
        self.max_requests = max_requests
        self.window = window  # secondes
        self.requests = {}  # ip -> [(timestamp, count)]
    
    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        
        # Nettoyage anciennes entrées
        if ip in self.requests:
            self.requests[ip] = [
                (ts, count) for ts, count in self.requests[ip] 
                if now - ts < self.window
            ]
        else:
            self.requests[ip] = []
        
        # Comptage
        total = sum(count for ts, count in self.requests[ip])
        
        if total >= self.max_requests:
            return False
        
        # Ajout requête actuelle
        self.requests[ip].append((now, 1))
        return True
    
    def get_remaining(self, ip: str) -> int:
        if ip not in self.requests:
            return self.max_requests
        
        now = time.time()
        total = sum(count for ts, count in self.requests[ip] if now - ts < self.window)
        return max(0, self.max_requests - total)


# Instance globale
rate_limiter = SimpleRateLimiter()


def rate_limit(max_requests: int = 60, window: int = 60):
    """
    Décorateur de rate limiting
    
    Args:
        max_requests: Nombre max de requêtes
        window: Fenêtre de temps en secondes
    """
    limiter = SimpleRateLimiter(max_requests, window)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = request.client.host if request.client else "unknown"
            
            if not limiter.is_allowed(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail="Trop de requêtes. Veuillez réessayer plus tard.",
                    headers={"Retry-After": str(window)}
                )
            
            # Ajout headers informatifs
            response = await func(request, *args, **kwargs)
            
            if isinstance(response, dict):
                response['rate_limit'] = {
                    'remaining': limiter.get_remaining(client_ip),
                    'limit': max_requests,
                    'window': window
                }
            
            return response
        
        return wrapper
    return decorator


# ============================================================================
# DÉCORATEURS DE VALIDATION
# ============================================================================

def validate_json_schema(schema: dict):
    """
    Décorateur qui valide le JSON d'entrée selon un schéma
    Utilise une validation simple (pas JSON Schema complet)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            try:
                body = await request.json()
            except:
                raise HTTPException(status_code=400, detail="JSON invalide")
            
            # Vérification champs requis
            required = schema.get('required', [])
            for field in required:
                if field not in body:
                    raise HTTPException(status_code=400, detail=f"Champ requis manquant: {field}")
            
            # Vérification types (simplifiée)
            properties = schema.get('properties', {})
            for field, config in properties.items():
                if field in body:
                    expected_type = config.get('type')
                    value = body[field]
                    
                    type_map = {
                        'string': str,
                        'integer': int,
                        'number': (int, float),
                        'boolean': bool,
                        'array': list,
                        'object': dict
                    }
                    
                    if expected_type and expected_type in type_map:
                        if not isinstance(value, type_map[expected_type]):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Type invalide pour {field}: attendu {expected_type}"
                            )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# UTILITAIRES DE DÉCORATION DE CLASSES
# ============================================================================

def apply_decorators_to_methods(decorator, methods: Optional[list] = None):
    """
    Applique un décorateur à toutes les méthodes d'une classe
    Utile pour appliquer auth à tout un contrôleur
    
    Usage:
        @apply_decorators_to_methods(require_api_key)
        class MyController:
            ...
    """
    def decorator_class(cls):
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                if methods is None or attr_name in methods:
                    setattr(cls, attr_name, decorator(attr))
        return cls
    return decorator_class
