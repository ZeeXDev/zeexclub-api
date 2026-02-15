"""
Commandes du Bot Telegram ZeeXClub
/create, /add, /addf, /view, /done, etc.
"""

import logging
import re
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

from config import settings, BOT_MESSAGES, SEASON_EPISODE_PATTERNS
from database.queries import (
    create_show, get_show_by_tmdb_id, get_show_by_id,
    create_season, get_season_by_number, get_seasons_by_show,
    create_episode, get_episode_by_number,
    create_video_source, get_or_create_bot_session, update_bot_session,
    clear_bot_session, create_upload_task, update_upload_task,
    get_all_shows, get_episode_sources
)
from services.tmdb_api import search_tmdb, get_tmdb_details, get_tmdb_season
from services.filemoon_api import upload_to_filemoon
from services.stream_handler import stream_handler

logger = logging.getLogger(__name__)

# Stockage temporaire des sessions (en attendant Redis/DB)
user_sessions: Dict[int, Dict[str, Any]] = {}


def setup_commands(bot: Client):
    """
    Configure toutes les commandes du bot
    """
    
    # =========================================================================
    # COMMANDE /START
    # =========================================================================
    @bot.on_message(filters.command("start") & filters.private)
    async def start_command(client: Client, message: Message):
        """Commande de démarrage"""
        user_id = message.from_user.id
        
        # Vérification admin
        if user_id not in settings.ADMIN_USER_IDS:
            await message.reply(BOT_MESSAGES['error_not_admin'])
            return
        
        # Initialisation session
        user_sessions[user_id] = {"state": "idle", "data": {}}
        
        await message.reply(
            BOT_MESSAGES['welcome'].format(username=message.from_user.username),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # =========================================================================
    # COMMANDE /HELP
    # =========================================================================
    @bot.on_message(filters.command("help") & filters.private)
    async def help_command(client: Client, message: Message):
        """Aide détaillée"""
        help_text = """
📚 **Guide d'utilisation ZeeXClub Bot**

**Création de contenu:**

1️⃣ **Créer un film/série**
   `/create Nom du film`
   Le bot recherche sur TMDB et propose les résultats.

2️⃣ **Créer une saison** (séries uniquement)
   `/addf`
   Puis choisissez le show et le numéro de saison.

3️⃣ **Ajouter un épisode**
   `/add`
   Envoyez la vidéo avec caption: `S01E01` ou `Épisode 1`
   Le bot détecte automatiquement la saison et l'épisode.

4️⃣ **Finaliser l'upload**
   `/done`
   Upload vers Filemoon et génération des liens.

**Gestion:**

• `/view [ID]` - Voir les détails d'un show
• `/docs` - Lister tous les shows (avec pagination)
• `/cancel` - Annuler l'opération en cours

**Format des captions:**
- `S01E01` ou `s1e1` → Saison 1, Épisode 1
- `Épisode 5` → Saison en cours, Épisode 5
- `2x15` → Saison 2, Épisode 15

**Conseils:**
- Les vidéos doivent être envoyées en tant que document ou vidéo
- Attendez que chaque opération soit terminée avant de commencer la suivante
- Utilisez /cancel si vous êtes bloqué
        """
        await message.reply(help_text, parse_mode=ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE /CANCEL
    # =========================================================================
    @bot.on_message(filters.command("cancel") & filters.private)
    async def cancel_command(client: Client, message: Message):
        """Annule l'opération en cours"""
        user_id = message.from_user.id
        user_sessions[user_id] = {"state": "idle", "data": {}}
        await clear_bot_session(user_id)
        await message.reply("❌ Opération annulée. Vous pouvez recommencer.")
    
    # =========================================================================
    # COMMANDE /CREATE
    # =========================================================================
    @bot.on_message(filters.command("create") & filters.private)
    async def create_command(client: Client, message: Message):
        """Crée un nouveau show via TMDB"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        # Récupération du nom
        if len(message.command) < 2:
            await message.reply(
                "❌ Usage: `/create Nom du film ou série`\n"
                "Exemple: `/create Avengers Endgame`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        query = " ".join(message.command[1:])
        await message.reply(f"🔍 Recherche de *{query}* sur TMDB...", parse_mode=ParseMode.MARKDOWN)
        
        try:
            # Recherche film ET série
            movie_results = await search_tmdb(query, "movie")
            tv_results = await search_tmdb(query, "tv")
            
            all_results = []
            
            # Formatage résultats films
            for item in movie_results[:5]:
                all_results.append({
                    "tmdb_id": item["tmdb_id"],
                    "title": item["title"],
                    "year": item.get("release_date", "")[:4] if item.get("release_date") else "N/A",
                    "type": "movie",
                    "overview": item.get("overview", "")[:100] + "..." if len(item.get("overview", "")) > 100 else item.get("overview", ""),
                    "poster": item.get("poster_path", "")
                })
            
            # Formatage résultats séries
            for item in tv_results[:5]:
                all_results.append({
                    "tmdb_id": item["tmdb_id"],
                    "title": item["title"],
                    "year": item.get("release_date", "")[:4] if item.get("release_date") else "N/A",
                    "type": "series",
                    "overview": item.get("overview", "")[:100] + "..." if len(item.get("overview", "")) > 100 else item.get("overview", ""),
                    "poster": item.get("poster_path", "")
                })
            
            if not all_results:
                await message.reply("❌ Aucun résultat trouvé sur TMDB.")
                return
            
            # Stockage des résultats en session
            user_sessions[user_id] = {
                "state": "selecting_show",
                "results": all_results,
                "data": {}
            }
            
            # Construction des boutons
            buttons = []
            for idx, result in enumerate(all_results[:6]):  # Max 6 résultats
                type_emoji = "🎬" if result["type"] == "movie" else "📺"
                btn_text = f"{type_emoji} {result['title']} ({result['year']})"
                buttons.append([InlineKeyboardButton(btn_text, callback_data=f"create_select_{idx}")])
            
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="create_cancel")])
            
            # Envoi du message avec résultats
            text = BOT_MESSAGES['create_multiple'] + "\n\n"
            for idx, r in enumerate(all_results[:6], 1):
                emoji = "🎬" if r["type"] == "movie" else "📺"
                text += f"{idx}. {emoji} *{r['title']}* ({r['year']})\n"
                text += f"   _{r['overview'][:80]}..._\n\n"
            
            await message.reply(
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Erreur commande create: {e}")
            await message.reply(f"❌ Erreur: {str(e)}")
    
    # =========================================================================
    # COMMANDE /ADD (Ajout épisode)
    # =========================================================================
    @bot.on_message(filters.command("add") & filters.private)
    async def add_command(client: Client, message: Message):
        """Prépare l'ajout d'un épisode"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        # Vérification qu'un show est sélectionné
        session = user_sessions.get(user_id, {})
        current_show = session.get("data", {}).get("current_show")
        
        if not current_show:
            # Demander de sélectionner d'abord un show
            await list_shows_for_selection(client, message, "add_episode")
            return
        
        # Mise à jour état
        user_sessions[user_id]["state"] = "waiting_video"
        
        await message.reply(
            f"📤 Envoi d'épisode pour: *{current_show['title']}*\n\n"
            f"Envoyez la vidéo avec caption indiquant la saison et épisode:\n"
            f"• `S01E01` ou `s1e1`\n"
            f"• `Épisode 5`\n"
            f"• `2x15` (saison 2, ép 15)\n\n"
            f"_Le fichier sera stocké sur Telegram en attendant l'upload Filemoon._",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # =========================================================================
    # COMMANDE /ADDF (Création saison/dossier)
    # =========================================================================
    @bot.on_message(filters.command("addf") & filters.private)
    async def addf_command(client: Client, message: Message):
        """Crée un sous-dossier/saison"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        session = user_sessions.get(user_id, {})
        current_show = session.get("data", {}).get("current_show")
        
        if not current_show:
            await list_shows_for_selection(client, message, "create_season")
            return
        
        if current_show["type"] == "movie":
            await message.reply("❌ Les films n'ont pas de saisons!")
            return
        
        # Récupération des saisons existantes
        from database.queries import get_seasons_by_show
        seasons = await get_seasons_by_show(current_show["id"])
        next_season = len(seasons) + 1
        
        # Proposition de création
        buttons = [
            [InlineKeyboardButton(f"Créer Saison {next_season}", callback_data=f"season_create_{next_season}")],
            [InlineKeyboardButton("Autre numéro...", callback_data="season_custom")],
            [InlineKeyboardButton("❌ Annuler", callback_data="season_cancel")]
        ]
        
        await message.reply(
            f"📁 Gestion des saisons pour *{current_show['title']}*\n\n"
            f"Saisons existantes: {len(seasons)}\n"
            f"Quelle action souhaitez-vous?",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # =========================================================================
    # COMMANDE /VIEW
    # =========================================================================
    @bot.on_message(filters.command("view") & filters.private)
    async def view_command(client: Client, message: Message):
        """Affiche les détails d'un show"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        if len(message.command) < 2:
            # Lister pour sélection
            await list_shows_for_selection(client, message, "view_show")
            return
        
        show_id = message.command[1]
        await show_show_details(client, message, show_id)
    
    # =========================================================================
    # COMMANDE /DOCS (Lister shows)
    # =========================================================================
    @bot.on_message(filters.command("docs") & filters.private)
    async def docs_command(client: Client, message: Message):
        """Liste tous les shows avec pagination"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        page = 1
        if len(message.command) > 1 and message.command[1].isdigit():
            page = int(message.command[1])
        
        await list_shows_paginated(client, message, page)
    
    # =========================================================================
    # COMMANDE /DONE (Finalisation)
    # =========================================================================
    @bot.on_message(filters.command("done") & filters.private)
    async def done_command(client: Client, message: Message):
        """Finalise l'upload vers Filemoon"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        session = user_sessions.get(user_id, {})
        pending_uploads = session.get("data", {}).get("pending_uploads", [])
        
        if not pending_uploads:
            await message.reply(
                "❌ Aucun upload en attente.\n"
                "Utilisez d'abord /add pour ajouter des épisodes."
            )
            return
        
        await message.reply(f"🚀 Démarrage de l'upload Filemoon pour {len(pending_uploads)} fichier(s)...")
        
        # Traitement des uploads
        for idx, upload_info in enumerate(pending_uploads, 1):
            file_id = upload_info["file_id"]
            episode_id = upload_info["episode_id"]
            
            progress_msg = await message.reply(f"⏳ Upload {idx}/{len(pending_uploads)}: Préparation...")
            
            try:
                # Génération du lien de téléchargement Telegram
                # Note: Dans l'implémentation réelle, il faudrait générer un lien
                # temporaire ou utiliser le file_id pour l'upload remote
                
                # Simulation pour l'exemple - en prod, utiliser l'URL de notre API
                telegram_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_id}"
                
                await progress_msg.edit_text(f"⏳ Upload {idx}/{len(pending_uploads)}: Envoi à Filemoon...")
                
                # Upload Filemoon
                result = await upload_to_filemoon(telegram_url, title=upload_info.get("title", "Video"))
                
                if result["success"]:
                    # Création de la source vidéo
                    await create_video_source({
                        "episode_id": episode_id,
                        "server_name": "filemoon",
                        "link": result["player_url"],
                        "filemoon_code": result["file_code"],
                        "quality": "HD",
                        "is_active": True
                    })
                    
                    await progress_msg.edit_text(
                        f"✅ Upload terminé!\n"
                        f"Code: `{result['file_code']}`\n"
                        f"Lien: {result['player_url']}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await progress_msg.edit_text(f"❌ Échec: {result.get('error', 'Erreur inconnue')}")
                
                await asyncio.sleep(1)  # Éviter le rate limit
                
            except Exception as e:
                logger.error(f"Erreur upload {file_id}: {e}")
                await progress_msg.edit_text(f"❌ Erreur upload: {str(e)}")
        
        # Nettoyage
        user_sessions[user_id]["data"]["pending_uploads"] = []
        await message.reply("✅ Tous les uploads sont terminés!")
    
    # =========================================================================
    # HANDLER MESSAGES VIDÉO/DOCUMENT (Pour /add)
    # =========================================================================
    @bot.on_message(
        (filters.video | filters.document) & 
        filters.private & 
        filters.create(lambda _, __, msg: is_waiting_video(msg.from_user.id))
    )
    async def handle_video_upload(client: Client, message: Message):
        """Gère la réception d'une vidéo pour ajout d'épisode"""
        user_id = message.from_user.id
        session = user_sessions.get(user_id, {})
        
        current_show = session["data"].get("current_show")
        current_season = session["data"].get("current_season")
        
        if not current_show:
            await message.reply("❌ Erreur: Aucun show sélectionné. Utilisez /create d'abord.")
            return
        
        # Détection du fichier
        if message.video:
            file_id = message.video.file_id
            file_size = message.video.file_size
            duration = message.video.duration
            mime_type = message.video.mime_type
        elif message.document:
            file_id = message.document.file_id
            file_size = message.document.file_size
            mime_type = message.document.mime_type
            duration = None
        else:
            await message.reply("❌ Format non supporté.")
            return
        
        # Parsing de la caption pour SxxExx
        caption = message.caption or ""
        season_num, episode_num = parse_season_episode(caption)
        
        if season_num is None:
            season_num = current_season["season_number"] if current_season else 1
        
        if episode_num is None:
            await message.reply(
                "❌ Impossible de détecter le numéro d'épisode.\n"
                "Veuillez inclure dans la caption:\n"
                "• `S01E05` pour Saison 1 Épisode 5\n"
                "• `Épisode 3` pour l'épisode 3 de la saison en cours"
            )
            return
        
        try:
            # Récupération ou création de la saison
            from database.queries import get_season_by_number, create_season
            
            season = await get_season_by_number(current_show["id"], season_num)
            if not season:
                # Création auto de la saison
                season = await create_season({
                    "show_id": current_show["id"],
                    "season_number": season_num,
                    "name": f"Saison {season_num}"
                })
                await message.reply(f"📁 Saison {season_num} créée automatiquement.")
            
            # Création de l'épisode
            episode = await create_episode({
                "season_id": season["id"],
                "episode_number": episode_num,
                "title": caption if caption and not caption.startswith("S") else f"Épisode {episode_num}"
            })
            
            # Création source Telegram (backup)
            await create_video_source({
                "episode_id": episode["id"],
                "server_name": "telegram",
                "link": f"/api/stream/telegram/{file_id}",
                "file_id": file_id,
                "file_size": file_size,
                "duration": duration,
                "quality": "HD",
                "is_active": True
            })
            
            # Ajout à la liste d'upload Filemoon en attente
            if "pending_uploads" not in user_sessions[user_id]["data"]:
                user_sessions[user_id]["data"]["pending_uploads"] = []
            
            user_sessions[user_id]["data"]["pending_uploads"].append({
                "file_id": file_id,
                "episode_id": episode["id"],
                "title": f"{current_show['title']} S{season_num:02d}E{episode_num:02d}"
            })
            
            # Mise à jour de la saison courante
            user_sessions[user_id]["data"]["current_season"] = season
            
            await message.reply(
                f"✅ Épisode ajouté!\n\n"
                f"📺 *{current_show['title']}*\n"
                f"📁 Saison {season_num}\n"
                f"🎬 Épisode {episode_num}\n"
                f"💾 File ID: `{file_id}`\n\n"
                f"Envoyez d'autres épisodes ou tapez /done pour uploader vers Filemoon.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Erreur handle_video: {e}")
            await message.reply(f"❌ Erreur: {str(e)}")


def setup_handlers(bot: Client):
    """
    Configure les handlers de callbacks
    """
    
    @bot.on_callback_query()
    async def handle_callback(client: Client, callback: CallbackQuery):
        """Gère tous les callbacks inline"""
        user_id = callback.from_user.id
        data = callback.data
        
        try:
            # Création de show - sélection résultat
            if data.startswith("create_select_"):
                idx = int(data.split("_")[-1])
                await process_show_selection(client, callback, user_id, idx)
            
            elif data == "create_cancel":
                await callback.message.edit_text("❌ Création annulée.")
                user_sessions[user_id] = {"state": "idle", "data": {}}
            
            # Sélection de show pour différentes actions
            elif data.startswith("select_show_"):
                show_id = data.replace("select_show_", "")
                action = user_sessions.get(user_id, {}).get("action")
                await process_show_selection_by_id(client, callback, user_id, show_id, action)
            
            # Gestion saisons
            elif data.startswith("season_create_"):
                season_num = int(data.split("_")[-1])
                await process_season_creation(client, callback, user_id, season_num)
            
            elif data == "season_custom":
                await callback.message.edit_text(
                    "Envoyez le numéro de saison souhaité:\n"
                    "Exemple: `3` pour la saison 3",
                    parse_mode=ParseMode.MARKDOWN
                )
                user_sessions[user_id]["state"] = "waiting_season_number"
            
            elif data == "season_cancel":
                await callback.message.edit_text("❌ Opération annulée.")
            
            # Pagination docs
            elif data.startswith("docs_page_"):
                page = int(data.split("_")[-1])
                await update_shows_list(client, callback, page)
            
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Erreur callback: {e}")
            await callback.answer("❌ Erreur", show_alert=True)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def is_admin(user_id: int) -> bool:
    """Vérifie si l'utilisateur est admin"""
    return user_id in settings.ADMIN_USER_IDS


def is_waiting_video(user_id: int) -> bool:
    """Vérifie si l'utilisateur attend une vidéo"""
    return user_sessions.get(user_id, {}).get("state") == "waiting_video"


def parse_season_episode(caption: str) -> tuple:
    """
    Parse la caption pour extraire saison et épisode
    
    Returns:
        (season, episode) ou (None, None) si non trouvé
    """
    if not caption:
        return None, None
    
    # Patterns de recherche
    patterns = [
        (r'[Ss](\d+)[Ee](\d+)', True),  # S01E01
        (r'(\d+)[xX](\d+)', True),       # 1x01
        (r'[Ss]aison\s*(\d+).*?[ÉEe]pisode\s*(\d+)', True),  # Saison 1 Episode 1
        (r'[ÉEe]pisode\s*(\d+)', False), # Épisode 5 (saison 1 par défaut)
    ]
    
    for pattern, has_season in patterns:
        match = re.search(pattern, caption)
        if match:
            if has_season:
                return int(match.group(1)), int(match.group(2))
            else:
                return 1, int(match.group(1))
    
    return None, None


async def process_show_selection(client: Client, callback: CallbackQuery, user_id: int, idx: int):
    """Traite la sélection d'un show depuis la recherche TMDB"""
    session = user_sessions.get(user_id, {})
    results = session.get("results", [])
    
    if idx >= len(results):
        await callback.message.edit_text("❌ Résultat invalide.")
        return
    
    selected = results[idx]
    
    await callback.message.edit_text(f"⏳ Récupération des détails TMDB...")
    
    try:
        # Récupération détails complets
        details = await get_tmdb_details(selected["tmdb_id"], selected["type"])
        
        if not details:
            await callback.message.edit_text("❌ Erreur récupération détails TMDB.")
            return
        
        # Création en base
        show_data = {
            "tmdb_id": details["tmdb_id"],
            "title": details["title"],
            "type": selected["type"],
            "overview": details["overview"],
            "poster_path": details["poster_path"],
            "backdrop_path": details["backdrop_path"],
            "release_date": details["release_date"],
            "genres": details["genres"],
            "runtime": details["runtime"],
            "rating": details["vote_average"]
        }
        
        created_show = await create_show(show_data)
        
        # Création saison 0 pour films ou saison 1 pour séries si besoin
        if selected["type"] == "movie":
            # Pour les films, créer une saison "spéciale" 0
            await create_season({
                "show_id": created_show["id"],
                "season_number": 0,
                "name": "Film"
            })
        else:
            # Pour les séries, créer la saison 1 par défaut
            await create_season({
                "show_id": created_show["id"],
                "season_number": 1,
                "name": "Saison 1"
            })
        
        # Mise à jour session
        user_sessions[user_id] = {
            "state": "idle",
            "data": {
                "current_show": created_show
            }
        }
        
        # Message de confirmation
        poster_url = f"https://image.tmdb.org/t/p/w500{details['poster_path']}" if details['poster_path'] else None
        
        text = (
            f"✅ *Show créé avec succès!*\n\n"
            f"🎬 *{created_show['title']}*\n"
            f"📅 {details.get('release_date', 'N/A')}\n"
            f"⭐ {details.get('vote_average', 'N/A')}/10\n"
            f"🎭 {', '.join(details['genres'][:3])}\n"
            f"📝 _{details['overview'][:200]}..._\n\n"
            f"ID: `{created_show['id']}`\n\n"
            f"Prochaines étapes:\n"
            f"• `/add` - Ajouter des épisodes\n"
            f"• `/addf` - Gérer les saisons\n"
            f"• `/view` - Voir les détails"
        )
        
        if poster_url:
            await callback.message.reply_photo(poster_url, caption=text, parse_mode=ParseMode.MARKDOWN)
            await callback.message.delete()
        else:
            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Erreur process_show_selection: {e}")
        await callback.message.edit_text(f"❌ Erreur: {str(e)}")


async def list_shows_for_selection(client: Client, message: Message, action: str):
    """Affiche la liste des shows pour sélection"""
    try:
        shows, _ = await get_all_shows(limit=20)
        
        if not shows:
            await message.reply("❌ Aucun show trouvé. Créez-en un avec /create")
            return
        
        buttons = []
        for show in shows:
            emoji = "🎬" if show["type"] == "movie" else "📺"
            btn_text = f"{emoji} {show['title']}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_show_{show['id']}")])
        
        # Stockage de l'action en cours
        user_id = message.from_user.id
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]["action"] = action
        
        text = "📋 Sélectionnez un show:"
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Erreur list_shows: {e}")
        await message.reply(f"❌ Erreur: {str(e)}")


async def process_show_selection_by_id(client: Client, callback: CallbackQuery, user_id: int, show_id: str, action: str):
    """Traite la sélection d'un show par ID pour une action donnée"""
    try:
        show = await get_show_by_id(show_id)
        if not show:
            await callback.message.edit_text("❌ Show non trouvé.")
            return
        
        # Mise à jour session
        if user_id not in user_sessions:
            user_sessions[user_id] = {"state": "idle", "data": {}}
        
        user_sessions[user_id]["data"]["current_show"] = show
        
        if action == "add_episode":
            await callback.message.edit_text(
                f"✅ Show sélectionné: *{show['title']}*\n\n"
                f"Utilisez maintenant /add pour envoyer des épisodes.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif action == "create_season":
            # Rediriger vers la logique de création de saison
            await callback.message.edit_text(
                f"✅ Show sélectionné: *{show['title']}*\n\n"
                f"Utilisez /addf pour créer une saison.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif action == "view_show":
            await show_show_details(client, callback.message, show_id, edit=True)
        
    except Exception as e:
        logger.error(f"Erreur process_show_selection_by_id: {e}")
        await callback.message.edit_text(f"❌ Erreur: {str(e)}")


async def show_show_details(client: Client, message_or_callback, show_id: str, edit: bool = False):
    """Affiche les détails d'un show"""
    try:
        from database.queries import get_seasons_by_show, get_episodes_by_season
        
        show = await get_show_by_id(show_id)
        if not show:
            text = "❌ Show non trouvé."
            if edit:
                await message_or_callback.edit_text(text)
            else:
                await message_or_callback.reply(text)
            return
        
        # Récupération saisons et épisodes
        seasons = await get_seasons_by_show(show_id)
        total_episodes = 0
        
        seasons_info = []
        for season in seasons:
            episodes = await get_episodes_by_season(season["id"])
            total_episodes += len(episodes)
            seasons_info.append(f"Saison {season['season_number']}: {len(episodes)} ép.")
        
        # Construction du texte
        text = (
            f"📊 *{show['title']}*\n"
            f"{'🎬 Film' if show['type'] == 'movie' else '📺 Série'}\n"
            f"⭐ {show.get('rating', 'N/A')}/10\n"
            f"📅 {show.get('release_date', 'N/A')}\n"
            f"👁 {show.get('views', 0)} vues\n\n"
            f"📝 _{show.get('overview', 'Pas de synopsis')[:300]}..._\n\n"
            f"📁 *Saisons:* {len(seasons)}\n"
            f"🎬 *Épisodes:* {total_episodes}\n"
        )
        
        if seasons_info:
            text += "\n" + "\n".join(seasons_info)
        
        text += f"\n\n🆔 `{show_id}`"
        
        if edit:
            await message_or_callback.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            await message_or_callback.reply(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Erreur show_details: {e}")
        text = f"❌ Erreur: {str(e)}"
        if edit:
            await message_or_callback.edit_text(text)
        else:
            await message_or_callback.reply(text)


async def list_shows_paginated(client: Client, message: Message, page: int = 1):
    """Liste les shows avec pagination"""
    try:
        limit = 10
        offset = (page - 1) * limit
        
        shows, total = await get_all_shows(limit=limit, offset=offset)
        total_pages = (total + limit - 1) // limit
        
        if not shows:
            await message.reply("📭 Aucun show trouvé.")
            return
        
        text = f"📋 *Liste des shows* (Page {page}/{total_pages})\n\n"
        
        for idx, show in enumerate(shows, offset + 1):
            emoji = "🎬" if show["type"] == "movie" else "📺"
            text += f"{idx}. {emoji} *{show['title']}*\n"
            text += f"   👁 {show.get('views', 0)} vues | 🆔 `{show['id'][:8]}...`\n\n"
        
        # Boutons pagination
        buttons = []
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ Précédent", callback_data=f"docs_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Suivant ➡️", callback_data=f"docs_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Erreur list_shows_paginated: {e}")
        await message.reply(f"❌ Erreur: {str(e)}")


async def update_shows_list(client: Client, callback: CallbackQuery, page: int):
    """Met à jour la liste paginée"""
    try:
        limit = 10
        offset = (page - 1) * limit
        
        shows, total = await get_all_shows(limit=limit, offset=offset)
        total_pages = (total + limit - 1) // limit
        
        text = f"📋 *Liste des shows* (Page {page}/{total_pages})\n\n"
        
        for idx, show in enumerate(shows, offset + 1):
            emoji = "🎬" if show["type"] == "movie" else "📺"
            text += f"{idx}. {emoji} *{show['title']}*\n"
            text += f"   👁 {show.get('views', 0)} vues | 🆔 `{show['id'][:8]}...`\n\n"
        
        buttons = []
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ Précédent", callback_data=f"docs_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Suivant ➡️", callback_data=f"docs_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        await callback.message.edit_text(
            text, 
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur update_shows_list: {e}")
        await callback.answer("❌ Erreur", show_alert=True)


async def process_season_creation(client: Client, callback: CallbackQuery, user_id: int, season_num: int):
    """Crée une nouvelle saison"""
    try:
        session = user_sessions.get(user_id, {})
        current_show = session.get("data", {}).get("current_show")
        
        if not current_show:
            await callback.message.edit_text("❌ Erreur: Aucun show sélectionné.")
            return
        
        # Vérification existence
        existing = await get_season_by_number(current_show["id"], season_num)
        if existing:
            await callback.message.edit_text(f"❌ La saison {season_num} existe déjà!")
            return
        
        # Création
        season = await create_season({
            "show_id": current_show["id"],
            "season_number": season_num,
            "name": f"Saison {season_num}"
        })
        
        # Mise à jour session
        user_sessions[user_id]["data"]["current_season"] = season
        
        await callback.message.edit_text(
            f"✅ *Saison {season_num} créée!*\n\n"
            f"Vous pouvez maintenant ajouter des épisodes avec /add",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur process_season_creation: {e}")
        await callback.message.edit_text(f"❌ Erreur: {str(e)}")
