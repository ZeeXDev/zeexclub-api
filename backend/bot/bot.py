# backend/bot/bot.py
"""
Bot Telegram ZeeXClub - VERSION WEB SERVICE
Tourne avec un serveur HTTP factice pour Render
"""

import logging
import sys
import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Ajouter le parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyrogram import Client, filters, idle, enums
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

# ✅ CORRECTION: Imports optionnels avec fallback
try:
    from bot.commands import setup_commands
    from bot.handlers import setup_handlers
    from bot.sessions import SessionManager
    BOT_MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Modules bot non disponibles: {e}")
    BOT_MODULES_AVAILABLE = False
    
    # Fallback: classes vides
    def setup_commands(app, session_manager):
        pass
    
    def setup_handlers(app, session_manager):
        pass
    
    class SessionManager:
        def __init__(self):
            self.sessions = {}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


# =============================================================================
# SERVEUR HTTP FACTICE (pour Render)
# =============================================================================

class HealthHandler(BaseHTTPRequestHandler):
    """Handler simple pour health check Render"""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "service": "zeexclub-bot"}')
    
    def log_message(self, format, *args):
        # Silence les logs HTTP
        pass


def start_health_server(port=10000):
    """Démarre un serveur HTTP minimal pour le health check"""
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"🌐 Serveur health check démarré sur le port {port}")
        
        # Tourne dans un thread séparé
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        return server
    except Exception as e:
        logger.error(f"❌ Erreur serveur health: {e}")
        return None


# =============================================================================
# BOT TELEGRAM
# =============================================================================

class ZeeXClubBot:
    """Bot principal"""
    
    def __init__(self):
        self.app = None
        self.session_manager = SessionManager()
        self._running = False
        
    async def initialize(self):
        """Initialise le client Pyrogram"""
        try:
            errors = validate_config()
            if errors:
                for error in errors:
                    logger.error(f"  - {error}")
                return False
            
            if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN]):
                logger.error("❌ Credentials manquants!")
                return False
            
            self.app = Client(
                "zeexclub_bot",
                api_id=TELEGRAM_API_ID,
                api_hash=TELEGRAM_API_HASH,
                bot_token=TELEGRAM_BOT_TOKEN,
                workers=50,
                parse_mode=enums.ParseMode.MARKDOWN)
            
            # Setup des commandes et handlers (si disponibles)
            if BOT_MODULES_AVAILABLE:
                setup_commands(self.app, self.session_manager)
                setup_handlers(self.app, self.session_manager)
            
            logger.info("✅ Bot initialisé")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur init: {e}")
            return False
    
    async def run(self):
        """Démarre le bot"""
        if not self.app:
            if not await self.initialize():
                return
        
        logger.info("🚀 Démarrage bot...")
        logger.info(f"👥 Admins: {ADMIN_IDS}")
        
        try:
            await self.app.start()
            self._running = True
            
            logger.info("=" * 50)
            logger.info("✅ BOT CONNECTÉ!")
            logger.info("⏳ En attente de messages...")
            logger.info("=" * 50)
            
            # ✅ CORRECTION: Utiliser idle() de Pyrogram au lieu d'une boucle while
            # idle() gère proprement les signaux et les mises à jour
            await idle()
                
        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
        finally:
            self._running = False
            # ✅ CORRECTION: Gestion d'erreur pour stop()
            try:
                if self.app:
                    await self.app.stop()
            except Exception as stop_error:
                logger.warning(f"⚠️ Erreur lors de l'arrêt: {stop_error}")


# Instance globale
bot_instance = ZeeXClubBot()


async def main():
    """Fonction principale async"""
    # Démarrer le serveur health check
    start_health_server()
    
    # Démarrer le bot
    await bot_instance.run()


def run():
    """Point d'entrée synchrone"""
    try:
        print("=" * 60, flush=True)
        print("🚀 ZeeXClub BOT - Web Service Mode", flush=True)
        print("=" * 60, flush=True)
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n👋 Arrêt demandé par l'utilisateur", flush=True)
    except Exception as e:
        print(f"❌ FATAL: {e}", flush=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run()
