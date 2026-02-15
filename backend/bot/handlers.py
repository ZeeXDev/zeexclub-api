"""
Handlers additionnels pour le bot Telegram
Gestion des messages texte, erreurs, etc.
"""

import logging
import re

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.commands import user_sessions, is_admin

logger = logging.getLogger(__name__)


def setup_handlers(bot: Client):
    """
    Configure les handlers supplémentaires
    """
    
    @bot.on_message(filters.text & filters.private & ~filters.command(["start", "help", "create", "add", "addf", "view", "docs", "done", "cancel"]))
    async def handle_text_message(client: Client, message: Message):
        """
        Gère les messages texte qui ne sont pas des commandes
        Utile pour les réponses contextuelles (numéro de saison personnalisé, etc.)
        """
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        session = user_sessions.get(user_id, {})
        state = session.get("state")
        
        # Attente d'un numéro de saison personnalisé
        if state == "waiting_season_number":
            text = message.text.strip()
            
            if text.isdigit():
                season_num = int(text)
                # Traitement via la logique existante dans commands.py
                from bot.commands import process_season_creation
                
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
    
    @bot.on_message(filters.private & filters.create(lambda _, __, msg: msg.video or msg.document))
    async def handle_non_command_video(client: Client, message: Message):
        """
        Gère les vidéos envoyées hors contexte /add
        """
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        session = user_sessions.get(user_id, {})
        
        # Si on n'attend pas de vidéo, informer l'utilisateur
        if session.get("state") != "waiting_video":
            await message.reply(
                "⚠️ Vous avez envoyé une vidéo sans utiliser /add d'abord.\n\n"
                "Pour ajouter un épisode:\n"
                "1. Utilisez /create pour créer un show\n"
                "2. Puis /add pour ajouter des épisodes\n"
                "3. Envoyez la vidéo avec caption S01E01"
            )
    
    @bot.on_edited_message(filters.private)
    async def handle_edited_message(client: Client, message: Message):
        """Log les messages édités (pour debug)"""
        logger.info(f"Message édité par {message.from_user.id}: {message.text or 'media'}")
    
    @bot.on_deleted_messages()
    async def handle_deleted_messages(client: Client, messages):
        """Log les messages supprimés"""
        logger.info(f"{len(messages)} messages supprimés")
