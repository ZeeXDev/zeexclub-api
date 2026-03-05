"""
Point d'entrée principal ZeeXClub API
FastAPI application - Bot Telegram séparé sur Render
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
    CONFIG_AVAILABLE = True
except ImportError as e:
    CONFIG_AVAILABLE = False
    print(f"⚠️  Import error: {e}")

# Import bot uniquement si activé
try:
    from bot.bot import start_bot, stop_bot
    BOT_AVAILABLE = True
except ImportError:
    BOT_AVAILABLE = False


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
        if os.getenv("KOYEB_DEPLOYMENT"):
            logger.warning("⚠️  Mode Koyeb - continuation malgré erreur config")
    
    # Initialisation Supabase
    try:
        from database.supabase_client import init_supabase, close_supabase
        await init_supabase()
        logger.info("✅ Connexion Supabase établie")
    except Exception as e:
        logger.error(f"❌ Erreur Supabase: {e}")
        if not os.getenv("KOYEB_DEPLOYMENT"):
            raise
    
    # Démarrage du bot UNIQUEMENT si ENABLE_BOT=true (Render)
    bot_task = None
    enable_bot = os.getenv("ENABLE_BOT", "false").lower() == "true"
    
    if enable_bot and BOT_AVAILABLE:
        try:
            bot_task = asyncio.create_task(start_bot())
            logger.info("🤖 Bot Telegram démarré sur Render")
        except Exception as e:
            logger.error(f"❌ Erreur démarrage bot: {e}")
            logger.exception(e)
    else:
        logger.info(f"🤖 Bot désactivé (ENABLE_BOT={enable_bot}, BOT_AVAILABLE={BOT_AVAILABLE})")
    
    yield  # L'application est prête
    
    # Nettoyage à l'arrêt
    logger.info("🛑 Arrêt de ZeeXClub API...")
    
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        if BOT_AVAILABLE:
            await stop_bot()
        logger.info("🤖 Bot Telegram arrêté")
    
    if CONFIG_AVAILABLE:
        try:
            from database.supabase_client import close_supabase
            await close_supabase()
            logger.info("✅ Connexions fermées")
        except:
            pass


# Création de l'application FastAPI
app = FastAPI(
    title="ZeeXClub API",
    description="API de streaming ZeeXClub - Netflix-like platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ============================================================================
# CORS - CORRIGÉ DÉFINITIVEMENT
# ============================================================================

def get_cors_origins():
    """Récupère les origines CORS depuis les variables d'environnement"""
    # URLs de base SANS ESPACES
    origins = [
        "https://zeexclub.vercel.app",
        "https://zeexclub-admin.vercel.app",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://localhost:3000",
        "https://localhost:3000",
        "null",
    ]
    
    # Ajouter l'URL frontend Vercel depuis env
    frontend_url = os.getenv("FRONTEND_URL") or os.getenv("CORS_ORIGINS")
    if frontend_url:
        # Nettoyer l'URL (enlever espaces et slashs finaux)
        frontend_url = frontend_url.strip().rstrip('/')
        if frontend_url and frontend_url not in origins:
            origins.append(frontend_url)
        
        # Variantes www/non-www
        if frontend_url.startswith("https://"):
            www_variant = frontend_url.replace("https://", "https://www.")
            non_www_variant = frontend_url.replace("https://www.", "https://")
            if www_variant not in origins:
                origins.append(www_variant)
            if non_www_variant not in origins:
                origins.append(non_www_variant)
        elif frontend_url.startswith("http://"):
            www_variant = frontend_url.replace("http://", "http://www.")
            non_www_variant = frontend_url.replace("http://www.", "http://")
            if www_variant not in origins:
                origins.append(www_variant)
            if non_www_variant not in origins:
                origins.append(non_www_variant)
    
    # Origines supplémentaires depuis env
    extra_origins = os.getenv("EXTRA_CORS_ORIGINS", "")
    if extra_origins:
        for url in extra_origins.split(","):
            clean_url = url.strip().rstrip('/')
            if clean_url and clean_url not in origins:
                origins.append(clean_url)
    
    # Nettoyage final: s'assurer qu'il n'y a aucun espace
    origins = [url.strip() for url in origins if url.strip()]
    
    logger.info(f"CORS origins configurées: {origins}")
    return origins

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Authorization", "X-Requested-With"],
    max_age=86400,
)

# Compression GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ============================================================================
# ROUTES API
# ============================================================================

if CONFIG_AVAILABLE:
    app.include_router(api_router, prefix="/api")
    logger.info("✅ Routes API chargées avec préfixe /api")
else:
    @app.get("/api/{path:path}")
    async def api_unavailable():
        return JSONResponse(
            status_code=503,
            content={"error": "API non configurée", "status": "maintenance"}
        )


# ============================================================================
# Endpoints de base
# ============================================================================

@app.api_route("/", methods=["GET", "HEAD", "OPTIONS"])
async def root():
    """Endpoint racine / health check"""
    return {
        "status": "online",
        "service": "ZeeXClub API",
        "version": "1.0.0",
        "environment": "production" if os.getenv("KOYEB_DEPLOYMENT") else "development",
        "config_loaded": CONFIG_AVAILABLE,
        "bot_enabled": os.getenv("ENABLE_BOT", "false").lower() == "true"
    }


@app.api_route("/health", methods=["GET", "HEAD", "OPTIONS"])
async def health_check():
    """Health check détaillé"""
    health_data = {
        "status": "healthy",
        "services": {
            "api": "up",
            "config": "loaded" if CONFIG_AVAILABLE else "missing",
            "database": "unknown",
            "bot": "enabled" if os.getenv("ENABLE_BOT", "false").lower() == "true" else "disabled"
        }
    }
    return health_data


@app.api_route("/ready", methods=["GET", "HEAD", "OPTIONS"])
async def readiness_check():
    """Koyeb readiness probe"""
    return {"ready": True}


@app.api_route("/alive", methods=["GET", "HEAD", "OPTIONS"])
async def liveness_check():
    """Koyeb liveness probe"""
    return {"alive": True}


# ============================================================================
# OPTIONS PREFLIGHT GLOBAL - CRITIQUE POUR CORS
# ============================================================================

@app.options("/{path:path}")
async def options_handler(path: str, request: Request):
    """
    Handler OPTIONS global pour TOUTES les routes
    C'est ce qui manquait pour résoudre le CORS !
    """
    origin = request.headers.get("origin", "")
    
    # Liste des origines autorisées
    allowed = get_cors_origins()
    
    # Vérifier si l'origin est autorisée
    if origin in allowed or "*" in allowed:
        allowed_origin = origin
    else:
        allowed_origin = "https://zeexclub-admin.vercel.app"
    
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400",
        }
    )


# ============================================================================
# Gestionnaires d'erreurs
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestionnaire d'exceptions HTTP avec CORS"""
    origin = request.headers.get("origin", "https://zeexclub-admin.vercel.app")
    return JSONResponse(
        status_code=exc.status_code,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'exceptions générales avec CORS"""
    logger.error(f"Erreur non gérée sur {request.url.path}: {str(exc)}", exc_info=True)
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    origin = request.headers.get("origin", "https://zeexclub-admin.vercel.app")
    
    return JSONResponse(
        status_code=500,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
        content={
            "error": True,
            "message": "Erreur interne du serveur" if not debug_mode else str(exc),
            "status_code": 500,
            "path": request.url.path
        }
    )


# ============================================================================
# Middleware de logging
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour logger toutes les requêtes"""
    start_time = asyncio.get_event_loop().time()
    
    logger.info(f"→ {request.method} {request.url.path} - Origin: {request.headers.get('origin', 'N/A')}")
    
    response = await call_next(request)
    process_time = asyncio.get_event_loop().time() - start_time
    
    logger.info(f"← {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    # Ajouter CORS si manquant
    origin = request.headers.get("origin")
    if origin and "access-control-allow-origin" not in response.headers:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response


# Point d'entrée pour Koyeb
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        workers=1,
        log_level="info"
    )
