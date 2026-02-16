"""
Client Pyrogram - Bot Telegram ZeeXClub
Gestionnaire principal du bot
"""

import logging
import asyncio
from typing import Optional

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from pyrogram.enums import ParseMode

from config import settings
from bot.commands import setup_commands, setup_handlers
from bot.handlers import setup_additional_handlers

logger = logging.getLogger(__name__)

# Instance globale du bot
bot: Optional[Client] = None


async def start_bot():
    """
    Démarre le bot Telegram dans une boucle asyncio
    """
    global bot
    
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
        
        # Ajout session string si disponible (pour Koyeb)
        if settings.TELEGRAM_SESSION_STRING:
            logger.info("🔑 Utilisation de la session string")
            client_config["session_string"] = settings.TELEGRAM_SESSION_STRING
            # Enlever bot_token si session_string est présent (incompatible)
            del client_config["bot_token"]
        else:
            logger.info("📝 Utilisation du bot token (pas de session string)")
        
        # Création du client Pyrogram
        bot = Client(**client_config)
        
        # Configuration des commandes et handlers
        setup_commands(bot)
        setup_handlers(bot)
        setup_additional_handlers(bot)
        
        # Démarrage
        await bot.start()
        me = await bot.get_me()
        logger.info(f"✅ Bot démarré: @{me.username}")
        
        # Export session string si première connexion
        if not settings.TELEGRAM_SESSION_STRING:
            session_string = await bot.export_session_string()
            logger.info("=" * 50)
            logger.info("📝 SESSION STRING À COPIER DANS KOYEB :")
            logger.info(session_string)
            logger.info("=" * 50)
        
        # Mise à jour des commandes dans le menu - CORRIGÉ ICI
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
        if bot:
            await bot.stop()


async def stop_bot():
    """Arrête proprement le bot"""
    global bot
    if bot:
        await bot.stop()
        logger.info("🛑 Bot arrêté")


def get_bot() -> Optional[Client]:
    """Retourne l'instance du bot"""
    return bot
