# backend/bot/bot.py
"""
Bot Telegram ZeeXClub - Point d'entrée principal
Gestionnaire de contenu vidéo via Pyrogram - VERSION ASYNC
"""

import logging
import sys
import os
import asyncio

# Ajouter le parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.handlers import MessageHandler
from pyrogram.errors import FloodWait, UserNotParticipant, ChatAdminRequired

from config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_BOT_TOKEN,
    ADMIN_IDS,
    validate_config
)
from bot.commands import setup_commands
from bot.handlers import setup_handlers
from bot.sessions import SessionManager

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


class ZeeXClubBot:
    """
    Classe principale du bot ZeeXClub
    Gère l'initialisation, les commandes et les sessions
    """
    
    def __init__(self):
        self.app = None
        self.session_manager = SessionManager()
        self._running = False
        
    async def initialize(self):
        """Initialise le client Pyrogram (VERSION ASYNC)"""
        try:
            # Valider la configuration avant démarrage
            errors = validate_config()
            if errors:
                logger.error("❌ Configuration invalide:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False
            
            # Vérifier que les credentials sont présents
            if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN]):
                logger.error("❌ Credentials Telegram manquants!")
                return False
            
            # Créer le client Pyrogram
            self.app = Client(
                "zeexclub_bot",
                api_id=TELEGRAM_API_ID,
                api_hash=TELEGRAM_API_HASH,
                bot_token=TELEGRAM_BOT_TOKEN,
                workers=50,
                parse_mode="markdown"
            )
            
            # Configurer les commandes et handlers
            setup_commands(self.app, self.session_manager)
            setup_handlers(self.app, self.session_manager)
            
            # Handler pour les erreurs globales
            error_handler = MessageHandler(
                self._error_handler,
                filters.all & filters.private
            )
            self.app.add_handler(error_handler, group=-1)
            
            logger.info("✅ Bot initialisé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation bot: {e}", exc_info=True)
            return False
    
    async def _error_handler(self, client, message, exception):
        """Handler global pour capturer les erreurs"""
        logger.error(f"❌ Erreur non capturée: {exception}", exc_info=True)
        try:
            if hasattr(message, 'reply'):
                await message.reply(
                    "❌ **Une erreur est survenue**\n\n"
                    "L'administrateur a été notifié. Réessayez plus tard."
                )
        except:
            pass
    
    async def run(self):
        """
        Démarre le bot (VERSION ASYNC COMPLÈTE)
        """
        if not self.app:
            initialized = await self.initialize()
            if not initialized:
                logger.error("❌ Impossible d'initialiser le bot")
                return
        
        logger.info("🚀 Démarrage du bot ZeeXClub...")
        logger.info(f"👥 Admins autorisés: {ADMIN_IDS}")
        
        try:
            # Démarrer le client
            await self.app.start()
            self._running = True
            
            logger.info("=" * 50)
            logger.info("✅ BOT CONNECTÉ À TELEGRAM!")
            logger.info("⏳ En attente de messages...")
            logger.info("=" * 50)
            
            # Garder le bot en vie avec idle()
            await idle()
                
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé (KeyboardInterrupt)")
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        finally:
            self._running = False
            try:
                if self.app:
                    await self.app.stop()
                    logger.info("🛑 Bot arrêté proprement")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'arrêt: {e}")
    
    async def stop(self):
        """Arrête le bot proprement"""
        logger.info("🛑 Arrêt du bot demandé...")
        self._running = False


# Instance globale du bot (singleton)
bot_instance = ZeeXClubBot()


def run_bot_sync():
    """
    Point d'entrée synchrone pour démarrer le bot.
    Utilise asyncio.run() pour créer une boucle d'événements propre.
    """
    try:
        print("=" * 60, flush=True)
        print("🚀 DÉMARRAGE DU BOT TELEGRAM ZeeXClub", flush=True)
        print("=" * 60, flush=True)
        
        # asyncio.run() crée une nouvelle boucle d'événements et la ferme proprement
        asyncio.run(bot_instance.run())
        
    except Exception as e:
        print(f"❌ ERREUR FATALE: {e}", flush=True)
        import traceback
        traceback.print_exc()


# Point d'entrée pour exécution directe
if __name__ == "__main__":
    run_bot_sync()
