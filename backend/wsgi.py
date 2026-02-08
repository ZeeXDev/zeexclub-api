# backend/wsgi.py
"""
WSGI config for ZeeXClub project.
POINT D'ENTRÉE PRINCIPAL - Démarre Django + Bot Telegram
"""

import os
import sys
import threading
import time

# Ajouter le backend au path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# =============================================================================
# DÉMARRAGE DU BOT TELEGRAM (AVANT DJANGO)
# =============================================================================

def start_telegram_bot():
    """Démarre le bot dans un thread séparé avec sa propre boucle asyncio"""
    try:
        print("=" * 60, flush=True)
        print("🚀 LANCEMENT DU THREAD BOT TELEGRAM", flush=True)
        print("=" * 60, flush=True)
        
        # Importer la fonction synchrone qui gère asyncio.run()
        from bot.bot import run_bot_sync
        
        # Créer et démarrer le thread
        # run_bot_sync() contient asyncio.run() donc crée sa propre boucle
        bot_thread = threading.Thread(
            target=run_bot_sync,
            name="TelegramBot",
            daemon=True
        )
        
        bot_thread.start()
        
        # Attendre un peu pour voir si le thread démarre bien
        time.sleep(3)
        
        print(f"✅ Thread démarré (ID: {bot_thread.ident})", flush=True)
        print(f"✅ Thread vivant: {bot_thread.is_alive()}", flush=True)
        print("=" * 60, flush=True)
        
    except Exception as e:
        print(f"❌ Impossible de démarrer le bot: {e}", flush=True)
        import traceback
        traceback.print_exc()

# Lancer le bot immédiatement
start_telegram_bot()

# =============================================================================
# DJANGO
# =============================================================================

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
