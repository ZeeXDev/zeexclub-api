# backend/api/apps.py
"""
Configuration de l'application API Django
Démarre automatiquement le bot Telegram au lancement
"""

from django.apps import AppConfig
import threading
import logging
import os
import time

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    """
    Configuration personnalisée de l'app API
    Démarre le bot Telegram dans un thread séparé
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    
    def ready(self):
        """
        Méthode appelée quand Django est complètement chargé
        Démarre le bot Telegram en arrière-plan
        """
        # Éviter le double démarrage avec l'autoreload de Django
        if os.environ.get('RUN_MAIN') != 'true':
            return
        
        # Attendre un peu que tout soit initialisé
        time.sleep(2)
        
        # Démarrer le bot dans un thread séparé
        self._start_bot_thread()
    
    def _start_bot_thread(self):
        """
        Crée et démarre le thread du bot Telegram
        """
        try:
            # Importer ici pour éviter les imports circulaires
            from bot.bot import bot_instance
            
            def run_bot():
                """
                Fonction exécutée par le thread du bot
                """
                try:
                    logger.info("=" * 50)
                    logger.info("🚀 DÉMARRAGE DU BOT TELEGRAM ZeeXClub")
                    logger.info("=" * 50)
                    
                    # Initialiser et démarrer le bot
                    if bot_instance.initialize():
                        bot_instance.run()
                    else:
                        logger.error("❌ Échec de l'initialisation du bot")
                        
                except Exception as e:
                    logger.error(f"❌ Erreur fatale dans le bot: {e}", exc_info=True)
            
            # Créer le thread en daemon (s'arrête quand Django s'arrête)
            bot_thread = threading.Thread(
                target=run_bot,
                name="TelegramBot",
                daemon=True
            )
            
            # Démarrer le thread
            bot_thread.start()
            
            logger.info("✅ Thread du bot Telegram démarré avec succès")
            logger.info(f"   Thread ID: {bot_thread.ident}")
            logger.info(f"   Thread name: {bot_thread.name}")
            logger.info(f"   Daemon: {bot_thread.daemon}")
            
        except ImportError as e:
            logger.error(f"❌ Impossible d'importer le bot: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur lors du démarrage du bot: {e}", exc_info=True)
