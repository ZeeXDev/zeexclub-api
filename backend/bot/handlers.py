# backend/bot/handlers.py
"""
Handlers pour messages et callbacks du bot
Gestion des fichiers vidéo, textes, et interactions inline
"""

import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS
from bot.sessions import SessionManager
from bot.utils import parse_caption, format_file_size, format_duration, escape_markdown
from services.stream_handler import generate_stream_link
from services.filemoon_api import upload_to_filemoon_async
from database.supabase_client import supabase_manager

logger = logging.getLogger(__name__)

def setup_handlers(app: Client, session_manager: SessionManager):
    """
    Configure tous les handlers pour le bot
    
    Args:
        app: Client Pyrogram
        session_manager: Gestionnaire de sessions
    """
    
    # =========================================================================
    # HANDLER TEXTES (POUR SESSIONS ACTIVES)
    # =========================================================================
    
    @app.on_message(filters.text & filters.user(ADMIN_IDS) & ~filters.command([
        'start', 'help', 'create', 'addf', 'add', 'done', 'cancel', 
        'view', 'docs', 'stats', 'delete'
    ]))
    async def handle_text_message(client: Client, message: Message):
        """Gère les messages texte selon la session active"""
        user_id = message.from_user.id
        session = session_manager.get(user_id)
        
        if not session:
            # Pas de session active, ignorer ou aider
            await message.reply(
                "ℹ️ **Aucune commande active**\n\n"
                "Envoyez `/help` pour voir les commandes disponibles."
            )
            return
        
        mode = session.get('mode')
        
        if mode == 'creating_subfolder':
            await handle_subfolder_creation(client, message, session, session_manager)
        elif mode == 'adding_files':
            await message.reply(
                "⚠️ **Mode ajout actif**\n\n"
                "Envoyez des fichiers vidéo ou tapez `/done` pour terminer."
            )
        else:
            logger.warning(f"Mode inconnu: {mode}")
    
    async def handle_subfolder_creation(client: Client, message: Message, session: dict, session_manager: SessionManager):
        """Gère la création de sous-dossier (demande du nom)"""
        from bot.utils import is_valid_folder_name
        
        subfolder_name = message.text.strip()
        
        # Vérifier annulation
        if subfolder_name.lower() == '/cancel':
            session_manager.delete(message.from_user.id)
            await message.reply("❌ Création annulée.")
            return
        
        # Valider le nom
        is_valid, error_msg = is_valid_folder_name(subfolder_name)
        if not is_valid:
            await message.reply(f"❌ **Nom invalide:** {error_msg}\n\nRéessayez ou envoyez `/cancel`")
            return
        
        parent_id = session.get('parent_id')
        parent_name = session.get('parent_name')
        
        try:
            # Vérifier si le sous-dossier existe déjà
            existing_subs = supabase_manager.get_subfolders(parent_id)
            if any(s['folder_name'].lower() == subfolder_name.lower() for s in existing_subs):
                await message.reply(
                    f"⚠️ Le sous-dossier `{escape_markdown(subfolder_name)}` existe déjà dans `{escape_markdown(parent_name)}`"
                )
                return
            
            # Créer le sous-dossier
            result = supabase_manager.create_folder(subfolder_name, parent_id=parent_id)
            
            if result:
                await message.reply(
                    f"✅ **Sous-dossier créé!**\n\n"
                    f"📂 Parent: `{escape_markdown(parent_name)}`\n"
                    f"📁 Nouveau: `{escape_markdown(subfolder_name)}`\n\n"
                    f"▶️ `/add {escape_markdown(parent_name)}/{escape_markdown(subfolder_name)}` pour ajouter des vidéos"
                )
                session_manager.delete(message.from_user.id)
            else:
                await message.reply("❌ Erreur lors de la création du sous-dossier.")
                
        except Exception as e:
            logger.error(f"Erreur création sous-dossier: {e}")
            await message.reply(f"❌ **Erreur:** `{str(e)[:100]}`")
    
    # =========================================================================
    # HANDLER FICHIERS VIDÉO
    # =========================================================================
    
    @app.on_message((filters.video | filters.document) & filters.user(ADMIN_IDS))
    async def handle_video_file(client: Client, message: Message):
        """Traite les fichiers vidéo envoyés en mode ajout"""
        user_id = message.from_user.id
        session = session_manager.get(user_id)
        
        if not session or session.get('mode') != 'adding_files':
            await message.reply(
                "⚠️ **Mode ajout non actif**\n\n"
                "Utilisez `/add <dossier>` pour commencer à ajouter des vidéos."
            )
            return
        
        # Déterminer s'il s'agit d'une vidéo ou d'un document
        if message.video:
            video = message.video
            file_id = video.file_id
            file_size = video.file_size
            duration = video.duration
            width = video.width
            height = video.height
            mime_type = video.mime_type
        elif message.document and message.document.mime_type and 'video' in message.document.mime_type:
            video = message.document
            file_id = video.file_id
            file_size = video.file_size
            duration = 0  # Documents sans métadonnées vidéo
            width = 0
            height = 0
            mime_type = video.mime_type
        else:
            await message.reply("❌ **Fichier non reconnu comme vidéo**\n\nEnvoyez un fichier vidéo valide.")
            return
        
        # Vérifier taille (limite pratique pour Filemoon)
        if file_size and file_size > 5 * 1024 * 1024 * 1024:  # 5 GB
            await message.reply("❌ **Fichier trop volumineux** (max 5 GB recommandé pour Filemoon)")
            return
        
        caption = message.caption or ""
        season, episode, clean_title = parse_caption(caption)
        
        folder_id = session.get('folder_id')
        folder_path = session.get('folder_path')
        
        # Message de statut
        status_msg = await message.reply("⏳ **Traitement en cours...**")
        
        try:
            # Étape 1: Générer le lien de streaming ZeeX
            await status_msg.edit_text("🔧 **Génération du lien de streaming...**")
            stream_link = generate_stream_link(file_id)
            
            # Étape 2: Upload Filemoon (asynchrone avec timeout)
            filemoon_link = None
            try:
                await status_msg.edit_text("☁️ **Upload vers Filemoon en cours...**\n_Cela peut prendre plusieurs minutes pour les gros fichiers_")
                
                # Timeout de 10 minutes pour l'upload
                filemoon_link = await asyncio.wait_for(
                    upload_to_filemoon_async(stream_link),
                    timeout=600
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout Filemoon pour {file_id}")
                await status_msg.edit_text("⚠️ **Upload Filemoon timeout** - La vidéo sera disponible uniquement sur ZeeX")
            except Exception as e:
                logger.error(f"Erreur Filemoon: {e}")
                filemoon_link = None
            
            # Étape 3: Sauvegarder dans Supabase
            await status_msg.edit_text("💾 **Sauvegarde en base de données...**")
            
            video_data = {
                'folder_id': folder_id,
                'title': clean_title,
                'file_id': file_id,
                'episode_number': episode,
                'season_number': season,
                'zeex_url': stream_link,
                'filemoon_url': filemoon_link,
                'caption': caption,
                'duration': duration,
                'file_size': file_size,
                'width': width,
                'height': height,
                'mime_type': mime_type
            }
            
            result = supabase_manager.create_video(video_data)
            
            if result:
                # Mettre à jour les stats de session
                session['files_added'] = session.get('files_added', 0) + 1
                session['total_size'] = session.get('total_size', 0) + (file_size or 0)
                session_manager.update(user_id, session)
                
                # Message de confirmation
                ep_text = f"S{season:02d}E{episode:02d}" if season else f"E{episode:02d}" if episode else "Film"
                
                confirm_text = (
                    f"✅ **Fichier ajouté!**\n\n"
                    f"📺 **{ep_text}** - {escape_markdown(clean_title[:40])}\n"
                    f"📁 Dossier: `{escape_markdown(folder_path)}`\n"
                    f"💾 Taille: **{format_file_size(file_size)}**\n"
                    f"⏱️ Durée: **{format_duration(duration)}**\n\n"
                )
                
                if filemoon_link:
                    confirm_text += "☁️ **Backup Filemoon:** ✅\n"
                else:
                    confirm_text += "☁️ **Backup Filemoon:** ❌ (uniquement ZeeX)\n"
                
                confirm_text += f"\n📊 **Session:** {session['files_added']} fichier(s) ajouté(s)"
                
                await status_msg.edit_text(confirm_text)
                logger.info(f"Vidéo ajoutée par {user_id}: {clean_title} dans {folder_path}")
            else:
                raise Exception("Échec de la création en base de données")
                
        except Exception as e:
            logger.error(f"Erreur traitement vidéo: {e}", exc_info=True)
            
            # Ajouter à la liste des erreurs de session
            session['errors'] = session.get('errors', [])
            session['errors'].append(str(e))
            session_manager.update(user_id, session)
            
            await status_msg.edit_text(
                f"❌ **Erreur lors du traitement**\n\n"
                f"`{escape_markdown(str(e)[:200])}`\n\n"
                f"La vidéo n'a pas été sauvegardée. Réessayez."
            )
    
    # =========================================================================
    # HANDLER CALLBACKS (BOUTONS INLINE)
    # =========================================================================
    
    @app.on_callback_query()
    async def handle_callback(client: Client, callback_query: CallbackQuery):
        """Gère tous les callbacks des boutons inline"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        # Vérifier admin
        if user_id not in ADMIN_IDS:
            await callback_query.answer("⛔ Accès refusé", show_alert=True)
            return
        
        try:
            # Parser le callback data
            parts = data.split(':', 2)
            action = parts[0]
            
            # Dispatcher vers le bon handler
            if action == "select_parent":
                await handle_select_parent(client, callback_query, parts)
            elif action == "select_parent_id":
                await handle_select_parent_id(client, callback_query, parts)
            elif action == "select_subfolder":
                await handle_select_subfolder(client, callback_query, parts)
            elif action == "create_subfolder":
                await handle_create_subfolder_callback(client, callback_query, parts)
            elif action == "view_folder":
                await handle_view_folder(client, callback_query, parts)
            elif action == "view_folder_by_name":
                await handle_view_folder_by_name(client, callback_query, parts)
            elif action == "list_subfolders":
                await handle_list_subfolders(client, callback_query, parts)
            elif action == "add_to_folder":
                await handle_add_to_folder(client, callback_query, parts)
            elif action == "delete_folder":
                await handle_delete_folder(client, callback_query, parts)
            elif action == "confirm_delete":
                await handle_confirm_delete(client, callback_query, parts)
            else:
                await callback_query.answer("❓ Action inconnue")
                
        except Exception as e:
            logger.error(f"Erreur callback {data}: {e}", exc_info=True)
            await callback_query.answer(f"❌ Erreur: {str(e)[:50]}", show_alert=True)
    
    async def handle_select_parent(client: Client, callback_query: CallbackQuery, parts: list):
        """Sélection d'un parent depuis suggestion fuzzy"""
        if len(parts) < 2:
            return
        
        parent_name = parts[1]
        parents = supabase_manager.get_folder_by_name(parent_name)
        
        if not parents:
            await callback_query.answer("❌ Dossier introuvable", show_alert=True)
            return
        
        parent = parents[0]
        
        # Créer session
        session_manager.set(callback_query.from_user.id, {
            'mode': 'creating_subfolder',
            'parent_id': parent['id'],
            'parent_name': parent['folder_name'],
            'step': 'waiting_for_name'
        })
        
        await callback_query.message.edit_text(
            f"📂 **Dossier parent:** `{escape_markdown(parent['folder_name'])}`\n\n"
            f"💬 Envoyez le nom du sous-dossier:"
        )
        await callback_query.answer()
    
    async def handle_select_parent_id(client: Client, callback_query: CallbackQuery, parts: list):
        """Sélection d'un parent par ID (cas multiples dossiers même nom)"""
        if len(parts) < 2:
            return
        
        parent_id = parts[1]
        parent = supabase_manager.get_folder_by_id(parent_id)
        
        if not parent:
            await callback_query.answer("❌ Dossier introuvable", show_alert=True)
            return
        
        session_manager.set(callback_query.from_user.id, {
            'mode': 'creating_subfolder',
            'parent_id': parent['id'],
            'parent_name': parent['folder_name'],
            'step': 'waiting_for_name'
        })
        
        await callback_query.message.edit_text(
            f"📂 **Dossier parent:** `{escape_markdown(parent['folder_name'])}`\n\n"
            f"💬 Envoyez le nom du sous-dossier:"
        )
        await callback_query.answer()
    
    async def handle_select_subfolder(client: Client, callback_query: CallbackQuery, parts: list):
        """Sélection d'un sous-dossier existant depuis suggestion"""
        if len(parts) < 3:
            return
        
        parent_id = parts[1]
        subfolder_name = parts[2]
        
        subfolders = supabase_manager.get_subfolders(parent_id)
        subfolder = next((s for s in subfolders if s['folder_name'] == subfolder_name), None)
        
        if not subfolder:
            await callback_query.answer("❌ Sous-dossier introuvable", show_alert=True)
            return
        
        # Activer mode ajout dans ce sous-dossier
        parent = supabase_manager.get_folder_by_id(parent_id)
        path = f"{parent['folder_name']}/{subfolder_name}"
        
        session_manager.set(callback_query.from_user.id, {
            'mode': 'adding_files',
            'folder_id': subfolder['id'],
            'folder_path': path,
            'folder_name': subfolder_name,
            'files_added': 0,
            'total_size': 0,
            'errors': []
        })
        
        await callback_query.message.edit_text(
            f"✅ **Mode ajout activé dans:**\n`{escape_markdown(path)}`\n\n"
            f"📤 Envoyez vos fichiers vidéo ou `/done` pour terminer."
        )
        await callback_query.answer("✅ Mode ajout activé")
    
    async def handle_create_subfolder_callback(client: Client, callback_query: CallbackQuery, parts: list):
        """Création rapide de sous-dossier depuis callback"""
        if len(parts) < 3:
            return
        
        parent_id = parts[1]
        subfolder_name = parts[2]
        
        try:
            result = supabase_manager.create_folder(subfolder_name, parent_id=parent_id)
            if result:
                parent = supabase_manager.get_folder_by_id(parent_id)
                await callback_query.message.edit_text(
                    f"✅ **Sous-dossier créé!**\n\n"
                    f"📂 Parent: `{escape_markdown(parent['folder_name'])}`\n"
                    f"📁 Nouveau: `{escape_markdown(subfolder_name)}`"
                )
                await callback_query.answer("✅ Créé avec succès")
            else:
                await callback_query.answer("❌ Erreur de création", show_alert=True)
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)[:50]}", show_alert=True)
    
    async def handle_view_folder(client: Client, callback_query: CallbackQuery, parts: list):
        """Afficher détails d'un dossier depuis callback"""
        if len(parts) < 2:
            return
        
        folder_id = parts[1]
        
        # Importer ici pour éviter circular import
        from bot.commands import display_folder_details
        
        await display_folder_details(callback_query.message, folder_id)
        await callback_query.answer()
    
    async def handle_view_folder_by_name(client: Client, callback_query: CallbackQuery, parts: list):
        """Afficher dossier depuis nom (recherche)"""
        if len(parts) < 2:
            return
        
        folder_name = parts[1]
        folders = supabase_manager.get_folder_by_name(folder_name)
        
        if folders:
            from bot.commands import display_folder_details
            await display_folder_details(callback_query.message, folders[0]['id'])
        else:
            await callback_query.answer("❌ Dossier introuvable", show_alert=True)
    
    async def handle_list_subfolders(client: Client, callback_query: CallbackQuery, parts: list):
        """Lister les sous-dossiers d'un dossier"""
        if len(parts) < 2:
            return
        
        parent_id = parts[1]
        subfolders = supabase_manager.get_subfolders(parent_id)
        parent = supabase_manager.get_folder_by_id(parent_id)
        
        if not subfolders:
            await callback_query.answer("📂 Aucun sous-dossier", show_alert=True)
            return
        
        text = f"📂 **Sous-dossiers de {escape_markdown(parent['folder_name'])}:**\n\n"
        buttons = []
        
        for sub in subfolders:
            video_count = len(supabase_manager.get_videos_by_folder(sub['id']))
            text += f"• **{escape_markdown(sub['folder_name'])}** ({video_count} vidéos)\n"
            buttons.append([InlineKeyboardButton(
                f"📁 {sub['folder_name'][:30]}",
                callback_data=f"view_folder:{sub['id']}"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 Retour", callback_data=f"view_folder:{parent_id}")])
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer()
    
    async def handle_add_to_folder(client: Client, callback_query: CallbackQuery, parts: list):
        """Activer mode ajout dans un dossier spécifique"""
        if len(parts) < 2:
            return
        
        folder_id = parts[1]
        folder = supabase_manager.get_folder_by_id(folder_id)
        
        if not folder:
            await callback_query.answer("❌ Dossier introuvable", show_alert=True)
            return
        
        # Construire le chemin complet
        path = folder['folder_name']
        if folder.get('parent_id'):
            parent = supabase_manager.get_folder_by_id(folder['parent_id'])
            if parent:
                path = f"{parent['folder_name']}/{path}"
        
        session_manager.set(callback_query.from_user.id, {
            'mode': 'adding_files',
            'folder_id': folder_id,
            'folder_path': path,
            'folder_name': folder['folder_name'],
            'files_added': 0,
            'total_size': 0,
            'errors': []
        })
        
        await callback_query.message.edit_text(
            f"✅ **Mode ajout activé**\n\n"
            f"📁 Dossier: `{escape_markdown(path)}`\n\n"
            f"📤 Envoyez vos fichiers vidéo ou `/done` pour terminer."
        )
        await callback_query.answer("✅ Mode ajout activé")
    
    async def handle_delete_folder(client: Client, callback_query: CallbackQuery, parts: list):
        """Demander confirmation de suppression"""
        if len(parts) < 2:
            return
        
        folder_id = parts[1]
        folder = supabase_manager.get_folder_by_id(folder_id)
        
        if not folder:
            await callback_query.answer("❌ Dossier introuvable", show_alert=True)
            return
        
        # Compter contenu
        videos = supabase_manager.get_videos_by_folder(folder_id)
        subfolders = supabase_manager.get_subfolders(folder_id)
        
        text = (
            f"⚠️ **Confirmer la suppression?**\n\n"
            f"📁 **{escape_markdown(folder['folder_name'])}**\n"
            f"• {len(videos)} vidéos seront supprimées\n"
            f"• {len(subfolders)} sous-dossiers seront supprimés\n\n"
            f"❗ **Cette action est irréversible!**"
        )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Oui, supprimer", callback_data=f"confirm_delete:{folder_id}"),
                InlineKeyboardButton("❌ Non, annuler", callback_data=f"view_folder:{folder_id}")
            ]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=buttons)
        await callback_query.answer("⚠️ Confirmation requise")
    
    async def handle_confirm_delete(client: Client, callback_query: CallbackQuery, parts: list):
        """Confirmer et exécuter la suppression"""
        if len(parts) < 2:
            return
        
        folder_id = parts[1]
        
        try:
            success = supabase_manager.delete_folder(folder_id)
            if success:
                await callback_query.message.edit_text("✅ **Dossier et tout son contenu supprimés**")
                await callback_query.answer("✅ Supprimé")
            else:
                await callback_query.answer("❌ Erreur de suppression", show_alert=True)
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)[:50]}", show_alert=True)
