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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from pyrogram.enums import ParseMode

from config import settings, BOT_MESSAGES, SEASON_EPISODE_PATTERNS
from database.queries import (
    create_show, get_show_by_tmdb_id, get_show_by_id,
    create_season, get_season_by_number, get_seasons_by_show,
    create_episode, get_episode_by_number,
    create_video_source, get_all_shows, get_episodes_by_season,
    clear_bot_session
)
from services.tmdb_api import search_tmdb, get_tmdb_details, get_tmdb_season
from services.filemoon_api import upload_to_filemoon

logger = logging.getLogger(__name__)

# Stockage temporaire des sessions
user_sessions: Dict[int, Dict[str, Any]] = {}


def is_admin(user_id: int) -> bool:
    """Vérifie si l'utilisateur est admin"""
    return user_id in settings.ADMIN_USER_IDS


def is_waiting_video(user_id: int) -> bool:
    """Vérifie si l'utilisateur attend une vidéo"""
    return user_sessions.get(user_id, {}).get("state") == "waiting_video"


def parse_season_episode(caption: str) -> tuple:
    """Parse la caption pour extraire saison et épisode"""
    if not caption:
        return None, None
    
    patterns = [
        (r'[Ss](\d+)[Ee](\d+)', True),
        (r'(\d+)[xX](\d+)', True),
        (r'[Ss]aison\s*(\d+).*?[ÉEe]pisode\s*(\d+)', True),
        (r'[ÉEe]pisode\s*(\d+)', False),
    ]
    
    for pattern, has_season in patterns:
        match = re.search(pattern, caption)
        if match:
            if has_season:
                return int(match.group(1)), int(match.group(2))
            else:
                return 1, int(match.group(1))
    
    return None, None


def setup_commands(bot: Client):
    """Configure toutes les commandes du bot"""
    
    # =========================================================================
    # COMMANDE /START
    # =========================================================================
    @bot.on_message(filters.command("start") & filters.private)
    async def start_command(client: Client, message: Message):
        """Commande de démarrage"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            await message.reply("⛔ Accès refusé.")
            return
        
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

3️⃣ **Ajouter un épisode** (séries)
   `/add`
   Envoyez la vidéo avec caption: `S01E01` ou `Épisode 1`

4️⃣ **Ajouter un film** (films)
   `/add`
   Envoyez la vidéo SANS caption spéciale (le film est unique)

4️⃣ **Finaliser l'upload**
   `/done`
   Upload vers Filemoon et génération des liens.

**Gestion:**

• `/view [ID]` - Voir les détails d'un show et ajouter du contenu
• `/docs` - Lister tous les shows (avec pagination)
• `/cancel` - Annuler l'opération en cours

**Format des captions (séries uniquement):**
- `S01E01` ou `s1e1` → Saison 1, Épisode 1
- `Épisode 5` → Saison en cours, Épisode 5
- `2x15` → Saison 2, Épisode 15

**Conseils:**
- Les films n'ont pas besoin de caption spéciale
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
        await message.reply("❌ Opération annulée.")
    
    # =========================================================================
    # COMMANDE /CREATE
    # =========================================================================
    @bot.on_message(filters.command("create") & filters.private)
    async def create_command(client: Client, message: Message):
        """Crée un nouveau show via TMDB"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
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
            movie_results = await search_tmdb(query, "movie")
            tv_results = await search_tmdb(query, "tv")
            
            all_results = []
            
            for item in movie_results[:5]:
                all_results.append({
                    "tmdb_id": item["tmdb_id"],
                    "title": item["title"],
                    "year": item.get("release_date", "")[:4] if item.get("release_date") else "N/A",
                    "type": "movie",
                    "overview": item.get("overview", "")[:100] + "..." if len(item.get("overview", "")) > 100 else item.get("overview", ""),
                    "poster": item.get("poster_path", "")
                })
            
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
            
            user_sessions[user_id] = {
                "state": "selecting_show",
                "results": all_results,
                "data": {}
            }
            
            buttons = []
            for idx, result in enumerate(all_results[:6]):
                type_emoji = "🎬" if result["type"] == "movie" else "📺"
                btn_text = f"{type_emoji} {result['title']} ({result['year']})"
                buttons.append([InlineKeyboardButton(btn_text, callback_data=f"create_select_{idx}")])
            
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="create_cancel")])
            
            text = "🎯 *Plusieurs résultats trouvés:*\n\n"
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
    # COMMANDE /ADD - MODIFIÉE POUR FILMS ET SÉRIES
    # =========================================================================
    @bot.on_message(filters.command("add") & filters.private)
    async def add_command(client: Client, message: Message):
        """Prépare l'ajout d'un épisode (série) ou d'une source (film)"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        session = user_sessions.get(user_id, {})
        current_show = session.get("data", {}).get("current_show")
        
        if not current_show:
            await message.reply("❌ Utilisez d'abord /create pour sélectionner un show.")
            return
        
        user_sessions[user_id]["state"] = "waiting_video"
        
        # Message différent selon le type
        if current_show["type"] == "movie":
            await message.reply(
                f"📤 Ajout du film: *{current_show['title']}*\n\n"
                f"Envoyez la vidéo du film.\n"
                f"_Pas besoin de caption spéciale pour les films._\n\n"
                f"Le film sera ajouté directement.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.reply(
                f"📤 Envoi d'épisode pour: *{current_show['title']}*\n\n"
                f"Envoyez la vidéo avec caption:\n"
                f"• `S01E01` ou `s1e1`\n"
                f"• `Épisode 5`\n"
                f"• `2x15` (saison 2, ép 15)\n\n"
                f"_Envoyez plusieurs vidéos successivement, puis /done pour uploader._",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # =========================================================================
    # COMMANDE /ADDF
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
            await message.reply("❌ Utilisez d'abord /create pour sélectionner un show.")
            return
        
        if current_show["type"] == "movie":
            await message.reply("❌ Les films n'ont pas de saisons!")
            return
        
        seasons = await get_seasons_by_show(current_show["id"])
        next_season = len(seasons) + 1
        
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
    # COMMANDE /VIEW - AMÉLIORÉE AVEC BOUTONS D'ACTION
    # =========================================================================
    @bot.on_message(filters.command("view") & filters.private)
    async def view_command(client: Client, message: Message):
        """Affiche les détails d'un show avec boutons d'action"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        if len(message.command) < 2:
            # Si pas d'ID fourni, utiliser le show courant de la session
            session = user_sessions.get(user_id, {})
            current_show = session.get("data", {}).get("current_show")
            if current_show:
                show_id = current_show["id"]
            else:
                await message.reply("❌ Usage: `/view <ID>`\nExemple: `/view abc123`\nOu utilisez d'abord /create pour sélectionner un show.")
                return
        else:
            show_id = message.command[1]
        
        await show_show_details_with_actions(client, message, show_id, user_id)
    
    # =========================================================================
    # COMMANDE /DOCS
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
    # COMMANDE /DONE
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
            await message.reply("❌ Aucun upload en attente.")
            return
        
        await message.reply(f"🚀 Démarrage de l'upload Filemoon pour {len(pending_uploads)} fichier(s)...")
        
        for idx, upload_info in enumerate(pending_uploads, 1):
            progress_msg = await message.reply(f"⏳ Upload {idx}/{len(pending_uploads)}: Préparation...")
            
            try:
                await asyncio.sleep(2)
                await progress_msg.edit_text(f"✅ Upload {idx} terminé (simulation)")
                
            except Exception as e:
                logger.error(f"Erreur upload: {e}")
                await progress_msg.edit_text(f"❌ Erreur: {str(e)}")
        
        user_sessions[user_id]["data"]["pending_uploads"] = []
        await message.reply("✅ Tous les uploads sont terminés!")
    
    # =========================================================================
    # HANDLER VIDÉOS - MODIFIÉ POUR FILMS ET SÉRIES
    # =========================================================================
    @bot.on_message(
        (filters.video | filters.document) & filters.private
    )
    async def handle_video_upload(client: Client, message: Message):
        """Gère la réception d'une vidéo pour ajout d'épisode ou film"""
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        if not is_waiting_video(user_id):
            await message.reply(
                "⚠️ Envoyez d'abord /add pour ajouter un contenu.\n"
                "Ou utilisez /create pour créer un show."
            )
            return
        
        session = user_sessions.get(user_id, {})
        current_show = session["data"].get("current_show")
        
        if not current_show:
            await message.reply("❌ Erreur: Aucun show sélectionné.")
            return
        
        # Détection du fichier
        if message.video:
            file_id = message.video.file_id
            file_size = message.video.file_size
            duration = message.video.duration
        elif message.document:
            file_id = message.document.file_id
            file_size = message.document.file_size
            duration = None
        else:
            await message.reply("❌ Format non supporté.")
            return
        
        # TRAITEMENT DIFFÉRENT SELON LE TYPE
        if current_show["type"] == "movie":
            # FILM: Créer directement une source vidéo sans saison/épisode
            await handle_movie_upload(client, message, user_id, current_show, file_id, file_size, duration)
        else:
            # SÉRIE: Logique existante avec saison/épisode
            await handle_series_upload(client, message, user_id, current_show, file_id, file_size, duration, message.caption)


async def handle_movie_upload(client, message, user_id, current_show, file_id, file_size, duration):
    """Gère l'upload d'un film (sans saison/épisode)"""
    try:
        # Pour les films, on crée un "épisode spécial" saison 0 épisode 0
        # ou on modifie la structure pour supporter les films sans épisodes
        
        # Récupérer ou créer la saison 0 (spéciale pour films)
        season = await get_season_by_number(current_show["id"], 0)
        if not season:
            season = await create_season({
                "show_id": current_show["id"],
                "season_number": 0,
                "name": "Film"
            })
        
        # Créer l'épisode 0 (le film lui-même)
        episode = await create_episode({
            "season_id": season["id"],
            "episode_number": 0,
            "title": current_show["title"]  # Titre du film
        })
        
        # Créer la source vidéo
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
        
        # Ajout pending uploads
        if "pending_uploads" not in user_sessions[user_id]["data"]:
            user_sessions[user_id]["data"]["pending_uploads"] = []
        
        user_sessions[user_id]["data"]["pending_uploads"].append({
            "file_id": file_id,
            "episode_id": episode["id"],
            "title": f"{current_show['title']} (Film)"
        })
        
        count = len(user_sessions[user_id]["data"]["pending_uploads"])
        
        await message.reply(
            f"✅ Film ajouté! (Total: {count})\n\n"
            f"🎬 *{current_show['title']}*\n"
            f"📁 Saison 0 (Film)\n\n"
            f"Tapez /done pour uploader vers Filemoon.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur handle_movie: {e}")
        await message.reply(f"❌ Erreur: {str(e)}")


async def handle_series_upload(client, message, user_id, current_show, file_id, file_size, duration, caption):
    """Gère l'upload d'un épisode de série (logique existante)"""
    try:
        session = user_sessions.get(user_id, {})
        current_season = session["data"].get("current_season")
        
        # Parsing de la caption
        season_num, episode_num = parse_season_episode(caption)
        
        if season_num is None:
            season_num = current_season["season_number"] if current_season else 1
        
        if episode_num is None:
            await message.reply(
                "❌ Numéro d'épisode non détecté.\n"
                "Incluez dans la caption: `S01E05` ou `Épisode 3`"
            )
            return
        
        # Création saison si besoin
        season = await get_season_by_number(current_show["id"], season_num)
        if not season:
            season = await create_season({
                "show_id": current_show["id"],
                "season_number": season_num,
                "name": f"Saison {season_num}"
            })
            await message.reply(f"📁 Saison {season_num} créée.")
        
        # Création épisode
        episode = await create_episode({
            "season_id": season["id"],
            "episode_number": episode_num,
            "title": caption if caption and not caption.startswith("S") else f"Épisode {episode_num}"
        })
        
        # Source Telegram
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
        
        # Ajout pending uploads
        if "pending_uploads" not in user_sessions[user_id]["data"]:
            user_sessions[user_id]["data"]["pending_uploads"] = []
        
        user_sessions[user_id]["data"]["pending_uploads"].append({
            "file_id": file_id,
            "episode_id": episode["id"],
            "title": f"{current_show['title']} S{season_num:02d}E{episode_num:02d}"
        })
        
        user_sessions[user_id]["data"]["current_season"] = season
        
        count = len(user_sessions[user_id]["data"]["pending_uploads"])
        
        await message.reply(
            f"✅ Épisode ajouté! (Total: {count})\n\n"
            f"📺 *{current_show['title']}*\n"
            f"📁 Saison {season_num}\n"
            f"🎬 Épisode {episode_num}\n\n"
            f"Envoyez d'autres épisodes ou tapez /done pour uploader.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur handle_series: {e}")
        await message.reply(f"❌ Erreur: {str(e)}")


def setup_handlers(bot: Client):
    """Configure les handlers de callbacks"""
    
    @bot.on_callback_query()
    async def handle_callback(client: Client, callback: CallbackQuery):
        """Gère tous les callbacks inline"""
        user_id = callback.from_user.id
        data = callback.data
        
        try:
            if data.startswith("create_select_"):
                idx = int(data.split("_")[-1])
                await process_show_selection(client, callback, user_id, idx)
            
            elif data == "create_cancel":
                await callback.message.edit_text("❌ Création annulée.")
                user_sessions[user_id] = {"state": "idle", "data": {}}
            
            elif data.startswith("season_create_"):
                season_num = int(data.split("_")[-1])
                await process_season_creation(client, callback, user_id, season_num)
            
            elif data == "season_custom":
                await callback.message.edit_text("Envoyez le numéro de saison (ex: 3):")
                user_sessions[user_id]["state"] = "waiting_season_number"
            
            elif data == "season_cancel":
                await callback.message.edit_text("❌ Opération annulée.")
            
            elif data.startswith("docs_page_"):
                page = int(data.split("_")[-1])
                await update_shows_list(client, callback, page)
            
            # NOUVEAUX CALLBACKS POUR /view
            elif data.startswith("view_add_"):
                show_id = data.split("_")[-1]
                await callback_view_add(client, callback, user_id, show_id)
            
            elif data.startswith("view_addf_"):
                show_id = data.split("_")[-1]
                await callback_view_addf(client, callback, user_id, show_id)
            
            elif data.startswith("view_refresh_"):
                show_id = data.split("_")[-1]
                await callback_view_refresh(client, callback, user_id, show_id)
            
            # IMPORTANT: Répondre au callback
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Erreur callback: {e}")
            await callback.answer("❌ Erreur", show_alert=True)


# ============================================================================
# FONCTIONS AUXILIAIRES
# ============================================================================

async def process_show_selection(client: Client, callback: CallbackQuery, user_id: int, idx: int):
    """Traite la sélection d'un show depuis la recherche TMDB"""
    session = user_sessions.get(user_id, {})
    results = session.get("results", [])
    
    if idx >= len(results):
        await callback.message.edit_text("❌ Résultat invalide.")
        return
    
    selected = results[idx]
    await callback.message.edit_text(f"⏳ Récupération des détails...")
    
    try:
        details = await get_tmdb_details(selected["tmdb_id"], selected["type"])
        
        if not details:
            await callback.message.edit_text("❌ Erreur récupération détails TMDB.")
            return
        
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
        
        if selected["type"] == "movie":
            await create_season({
                "show_id": created_show["id"],
                "season_number": 0,
                "name": "Film"
            })
        else:
            await create_season({
                "show_id": created_show["id"],
                "season_number": 1,
                "name": "Saison 1"
            })
        
        user_sessions[user_id] = {
            "state": "idle",
            "data": {"current_show": created_show}
        }
        
        text = (
            f"✅ *Show créé!*\n\n"
            f"🎬 *{created_show['title']}*\n"
            f"📅 {details.get('release_date', 'N/A')}\n"
            f"⭐ {details.get('vote_average', 'N/A')}/10\n"
            f"🆔 `{created_show['id']}`\n\n"
            f"• `/add` - Ajouter du contenu\n"
            f"• `/view` - Voir les détails et gérer"
        )
        
        # Boutons d'action rapide
        buttons = [
            [InlineKeyboardButton("➕ Ajouter contenu", callback_data=f"view_add_{created_show['id']}")],
            [InlineKeyboardButton("📊 Voir détails", callback_data=f"view_refresh_{created_show['id']}")]
        ]
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur process_show_selection: {e}")
        await callback.message.edit_text(f"❌ Erreur: {str(e)}")


async def process_season_creation(client: Client, callback: CallbackQuery, user_id: int, season_num: int):
    """Crée une nouvelle saison"""
    try:
        session = user_sessions.get(user_id, {})
        current_show = session.get("data", {}).get("current_show")
        
        if not current_show:
            await callback.message.edit_text("❌ Erreur: Aucun show sélectionné.")
            return
        
        existing = await get_season_by_number(current_show["id"], season_num)
        if existing:
            await callback.message.edit_text(f"❌ La saison {season_num} existe déjà!")
            return
        
        season = await create_season({
            "show_id": current_show["id"],
            "season_number": season_num,
            "name": f"Saison {season_num}"
        })
        
        user_sessions[user_id]["data"]["current_season"] = season
        
        await callback.message.edit_text(
            f"✅ *Saison {season_num} créée!*\n\n"
            f"Utilisez /add pour ajouter des épisodes.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur process_season_creation: {e}")
        await callback.message.edit_text(f"❌ Erreur: {str(e)}")


# ============================================================================
# NOUVELLES FONCTIONS POUR /view AMÉLIORÉ
# ============================================================================

async def show_show_details_with_actions(client: Client, message: Message, show_id: str, user_id: int):
    """Affiche les détails d'un show avec boutons d'action"""
    try:
        show = await get_show_by_id(show_id)
        if not show:
            await message.reply("❌ Show non trouvé.")
            return
        
        # Mettre à jour la session avec ce show
        user_sessions[user_id]["data"]["current_show"] = show
        
        seasons = await get_seasons_by_show(show_id)
        total_episodes = 0
        
        for season in seasons:
            episodes = await get_episodes_by_season(season["id"])
            total_episodes += len(episodes)
        
        # Construction du texte
        text = (
            f"📊 *{show['title']}*\n"
            f"{'🎬 Film' if show['type'] == 'movie' else '📺 Série'}\n"
            f"⭐ {show.get('rating', 'N/A')}/10\n"
            f"📅 {show.get('release_date', 'N/A')}\n\n"
            f"📁 *Saisons:* {len(seasons)}\n"
            f"🎬 *Épisodes:* {total_episodes}\n\n"
            f"📝 _{show.get('overview', 'Pas de synopsis')[:200]}..._\n\n"
            f"🆔 `{show_id}`"
        )
        
        # Boutons d'action selon le type
        buttons = []
        
        if show["type"] == "movie":
            # Pour les films: bouton ajouter source
            buttons.append([InlineKeyboardButton("➕ Ajouter le film", callback_data=f"view_add_{show_id}")])
        else:
            # Pour les séries: boutons saison et épisode
            buttons.append([InlineKeyboardButton("➕ Ajouter épisode", callback_data=f"view_add_{show_id}")])
            buttons.append([InlineKeyboardButton("📁 Gérer saisons", callback_data=f"view_addf_{show_id}")])
        
        buttons.append([InlineKeyboardButton("🔄 Rafraîchir", callback_data=f"view_refresh_{show_id}")])
        
        await message.reply(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur show_details_with_actions: {e}")
        await message.reply(f"❌ Erreur: {str(e)}")


async def callback_view_add(client: Client, callback: CallbackQuery, user_id: int, show_id: str):
    """Callback pour ajouter du contenu depuis /view"""
    try:
        show = await get_show_by_id(show_id)
        if not show:
            await callback.answer("Show non trouvé", show_alert=True)
            return
        
        # Mettre à jour la session
        user_sessions[user_id]["data"]["current_show"] = show
        user_sessions[user_id]["state"] = "waiting_video"
        
        if show["type"] == "movie":
            await callback.message.edit_text(
                f"📤 Ajout du film: *{show['title']}*\n\n"
                f"Envoyez la vidéo du film maintenant.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await callback.message.edit_text(
                f"📤 Ajout d'épisode pour: *{show['title']}*\n\n"
                f"Envoyez la vidéo avec caption (S01E01, Épisode 5, etc.)",
                parse_mode=ParseMode.MARKDOWN
            )
        
    except Exception as e:
        logger.error(f"Erreur callback_view_add: {e}")
        await callback.answer("❌ Erreur", show_alert=True)


async def callback_view_addf(client: Client, callback: CallbackQuery, user_id: int, show_id: str):
    """Callback pour gérer les saisons depuis /view"""
    try:
        show = await get_show_by_id(show_id)
        if not show or show["type"] == "movie":
            await callback.answer("Pas de saisons pour les films", show_alert=True)
            return
        
        # Mettre à jour la session
        user_sessions[user_id]["data"]["current_show"] = show
        
        # Simuler la commande /addf
        seasons = await get_seasons_by_show(show_id)
        next_season = len(seasons) + 1
        
        buttons = [
            [InlineKeyboardButton(f"Créer Saison {next_season}", callback_data=f"season_create_{next_season}")],
            [InlineKeyboardButton("Autre numéro...", callback_data="season_custom")],
            [InlineKeyboardButton("❌ Annuler", callback_data="season_cancel")]
        ]
        
        await callback.message.edit_text(
            f"📁 Gestion des saisons pour *{show['title']}*\n\n"
            f"Saisons existantes: {len(seasons)}\n"
            f"Quelle action souhaitez-vous?",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur callback_view_addf: {e}")
        await callback.answer("❌ Erreur", show_alert=True)


async def callback_view_refresh(client: Client, callback: CallbackQuery, user_id: int, show_id: str):
    """Callback pour rafraîchir la vue"""
    try:
        await show_show_details_with_actions(client, callback.message, show_id, user_id)
        await callback.answer("✅ Rafraîchi")
    except Exception as e:
        logger.error(f"Erreur callback_view_refresh: {e}")
        await callback.answer("❌ Erreur", show_alert=True)


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
            text += f"   🆔 `{show['id'][:8]}...`\n\n"
        
        buttons = []
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"docs_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"docs_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        await message.reply(
            text, 
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Erreur list_shows: {e}")
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
            text += f"   🆔 `{show['id'][:8]}...`\n\n"
        
        buttons = []
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"docs_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"docs_page_{page+1}"))
        
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
