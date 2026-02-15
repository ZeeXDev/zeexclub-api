"""
Client Pyrogram - Bot Telegram ZeeXClub
Gestionnaire principal du bot
"""

import logging
import asyncio
from typing import Optional

from pyrogram import Client, idle
from pyrogram.enums import ParseMode

from config import settings
from bot.commands import setup_commands
from bot.handlers import setup_handlers

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
        
        # Création du client Pyrogram
        bot = Client(
            name="zeexclub_bot",
            api_id=settings.TELEGRAM_API_ID or 2040,  # Default si non set
            api_hash=settings.TELEGRAM_API_HASH or "b18441a1ff607e10a989891a5462e627",
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            parse_mode=ParseMode.MARKDOWN,
            workers=4,
            sleep_threshold=60
        )
        
        # Configuration des commandes et handlers
        setup_commands(bot)
        setup_handlers(bot)
        
        # Démarrage
        await bot.start()
        logger.info(f"✅ Bot démarré: @{bot.me.username}")
        
        # Mise à jour des commandes dans le menu
        await bot.set_bot_commands([
            ("start", "Démarrer le bot"),
            ("create", "Créer un nouveau show"),
            ("add", "Ajouter un épisode"),
            ("addf", "Créer une saison/dossier"),
            ("view", "Voir un show"),
            ("docs", "Lister les shows"),
            ("done", "Finaliser upload Filemoon"),
            ("help", "Aide détaillée"),
            ("cancel", "Annuler l'opération en cours")
        ])
        
        # Garder le bot en vie
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Erreur bot: {e}")
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
