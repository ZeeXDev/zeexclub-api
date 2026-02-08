# backend/bot/bot.py
"""
Bot Telegram ZeeXClub - Point d'entrée principal
Gestionnaire de contenu vidéo via Pyrogram
"""

import logging
import sys
import os

# Ajouter le parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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
        
    def initialize(self):
        """Initialise le client Pyrogram"""
        try:
            # Valider la configuration avant démarrage
            errors = validate_config()
            if errors:
                logger.error("❌ Configuration invalide:")
                for error in errors:
                    logger.error(f"  - {error}")
                sys.exit(1)
            
            # Créer le client
            self.app = Client(
                "zeexclub_bot",
                api_id=TELEGRAM_API_ID,
                api_hash=TELEGRAM_API_HASH,
                bot_token=TELEGRAM_BOT_TOKEN,
                workers=50,  # Nombre de workers pour gérer les requêtes concurrentes
                parse_mode="markdown"  # Mode parsing par défaut
            )
            
            # Configurer les commandes et handlers
            setup_commands(self.app, self.session_manager)
            setup_handlers(self.app, self.session_manager)
            
            # Handler pour les erreurs non capturées
            self.app.add_handler(
                filters.all & filters.private,
                self._error_handler,
                group=-1  # Priorité haute
            )
            
            logger.info("✅ Bot initialisé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation bot: {e}")
            return False
    
    async def _error_handler(self, client, update, exception):
        """Handler global pour capturer les erreurs"""
        logger.error(f"❌ Erreur non capturée: {exception}", exc_info=True)
        try:
            if hasattr(update, 'message') and update.message:
                await update.message.reply(
                    "❌ **Une erreur est survenue**\n\n"
                    "L'administrateur a été notifié. Réessayez plus tard."
                )
        except:
            pass
    
    def run(self):
        """Démarre le bot"""
        if not self.app:
            if not self.initialize():
                return
        
        logger.info("🚀 Démarrage du bot ZeeXClub...")
        logger.info(f"👥 Admins autorisés: {ADMIN_IDS}")
        
        try:
            self.app.run()
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt du bot (KeyboardInterrupt)")
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        finally:
            self._running = False
    
    async def start(self):
        """Démarre le bot de manière asynchrone (pour intégration avec Django)"""
        if not self.app:
            if not self.initialize():
                return False
        
        await self.app.start()
        self._running = True
        logger.info("✅ Bot démarré (mode async)")
        return True
    
    async def stop(self):
        """Arrête le bot proprement"""
        if self.app and self._running:
            await self.app.stop()
            self._running = False
            logger.info("🛑 Bot arrêté")


# Instance globale du bot
bot_instance = ZeeXClubBot()

if __name__ == "__main__":
    bot_instance.run()
