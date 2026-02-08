"""
Commandes du bot Telegram ZeeXClub
Toutes les commandes disponibles pour les administrateurs
"""

import logging
from typing import Optional
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import ADMIN_IDS
from bot.sessions import SessionManager
from bot.utils import (
    parse_folder_path, is_valid_folder_name, escape_markdown,
    create_video_summary, fuzzy_search, format_file_size
)
from database.supabase_client import supabase_manager

logger = logging.getLogger(__name__)

def setup_commands(app: Client, session_manager: SessionManager):
    """
    Configure toutes les commandes du bot
    
    Args:
        app: Client Pyrogram
        session_manager: Gestionnaire de sessions
    """
    
    # =========================================================================
    # COMMANDE START
    # =========================================================================
    
    @app.on_message(filters.command("start") & filters.user(ADMIN_IDS))
    async def start_command(client: Client, message: Message):
        """Commande /start - Message de bienvenue et aide rapide"""
        user = message.from_user
        
        welcome_text = f"""
👋 **Bienvenue sur ZeeXClub Bot, {escape_markdown(user.first_name)}!**

🤖 **Bot de gestion de contenu vidéo**

📋 **Commandes disponibles:**

🗂️ **Gestion des dossiers:**
• `/create <nom>` - Créer un dossier racine
• `/addf <dossier>` - Créer un sous-dossier  
• `/view <nom>` - Voir contenu d'un dossier
• `/docs` - Lister tous les dossiers

📤 **Ajout de contenu:**
• `/add <chemin>` - Mode ajout de vidéos
• `/done` - Terminer le mode ajout

ℹ️ **Utilitaires:**
• `/stats` - Statistiques du bot
• `/help` - Aide détaillée

⚡ **Exemple rapide:**
/create Marvel /addf Marvel /add Marvel/Avengers Puis envoyez vos fichiers vidéo!
        """
        
        await message.reply(welcome_text, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE HELP
    # =========================================================================
    
    @app.on_message(filters.command("help") & filters.user(ADMIN_IDS))
    async def help_command(client: Client, message: Message):
        """Commande /help - Aide détaillée"""
        help_text = """
📚 **GUIDE COMPLET ZeeXClub Bot**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📁 GESTION DES DOSSIERS        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

**`/create <nom>`**
Crée un dossier racine (film ou série).
Ex: `/create Breaking Bad`

**`/addf <dossier_parent>`**
Crée un sous-dossier dans un dossier existant.
Le bot vous demandera ensuite le nom du sous-dossier.
Ex: `/addf Breaking Bad` → répondre `Saison 1`

**`/view <nom>`**
Affiche les détails d'un dossier avec toutes ses vidéos.
Supporte la recherche floue (tolère les fautes).
Ex: `/view breaking bad` ou `/view Breaking Bad/Saison 1`

**`/docs`**
Liste tous les dossiers racine avec pagination.

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📤 AJOUT DE VIDÉOS             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

**`/add <chemin>`**
Active le mode ajout de vidéos dans un dossier.
Formats de chemin acceptés:
• `/add Dossier` (dossier racine)
• `/add Parent/Enfant` (sous-dossier)

Une fois activé, envoyez simplement vos fichiers vidéo.
⚠️ **Important:** Ajoutez une caption avec le numéro d'épisode:
• `E01` ou `Ep 1`
• `S01E05` (Saison 1 Épisode 5)
• `Épisode 3`

Le bot détecte automatiquement et upload sur Filemoon.

**`/done`**
Termine le mode ajout et affiche un résumé.

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📝 FORMATS DE CAPTION          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Pour les séries, utilisez ces formats dans la caption:

**Numérotation simple:**
• `E05` → Épisode 5
• `Ep 12` → Épisode 12
• `Épisode 3` → Épisode 3

**Avec saison:**
• `S01E05` → Saison 1, Épisode 5
• `S2 Ep 3` → Saison 2, Épisode 3

**Titre personnalisé:**
• `S01E05 - Le début` → S01E05 avec titre

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ⚡ CONSEILS                    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

• Les noms de dossiers sont sensibles à la casse
• Utilisez `/docs` pour voir la liste exacte des noms
• Le bot accepte les vidéos jusqu'à 2GB (limite Telegram)
• L'upload Filemoon est automatique mais peut prendre du temps
• En cas d'erreur, vérifiez que le dossier existe avec `/view`

💡 **Besoin d'aide?** Contactez le développeur.
        """
        
        await message.reply(help_text, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE CREATE
    # =========================================================================
    
    @app.on_message(filters.command("create") & filters.user(ADMIN_IDS))
    async def create_folder_command(client: Client, message: Message):
        """Commande /create - Créer un dossier racine"""
        try:
            # Vérifier les arguments
            command_parts = message.text.split(maxsplit=1)
            
            if len(command_parts) < 2:
                await message.reply(
                    "❌ **Usage incorrect**\\n\\n"
                    "Utilisez: `/create <nom_dossier>`\\n"
                    "Exemple: `/create Stranger Things`",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            folder_name = command_parts[1].strip()
            
            # Valider le nom
            is_valid, error_msg = is_valid_folder_name(folder_name)
            if not is_valid:
                await message.reply(f"❌ **Nom invalide:** {error_msg}", parse_mode=enums.ParseMode.MARKDOWN)
                return
            
            # Vérifier si le dossier existe déjà (racine uniquement)
            existing = supabase_manager.get_folder_by_name(folder_name, parent_id=None)
            if existing:
                await message.reply(
                    f"⚠️ **Le dossier existe déjà!**\\n\\n"
                    f"📁 `{escape_markdown(folder_name)}`\\n"
                    f"🆔 `{existing[0]['id']}`\\n\\n"
                    f"Utilisez `/view {escape_markdown(folder_name)}` pour le voir.",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            # Créer le dossier
            result = supabase_manager.create_folder(folder_name, parent_id=None)
            
            if result:
                await message.reply(
                    f"✅ **Dossier créé avec succès!**\\n\\n"
                    f"📁 Nom: `{escape_markdown(folder_name)}`\\n"
                    f"🆔 ID: `{result['id']}`\\n\\n"
                    f"▶️ Prochaines étapes:\\n"
                    f"• `/addf {escape_markdown(folder_name)}` pour ajouter des sous-dossiers\\n"
                    f"• `/add {escape_markdown(folder_name)}` pour ajouter des vidéos directement",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                logger.info(f"Dossier créé par {message.from_user.id}: {folder_name}")
            else:
                await message.reply("❌ **Erreur lors de la création du dossier**", parse_mode=enums.ParseMode.MARKDOWN)
                
        except Exception as e:
            logger.error(f"Erreur commande create: {e}", exc_info=True)
            await message.reply(f"❌ **Erreur interne:** `{str(e)[:100]}`", parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE ADDF (ADD FOLDER)
    # =========================================================================
    
    @app.on_message(filters.command("addf") & filters.user(ADMIN_IDS))
    async def add_subfolder_command(client: Client, message: Message):
        """Commande /addf - Créer un sous-dossier"""
        try:
            command_parts = message.text.split(maxsplit=1)
            
            if len(command_parts) < 2:
                await message.reply(
                    "❌ **Usage incorrect**\\n\\n"
                    "Utilisez: `/addf <dossier_parent>`\\n"
                    "Exemple: `/addf Stranger Things`\\n\\n"
                    "Le bot vous demandera ensuite le nom du sous-dossier.",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            parent_name = command_parts[1].strip()
            
            # Rechercher le dossier parent
            parents = supabase_manager.get_folder_by_name(parent_name, parent_id=None)
            
            if not parents:
                # Recherche fuzzy pour suggestion
                all_folders = supabase_manager.get_all_folders(parent_id='null')
                all_names = [f['folder_name'] for f in all_folders]
                suggestions = fuzzy_search(parent_name, all_names, limit=3)
                
                if suggestions:
                    buttons = [
                        [InlineKeyboardButton(f"📁 {name}", callback_data=f"select_parent:{name}")]
                        for name in suggestions
                    ]
                    
                    await message.reply(
                        f"❌ Dossier `{escape_markdown(parent_name)}` introuvable.\\n\\n"
                        f"🔍 **Vouliez-vous dire:**",
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                else:
                    await message.reply(
                        f"❌ Dossier `{escape_markdown(parent_name)}` introuvable.\\n\\n"
                        f"Utilisez `/docs` pour voir la liste des dossiers.",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                return
            
            # Si plusieurs correspondances exactes (peu probable mais possible)
            if len(parents) > 1:
                buttons = [
                    [InlineKeyboardButton(f"📁 {p['folder_name']} (ID: {p['id'][:8]}...)", 
                                        callback_data=f"select_parent_id:{p['id']}")]
                    for p in parents[:5]
                ]
                
                await message.reply(
                    "🔍 **Plusieurs dossiers trouvés:**\\n"
                    "Sélectionnez le bon:",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            parent = parents[0]
            
            # Créer la session pour demander le nom du sous-dossier
            session_manager.set(message.from_user.id, {
                'mode': 'creating_subfolder',
                'parent_id': parent['id'],
                'parent_name': parent['folder_name'],
                'step': 'waiting_for_name'
            })
            
            await message.reply(
                f"📂 **Dossier parent sélectionné:**\\n"
                f"`{escape_markdown(parent['folder_name'])}`\\n\\n"
                f"💬 **Envoyez maintenant le nom du sous-dossier:**\\n"
                f"Exemples:\\n"
                f"• `Saison 1`\\n"
                f"• `Épisodes spéciaux`\\n"
                f"• `Partie 1`\\n\\n"
                f"❌ Envoyez `/cancel` pour annuler",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Erreur commande addf: {e}", exc_info=True)
            await message.reply(f"❌ **Erreur interne:** `{str(e)[:100]}`", parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE ADD (MODE AJOUT VIDÉOS)
    # =========================================================================
    
    @app.on_message(filters.command("add") & filters.user(ADMIN_IDS))
    async def add_files_command(client: Client, message: Message):
        """Commande /add - Activer le mode ajout de fichiers"""
        try:
            command_parts = message.text.split(maxsplit=1)
            
            if len(command_parts) < 2:
                await message.reply(
                    "❌ **Usage incorrect**\\n\\n"
                    "Utilisez: `/add <chemin>`\\n\\n"
                    "**Formats acceptés:**\\n"
                    "• `/add Dossier` (dossier racine)\\n"
                    "• `/add Parent/Sous-dossier` (chemin complet)\\n\\n"
                    "**Exemples:**\\n"
                    "• `/add Breaking Bad`\\n"
                    "• `/add Breaking Bad/Saison 1`",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            path = command_parts[1].strip()
            parent_name, subfolder_name = parse_folder_path(path)
            
            if not parent_name:
                await message.reply("❌ Chemin invalide", parse_mode=enums.ParseMode.MARKDOWN)
                return
            
            # Rechercher le dossier parent
            parents = supabase_manager.get_folder_by_name(parent_name, parent_id=None)
            
            if not parents:
                await message.reply(
                    f"❌ Dossier `{escape_markdown(parent_name)}` introuvable.\\n"
                    f"Créez-le d'abord avec `/create {escape_markdown(parent_name)}`",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            parent = parents[0]
            target_folder = parent
            
            # Si sous-dossier spécifié, le rechercher
            if subfolder_name:
                subfolders = supabase_manager.get_subfolders(parent['id'])
                subfolder = next(
                    (s for s in subfolders if s['folder_name'].lower() == subfolder_name.lower()),
                    None
                )
                
                if not subfolder:
                    # Suggestions de sous-dossiers existants
                    sub_names = [s['folder_name'] for s in subfolders]
                    suggestions = fuzzy_search(subfolder_name, sub_names, limit=3)
                    
                    if suggestions:
                        buttons = [
                            [InlineKeyboardButton(f"📁 {name}", 
                                                callback_data=f"select_subfolder:{parent['id']}:{name}")]
                            for name in suggestions
                        ]
                        buttons.append([InlineKeyboardButton(
                            "➕ Créer ce sous-dossier", 
                            callback_data=f"create_subfolder:{parent['id']}:{subfolder_name}"
                        )])
                        
                        await message.reply(
                            f"❌ Sous-dossier `{escape_markdown(subfolder_name)}` introuvable dans `{escape_markdown(parent_name)}`.\\n\\n"
                            f"🔍 **Existants:** {', '.join(suggestions)}\\n\\n"
                            f"Ou créez-en un nouveau:",
                            reply_markup=InlineKeyboardMarkup(buttons),
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                        return
                
                target_folder = subfolder
            
            # Vérifier s'il y a déjà des vidéos dans ce dossier
            existing_videos = supabase_manager.get_videos_by_folder(target_folder['id'])
            
            # Créer la session
            session_manager.set(message.from_user.id, {
                'mode': 'adding_files',
                'folder_id': target_folder['id'],
                'folder_path': path,
                'folder_name': target_folder['folder_name'],
                'files_added': 0,
                'total_size': 0,
                'errors': []
            })
            
            status_text = (
                f"✅ **Mode ajout activé**\\n\\n"
                f"📁 **Dossier:** `{escape_markdown(path)}`\\n"
            )
            
            if existing_videos:
                status_text += f"📊 **Contenu existant:** {len(existing_videos)} vidéos\\n"
            
            status_text += (
                f"\\n📤 **Envoyez vos fichiers vidéo maintenant**\\n\\n"
                f"💡 **Conseils pour les captions:**\\n"
                f"• `E01` ou `Ep 1` → Épisode 1\\n"
                f"• `S01E05` → Saison 1, Épisode 5\\n"
                f"• `S2 Ep 3 - Titre` → Avec titre personnalisé\\n\\n"
                f"⏹️ **Terminer:** `/done`\\n"
                f"❌ **Annuler:** `/cancel`"
            )
            
            await message.reply(status_text, parse_mode=enums.ParseMode.MARKDOWN)
            logger.info(f"Mode ajout activé par {message.from_user.id} dans {path}")
            
        except Exception as e:
            logger.error(f"Erreur commande add: {e}", exc_info=True)
            await message.reply(f"❌ **Erreur interne:** `{str(e)[:100]}`", parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE DONE
    # =========================================================================
    
    @app.on_message(filters.command("done") & filters.user(ADMIN_IDS))
    async def done_command(client: Client, message: Message):
        """Commande /done - Terminer le mode ajout"""
        session = session_manager.get(message.from_user.id)
        
        if not session or session.get('mode') != 'adding_files':
            await message.reply(
                "⚠️ **Aucun mode ajout actif**\\n\\n"
                "Utilisez d'abord `/add <dossier>` pour commencer.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return
        
        # Récupérer les stats finales
        folder_path = session.get('folder_path', 'Inconnu')
        files_added = session.get('files_added', 0)
        total_size = session.get('total_size', 0)
        errors = session.get('errors', [])
        
        # Supprimer la session
        session_manager.delete(message.from_user.id)
        
        # Message de confirmation
        summary = (
            f"✅ **Mode ajout terminé**\\n\\n"
            f"📁 **Dossier:** `{escape_markdown(folder_path)}`\\n"
            f"📊 **Résumé:**\\n"
            f"  • Vidéos ajoutées: **{files_added}**\\n"
            f"  • Taille totale: **{format_file_size(total_size)}**\\n"
        )
        
        if errors:
            summary += f"\\n⚠️ **Erreurs ({len(errors)}):**\\n"
            for error in errors[:5]:  # Limiter à 5 erreurs
                summary += f"  • `{escape_markdown(str(error)[:50])}`\\n"
        
        summary += (
            f"\\n▶️ **Prochaines étapes:**\\n"
            f"• `/view {escape_markdown(folder_path)}` pour voir le contenu\\n"
            f"• `/add {escape_markdown(folder_path)}` pour ajouter plus de vidéos"
        )
        
        await message.reply(summary, parse_mode=enums.ParseMode.MARKDOWN)
        logger.info(f"Mode ajout terminé par {message.from_user.id}: {files_added} fichiers")
    
    # =========================================================================
    # COMMANDE CANCEL
    # =========================================================================
    
    @app.on_message(filters.command("cancel") & filters.user(ADMIN_IDS))
    async def cancel_command(client: Client, message: Message):
        """Commande /cancel - Annuler l'opération en cours"""
        session = session_manager.get(message.from_user.id)
        
        if not session:
            await message.reply("ℹ️ Aucune opération à annuler.", parse_mode=enums.ParseMode.MARKDOWN)
            return
        
        mode = session.get('mode', 'inconnu')
        session_manager.delete(message.from_user.id)
        
        mode_names = {
            'adding_files': 'ajout de fichiers',
            'creating_subfolder': 'création de sous-dossier',
            'selecting_parent': 'sélection de dossier'
        }
        
        await message.reply(
            f"❌ **Opération annulée**\\n\\n"
            f"Mode: {mode_names.get(mode, mode)}\\n"
            f"Les données non sauvegardées ont été perdues.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    
    # =========================================================================
    # COMMANDE VIEW
    # =========================================================================
    
    @app.on_message(filters.command("view") & filters.user(ADMIN_IDS))
    async def view_command(client: Client, message: Message):
        """Commande /view - Voir le contenu d'un dossier"""
        try:
            command_parts = message.text.split(maxsplit=1)
            
            if len(command_parts) < 2:
                await message.reply(
                    "❌ **Usage incorrect**\\n\\n"
                    "Utilisez: `/view <nom_dossier>`\\n"
                    "Exemples:\\n"
                    "• `/view Stranger Things`\\n"
                    "• `/view Stranger Things/Saison 1`",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            search_query = command_parts[1].strip()
            
            # Si chemin complet (avec /), parser
            if '/' in search_query:
                parent_name, sub_name = parse_folder_path(search_query)
                
                # Trouver parent
                parents = supabase_manager.get_folder_by_name(parent_name)
                if not parents:
                    await message.reply(f"❌ Dossier `{escape_markdown(parent_name)}` introuvable", parse_mode=enums.ParseMode.MARKDOWN)
                    return
                
                parent = parents[0]
                
                # Trouver sous-dossier
                subfolders = supabase_manager.get_subfolders(parent['id'])
                subfolder = next(
                    (s for s in subfolders if s['folder_name'].lower() == sub_name.lower()),
                    None
                )
                
                if not subfolder:
                    await message.reply(
                        f"❌ Sous-dossier `{escape_markdown(sub_name)}` introuvable dans `{escape_markdown(parent_name)}`",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                    return
                
                await display_folder_details(message, subfolder['id'])
            else:
                # Recherche simple
                folders = supabase_manager.get_folder_by_name(search_query)
                
                if not folders:
                    # Recherche fuzzy
                    all_folders = supabase_manager.get_all_folders()
                    all_names = list(set(f['folder_name'] for f in all_folders))
                    suggestions = fuzzy_search(search_query, all_names, limit=5)
                    
                    if suggestions:
                        buttons = [
                            [InlineKeyboardButton(f"📁 {name}", callback_data=f"view_folder_by_name:{name}")]
                            for name in suggestions
                        ]
                        
                        await message.reply(
                            f"❌ Dossier `{escape_markdown(search_query)}` introuvable.\\n\\n"
                            f"🔍 **Suggestions:**",
                            reply_markup=InlineKeyboardMarkup(buttons),
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    else:
                        await message.reply(
                            f"❌ Aucun dossier trouvé pour `{escape_markdown(search_query)}`",
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    return
                
                if len(folders) == 1:
                    await display_folder_details(message, folders[0]['id'])
                else:
                    # Plusieurs dossiers avec même nom (différents parents)
                    buttons = [
                        [InlineKeyboardButton(
                            f"📁 {f['folder_name']} (ID: {f['id'][:8]}...)", 
                            callback_data=f"view_folder:{f['id']}"
                        )]
                        for f in folders[:5]
                    ]
                    
                    await message.reply(
                        f"🔍 **{len(folders)} dossiers trouvés:**\\n"
                        f"Sélectionnez le bon:",
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                    
        except Exception as e:
            logger.error(f"Erreur commande view: {e}", exc_info=True)
            await message.reply(f"❌ **Erreur interne:** `{str(e)[:100]}`", parse_mode=enums.ParseMode.MARKDOWN)
    
    async def display_folder_details(message: Message, folder_id: str):
        """Affiche les détails d'un dossier"""
        folder = supabase_manager.get_folder_by_id(folder_id)
        if not folder:
            await message.reply("❌ Dossier introuvable", parse_mode=enums.ParseMode.MARKDOWN)
            return
        
        videos = supabase_manager.get_videos_by_folder(folder_id)
        
        # Construire le message
        header = f"📁 **{escape_markdown(folder['folder_name'])}**\\n\\n"
        
        if videos:
            header += create_video_summary(videos)
        else:
            header += "📂 **Dossier vide**\\n\\n"
            header += "Utilisez `/add` pour ajouter des vidéos."
        
        # Boutons d'action
        buttons = []
        
        # Vérifier s'il y a des sous-dossiers
        subfolders = supabase_manager.get_subfolders(folder_id)
        if subfolders:
            buttons.append([InlineKeyboardButton(
                f"📂 Voir les {len(subfolders)} sous-dossiers", 
                callback_data=f"list_subfolders:{folder_id}"
            )])
        
        buttons.append([
            InlineKeyboardButton("➕ Ajouter des vidéos", callback_data=f"add_to_folder:{folder_id}"),
            InlineKeyboardButton("🗑️ Supprimer", callback_data=f"delete_folder:{folder_id}")
        ])
        
        await message.reply(header, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE DOCS (LISTE DES DOSSIERS)
    # =========================================================================
    
    @app.on_message(filters.command("docs") & filters.user(ADMIN_IDS))
    async def docs_command(client: Client, message: Message):
        """Commande /docs - Lister tous les dossiers"""
        try:
            folders = supabase_manager.get_all_folders(parent_id='null')
            
            if not folders:
                await message.reply(
                    "📂 **Aucun dossier créé**\\n\\n"
                    "Commencez par créer un dossier:\\n"
                    "`/create Mon Film`",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                return
            
            total_videos = sum(f.get('videos', [{}])[0].get('count', 0) for f in folders)
            
            lines = [
                f"📚 **LISTE DES DOSSIERS** ({len(folders)} total, {total_videos} vidéos)\\n",
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓"
            ]
            
            for i, folder in enumerate(folders[:20], 1):  # Limiter à 20
                video_count = folder.get('videos', [{}])[0].get('count', 0)
                subfolder_count = len(supabase_manager.get_subfolders(folder['id']))
                
                lines.append(
                    f"┃ {i:2d}. **{escape_markdown(folder['folder_name'][:30])}**"
                    f"{' ' * (30 - len(folder['folder_name'][:30]))}┃"
                )
                lines.append(
                    f"┃    📂 {subfolder_count} sous-dossiers | 🎬 {video_count} vidéos"
                    f"{' ' * (15 - len(str(subfolder_count)) - len(str(video_count)))}┃"
                )
            
            if len(folders) > 20:
                lines.append(f"┃ ... et {len(folders) - 20} autres dossiers")
            
            lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
            lines.append("\\n💡 Cliquez sur un dossier pour voir les détails")
            
            # Créer des boutons pour les 10 premiers dossiers
            buttons = []
            for folder in folders[:10]:
                video_count = folder.get('videos', [{}])[0].get('count', 0)
                buttons.append([InlineKeyboardButton(
                    f"📁 {folder['folder_name'][:25]} ({video_count} 🎬)",
                    callback_data=f"view_folder:{folder['id']}"
                )])
            
            await message.reply(
                "\\n".join(lines),
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Erreur commande docs: {e}", exc_info=True)
            await message.reply(f"❌ **Erreur interne:** `{str(e)[:100]}`", parse_mode=enums.ParseMode.MARKDOWN)
    
    # =========================================================================
    # COMMANDE STATS
    # =========================================================================
    
    @app.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
    async def stats_command(client: Client, message: Message):
        """Commande /stats - Statistiques du système"""
        try:
            # Récupérer les stats
            folders = supabase_manager.get_all_folders()
            total_folders = len(folders)
            
            # Compter les sous-dossiers
            total_subfolders = 0
            for folder in folders:
                total_subfolders += len(supabase_manager.get_subfolders(folder['id']))
            
            # Stats sessions
            session_stats = session_manager.get_stats()
            
            stats_text = f"""
📊 **STATISTIQUES ZeeXClub**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📁 CONTENU                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
• Dossiers racine: **{total_folders}**
• Sous-dossiers: **{total_subfolders}**
• Total dossiers: **{total_folders + total_subfolders}**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🤖 BOT                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
• Sessions actives: **{session_stats['total']}**
  - Mode ajout: {session_stats['adding_files']}
  - Création sous-dossier: {session_stats['creating_subfolder']}
  - Autres: {session_stats['other']}

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  👤 ADMIN                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
• Votre ID: `{message.from_user.id}`
            """
            
            await message.reply(stats_text, parse_mode=enums.ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Erreur commande stats: {e}", exc_info=True)
            await message.reply(f"❌ **Erreur interne:** `{str(e)[:100]}`", parse_mode=enums.ParseMode.MARKDOWN)
