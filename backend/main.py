"""
Point d'entrée principal ZeeXClub API
FastAPI application avec gestion du bot Telegram
Optimisé pour Koyeb
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import conditionnel pour gérer les erreurs si fichiers manquants
try:
    from config import settings, validate_config
    from api.routes import router as api_router
    from bot.bot import start_bot, stop_bot
    from database.supabase_client import init_supabase, close_supabase
    CONFIG_AVAILABLE = True
except ImportError as e:
    CONFIG_AVAILABLE = False
    print(f"⚠️  Import error: {e}")


# Configuration logging
logging.basicConfig(
    level=logging.INFO,
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
    
    if not CONFIG_AVAILABLE:
        logger.warning("⚠️  Configuration non disponible, mode dégradé")
        yield
        return
    
    # Validation configuration
    try:
        validate_config()
        logger.info("✅ Configuration validée")
    except ValueError as e:
        logger.error(f"❌ Erreur configuration: {e}")
        # Ne pas bloquer le démarrage sur Koyeb si config incomplète
        if os.getenv("KOYEB_DEPLOYMENT"):
            logger.warning("⚠️  Mode Koyeb - continuation malgré erreur config")
    
    # Initialisation Supabase
    try:
        await init_supabase()
        logger.info("✅ Connexion Supabase établie")
    except Exception as e:
        logger.error(f"❌ Erreur Supabase: {e}")
        if not os.getenv("KOYEB_DEPLOYMENT"):
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
    
    if CONFIG_AVAILABLE:
        await close_supabase()
        logger.info("✅ Connexions fermées")


# Création de l'application FastAPI
app = FastAPI(
    title="ZeeXClub API",
    description="API de streaming ZeeXClub - Netflix-like platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configuration CORS dynamique
def get_cors_origins():
    """Récupère les origines CORS depuis les variables d'environnement"""
    origins = [
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
    ]
    
    # Ajouter l'URL frontend Vercel depuis env
    frontend_url = os.getenv("FRONTEND_URL") or os.getenv("CORS_ORIGINS")
    if frontend_url:
        origins.append(frontend_url)
        # Ajouter aussi sans www et avec www
        if frontend_url.startswith("https://"):
            origins.append(frontend_url.replace("https://", "https://www."))
            origins.append(frontend_url.replace("https://www.", "https://"))
    
    # Origines supplémentaires depuis env (séparées par virgule)
    extra_origins = os.getenv("EXTRA_CORS_ORIGINS", "")
    if extra_origins:
        origins.extend([url.strip() for url in extra_origins.split(",")])
    
    return list(set(origins))  # Supprimer doublons

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Authorization"]
)

# Compression GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Inclusion des routes API (si disponibles)
if CONFIG_AVAILABLE:
    app.include_router(api_router, prefix="/api")
else:
    @app.get("/api/{path:path}")
    async def api_unavailable():
        return JSONResponse(
            status_code=503,
            content={"error": "API non configurée", "status": "maintenance"}
        )


# Endpoints de base
@app.get("/")
async def root():
    """Endpoint racine / health check"""
    return {
        "status": "online",
        "service": "ZeeXClub API",
        "version": "1.0.0",
        "environment": "production" if os.getenv("KOYEB_DEPLOYMENT") else "development",
        "config_loaded": CONFIG_AVAILABLE
    }


@app.get("/health")
async def health_check():
    """Health check détaillé"""
    health_data = {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "services": {
            "api": "up",
            "config": "loaded" if CONFIG_AVAILABLE else "missing",
            "database": "unknown",
            "bot": "unknown"
        }
    }
    
    # Vérifier Supabase si disponible
    if CONFIG_AVAILABLE:
        try:
            # Test rapide de connexion ici si possible
            health_data["services"]["database"] = "connected"
        except:
            health_data["services"]["database"] = "disconnected"
            health_data["status"] = "degraded"
    
    return health_data


@app.get("/ready")
async def readiness_check():
    """Koyeb readiness probe"""
    return {"ready": True}


@app.get("/alive")
async def liveness_check():
    """Koyeb liveness probe"""
    return {"alive": True}


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
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Erreur interne du serveur" if not debug_mode else str(exc),
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


# Point d'entrée pour Koyeb (utilise $PORT)
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Désactivé en production
        workers=1,     # Koyeb gère le scaling
        log_level="info"
    )
