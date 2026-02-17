"""
Client Pyrogram - Bot Telegram ZeeXClub
Gestionnaire principal du bot - Version Web Service pour Render
"""

import logging
import asyncio
import os
import sys
from typing import Optional

# Fix Python 3.14 event loop si nécessaire
if sys.version_info >= (3, 14):
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from pyrogram.enums import ParseMode

# Serveur HTTP pour health check Render
from aiohttp import web

# Imports relatifs pour fonctionner avec python -m bot.bot
try:
    from config import settings
    from bot.commands import setup_commands, setup_handlers
    from bot.handlers import setup_additional_handlers
    from database.supabase_client import init_supabase, close_supabase
except ImportError:
    # Fallback si exécuté différemment
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import settings
    from bot.commands import setup_commands, setup_handlers
    from bot.handlers import setup_additional_handlers
    from database.supabase_client import init_supabase, close_supabase

logger = logging.getLogger(__name__)

# Instance globale du bot
bot: Optional[Client] = None


async def health_check(request):
    """Endpoint health check pour Render"""
    return web.Response(text="✅ ZeeXClub Bot is running", status=200)


async def start_web_server():
    """Démarre le serveur web minimal pour health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    logger.info(f"🌐 Serveur health check démarré sur port {port}")
    
    return runner


async def start_bot():
    """
    Démarre le bot Telegram + serveur web pour Render
    """
    global bot
    
    # Démarrer le serveur web d'abord (pour que Render détecte le service UP)
    web_runner = await start_web_server()
    
    # Initialiser Supabase AVANT le bot
    try:
        await init_supabase()
        logger.info("✅ Connexion Supabase établie")
    except Exception as e:
        logger.error(f"❌ Erreur Supabase: {e}")
        raise
    
    try:
        logger.info("🤖 Initialisation du bot Telegram...")
        
        # Configuration de base
        client_config = {
            "name": "zeexclub_bot",
            "api_id": settings.TELEGRAM_API_ID,
            "api_hash": settings.TELEGRAM_API_HASH,
            "parse_mode": ParseMode.MARKDOWN,
            "workers": 4,
            "sleep_threshold": 60
        }
        
        # Gestion session string vs bot token
        if settings.TELEGRAM_SESSION_STRING:
            logger.info("🔑 Utilisation de la session string")
            client_config["session_string"] = settings.TELEGRAM_SESSION_STRING
        else:
            logger.info("📝 Utilisation du bot token")
            client_config["bot_token"] = settings.BOT_TOKEN
        
        # Création du client Pyrogram
        bot = Client(**client_config)
        
        # Configuration des commandes et handlers
        setup_commands(bot)
        setup_handlers(bot)
        setup_additional_handlers(bot)
        
        # Démarrage du bot
        await bot.start()
        me = await bot.get_me()
        logger.info(f"✅ Bot démarré: @{me.username}")
        
        # Export session string si première connexion
        if not settings.TELEGRAM_SESSION_STRING and not hasattr(settings, 'TELEGRAM_SESSION_STRING'):
            try:
                session_string = await bot.export_session_string()
                logger.info("=" * 50)
                logger.info("📝 SESSION STRING À SAUVEGARDER:")
                logger.info(session_string)
                logger.info("=" * 50)
            except Exception as e:
                logger.warning(f"⚠️ Impossible d'exporter la session: {e}")
        
        # Mise à jour des commandes dans le menu
        try:
            await bot.set_bot_commands([
                BotCommand("start", "Démarrer le bot"),
                BotCommand("create", "Créer un nouveau show"),
                BotCommand("add", "Ajouter un épisode"),
                BotCommand("addf", "Créer une saison/dossier"),
                BotCommand("view", "Voir un show"),
                BotCommand("docs", "Lister les shows"),
                BotCommand("done", "Finaliser upload Filemoon"),
                BotCommand("help", "Aide détaillée"),
                BotCommand("cancel", "Annuler l'opération en cours"),
            ])
            logger.info("✅ Commandes du menu mises à jour")
        except Exception as e:
            logger.warning(f"⚠️ Commandes non mises à jour: {e}")
        
        # Garder le bot en vie
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Erreur bot: {e}", exc_info=True)
        raise
    finally:
        await stop_bot()
        await web_runner.cleanup()
        await close_supabase()


async def stop_bot():
    """Arrête proprement le bot"""
    global bot
    if bot:
        await bot.stop()
        logger.info("🛑 Bot arrêté")


def get_bot() -> Optional[Client]:
    """Retourne l'instance du bot"""
    return bot


# Point d'entrée pour python -m bot.bot
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("👋 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}", exc_info=True)
        raise
