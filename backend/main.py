"""
Point d'entrée principal ZeeXClub API
FastAPI application avec gestion du bot Telegram
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from config import settings, validate_config
from api.routes import router as api_router
from bot.bot import start_bot, stop_bot
from database.supabase_client import init_supabase, close_supabase


# Configuration logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeexclub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application
    Démarre le bot Telegram et initialise les connexions au démarrage
    """
    logger.info("🚀 Démarrage de ZeeXClub API...")
    
    # Validation configuration
    try:
        validate_config()
        logger.info("✅ Configuration validée")
    except ValueError as e:
        logger.error(f"❌ Erreur configuration: {e}")
        raise
    
    # Initialisation Supabase
    try:
        await init_supabase()
        logger.info("✅ Connexion Supabase établie")
    except Exception as e:
        logger.error(f"❌ Erreur Supabase: {e}")
        raise
    
    # Démarrage du bot Telegram dans une tâche séparée
    bot_task = None
    try:
        bot_task = asyncio.create_task(start_bot())
        logger.info("🤖 Bot Telegram démarré")
    except Exception as e:
        logger.error(f"❌ Erreur démarrage bot: {e}")
    
    yield  # L'application est prête à recevoir des requêtes
    
    # Nettoyage à l'arrêt
    logger.info("🛑 Arrêt de ZeeXClub API...")
    
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        await stop_bot()
        logger.info("🤖 Bot Telegram arrêté")
    
    await close_supabase()
    logger.info("✅ Connexions fermées")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="API de streaming ZeeXClub - Netflix-like platform",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Middleware CORS pour le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://zeexclub.vercel.app", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"]
)

# Compression GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Inclusion des routes API
app.include_router(api_router, prefix="/api")


# Health check endpoint
@app.get("/")
async def root():
    """Endpoint racine / health check"""
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "debug": settings.DEBUG
    }


@app.get("/health")
async def health_check():
    """Health check détaillé"""
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "services": {
            "api": "up",
            "database": "connected",  # À implémenter avec vrai check
            "bot": "running"
        }
    }


# Gestionnaire d'erreurs global
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestionnaire d'exceptions HTTP personnalisé"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'exceptions générales"""
    logger.error(f"Erreur non gérée sur {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Erreur interne du serveur" if not settings.DEBUG else str(exc),
            "status_code": 500,
            "path": request.url.path
        }
    )


# Middleware de logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour logger toutes les requêtes"""
    start_time = asyncio.get_event_loop().time()
    response = await call_next(request)
    process_time = asyncio.get_event_loop().time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s"
    )
    return response


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
        log_level="info"
    )
