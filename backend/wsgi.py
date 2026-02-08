# backend/wsgi.py
"""
WSGI config for ZeeXClub project.
Démarre aussi le bot Telegram au lancement.
"""

import os
import sys
import threading
import logging

# Ajouter le backend au path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# =============================================================================
# DÉMARRAGE DU BOT TELEGRAM (avant Django)
# =============================================================================

def start_telegram_bot():
    """Démarre le bot dans un thread séparé"""
    try:
        print("=" * 60)
        print("🚀 TENTATIVE DE DÉMARRAGE DU BOT TELEGRAM")
        print("=" * 60)
        
        from bot.bot import bot_instance
        
        def run_bot():
            try:
                print("⏳ Initialisation du bot...")
                if bot_instance.initialize():
                    print("✅ Bot initialisé, démarrage...")
                    bot_instance.run()
                else:
                    print("❌ Échec initialisation bot")
            except Exception as e:
                print(f"❌ ERREUR BOT: {e}")
                import traceback
                traceback.print_exc()
        
        # Créer et démarrer le thread
        bot_thread = threading.Thread(target=run_bot, name="TelegramBot", daemon=True)
        bot_thread.start()
        
        print("✅ Thread bot démarré")
        print(f"   Thread ID: {bot_thread.ident}")
        print(f"   Thread vivant: {bot_thread.is_alive()}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Impossible de démarrer le bot: {e}")
        import traceback
        traceback.print_exc()

# Démarrer le bot immédiatement
start_telegram_bot()

# =============================================================================
# DJANGO WSGI APPLICATION
# =============================================================================

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
