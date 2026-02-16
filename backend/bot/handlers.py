"""
Handlers additionnels pour le bot Telegram
Gestion des messages texte, erreurs, etc.
"""

import logging
import re

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.commands import user_sessions, is_admin, is_waiting_video, parse_season_episode, process_season_creation

logger = logging.getLogger(__name__)


def setup_additional_handlers(bot: Client):
    """
    Configure les handlers supplémentaires
    """
    
    @bot.on_message(filters.text & filters.private)
    async def handle_text_message(client: Client, message: Message):
        """
        Gère les messages texte qui ne sont pas des commandes
        """
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        # Ignorer les commandes déjà gérées
        if message.text.startswith('/'):
            return
        
        session = user_sessions.get(user_id, {})
        state = session.get("state")
        
        # Attente d'un numéro de saison personnalisé
        if state == "waiting_season_number":
            text = message.text.strip()
            
            if text.isdigit():
                season_num = int(text)
                
                # Création d'un faux callback pour réutiliser la fonction
                class FakeCallback:
                    def __init__(self, msg):
                        self.message = msg
                    async def answer(self):
                        pass
                
                fake_callback = FakeCallback(message)
                await process_season_creation(client, fake_callback, user_id, season_num)
                user_sessions[user_id]["state"] = "idle"
            else:
                await message.reply("❌ Veuillez entrer un numéro valide (ex: 3)")
            
            return
        
        # Message par défaut
        await message.reply(
            "❓ Commande non reconnue.\n"
            "Utilisez /help pour voir les commandes disponibles."
        )
    
    @bot.on_edited_message(filters.private)
    async def handle_edited_message(client: Client, message: Message):
        """Log les messages édités"""
        logger.info(f"Message édité par {message.from_user.id}")
    
    @bot.on_deleted_messages()
    async def handle_deleted_messages(client: Client, messages):
        """Log les messages supprimés"""
        logger.info(f"{len(messages)} messages supprimés")
