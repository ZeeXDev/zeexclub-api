"""
Dépendances FastAPI - Authentification, sécurité, middleware
"""

import logging
from typing import Optional
from fastapi import Header, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """
    Vérifie la clé API pour les endpoints sensibles
    À utiliser pour les appels internes ou admin
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Clé API manquante")
    
    # Comparer avec une clé stockée en env ou générée
    expected_key = settings.SECRET_KEY[:32]  # Simplification, à améliorer
    
    if x_api_key != expected_key:
        logger.warning(f"Tentative d'accès avec clé API invalide: {x_api_key[:10]}...")
        raise HTTPException(status_code=403, detail="Clé API invalide")
    
    return True


async def get_pagination_params(
    page: int = 1,
    limit: int = 20,
    sort_by: Optional[str] = "created_at",
    order: Optional[str] = "desc"
):
    """
    Paramètres de pagination standardisés
    """
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100  # Max 100 items par page
    
    order = order.lower() if order in ["asc", "desc"] else "desc"
    
    return {
        "page": page,
        "limit": limit,
        "offset": (page - 1) * limit,
        "sort_by": sort_by,
        "order": order
    }


async def verify_origin(request: Request):
    """
    Vérifie que la requête vient d'une origine autorisée
    """
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    
    allowed_origins = [
        settings.FRONTEND_URL,
        "http://zeexclub.vercel.app",
        "http://127.0.0.1:5500"
    ]
    
    # Vérifier si l'origine est autorisée
    is_allowed = any(
        allowed in origin or allowed in referer 
        for allowed in allowed_origins
    )
    
    if not is_allowed and not settings.DEBUG:
        logger.warning(f"Origine non autorisée: {origin}, referer: {referer}")
        # On ne bloque pas en production si l'origin est vide (mobile apps)
        if origin:
            raise HTTPException(status_code=403, detail="Origine non autorisée")
    
    return True


class RateLimiter:
    """
    Rate limiter simple basé sur IP
    À remplacer par Redis en production haute charge
    """
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # IP -> [timestamps]
    
    async def check(self, request: Request):
        """Vérifie si la requête respecte le rate limit"""
        # Simplification: à implémenter avec Redis pour production
        return True


rate_limiter = RateLimiter()


async def rate_limit(request: Request):
    """Dépendance de rate limiting"""
    await rate_limiter.check(request)
    return True
