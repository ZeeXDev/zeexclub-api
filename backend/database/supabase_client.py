# backend/database/supabase_client.py
"""
Client Supabase pour ZeeXClub
Gestion de la connexion et des opérations de base de données
"""

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
import logging

logger = logging.getLogger(__name__)

class SupabaseManager:
    """
    Gestionnaire singleton pour le client Supabase
    Gère deux clients : un pour les opérations publiques (RLS) 
    et un pour les opérations admin (service role)
    """
    
    _instance = None
    _client: Client = None
    _service_client: Client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialise les deux clients Supabase"""
        try:
            # Client standard (respecte les RLS policies)
            self._client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("✅ Client Supabase standard initialisé")
            
            # Client service (contourne les RLS, pour le bot)
            if SUPABASE_SERVICE_KEY:
                self._service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
                logger.info("✅ Client Supabase service initialisé")
            else:
                logger.warning("⚠️ Pas de SERVICE_KEY, utilisation du client standard pour tout")
                self._service_client = self._client
                
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Supabase: {e}")
            raise
    
    @property
    def client(self) -> Client:
        """Retourne le client standard (respecte RLS)"""
        if self._client is None:
            self._initialize_clients()
        return self._client
    
    @property
    def service_client(self) -> Client:
        """Retourne le client service (admin, contourne RLS)"""
        if self._service_client is None:
            self._initialize_clients()
        return self._service_client
    
    # =========================================================================
    # OPÉRATIONS SUR LES DOSSIERS (FOLDERS)
    # =========================================================================
    
    def create_folder(self, folder_name: str, parent_id: str = None, use_service: bool = True) -> dict:
        """
        Crée un nouveau dossier
        
        Args:
            folder_name: Nom du dossier
            parent_id: ID du dossier parent (None pour racine)
            use_service: Utiliser le client service (True) ou standard (False)
        
        Returns:
            dict: Données du dossier créé
        """
        client = self.service_client if use_service else self.client
        
        data = {
            'folder_name': folder_name,
            'parent_id': parent_id
        }
        
        try:
            result = client.table('folders').insert(data).execute()
            logger.info(f"✅ Dossier créé: {folder_name}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur création dossier {folder_name}: {e}")
            raise
    
    def get_folder_by_name(self, folder_name: str, parent_id: str = None, use_service: bool = True) -> list:
        """
        Recherche un dossier par nom (optionnellement dans un parent spécifique)
        
        Args:
            folder_name: Nom à rechercher
            parent_id: Filtrer par parent (None pour racine uniquement)
            use_service: Utiliser le client service
        
        Returns:
            list: Liste des dossiers correspondants
        """
        client = self.service_client if use_service else self.client
        
        query = client.table('folders').select('*').eq('folder_name', folder_name)
        
        if parent_id is not None:
            query = query.eq('parent_id', parent_id)
        else:
            query = query.is_('parent_id', 'null')
        
        try:
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur recherche dossier {folder_name}: {e}")
            return []
    
    def get_folder_by_id(self, folder_id: str, use_service: bool = True) -> dict:
        """
        Récupère un dossier par son ID
        
        Args:
            folder_id: UUID du dossier
            use_service: Utiliser le client service
        
        Returns:
            dict: Données du dossier ou None
        """
        client = self.service_client if use_service else self.client
        
        try:
            # ✅ CORRECTION: Utiliser .limit(1) au lieu de .single() pour éviter l'erreur si pas de résultat
            result = client.table('folders').select('*').eq('id', folder_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur récupération dossier {folder_id}: {e}")
            return None
    
    def get_all_folders(self, parent_id: str = None, use_service: bool = True) -> list:
        """
        Récupère tous les dossiers (optionnellement filtrés par parent)
        
        Args:
            parent_id: Filtrer par parent (None pour tous, 'null' pour racine)
            use_service: Utiliser le client service
        
        Returns:
            list: Liste des dossiers
        """
        client = self.service_client if use_service else self.client
        
        query = client.table('folders').select('*, videos(count)')
        
        if parent_id == 'null':
            query = query.is_('parent_id', 'null')
        elif parent_id:
            query = query.eq('parent_id', parent_id)
        
        try:
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération dossiers: {e}")
            return []
    
    def get_subfolders(self, parent_id: str, use_service: bool = True) -> list:
        """
        Récupère tous les sous-dossiers d'un dossier parent
        
        Args:
            parent_id: ID du dossier parent
            use_service: Utiliser le client service
        
        Returns:
            list: Liste des sous-dossiers
        """
        client = self.service_client if use_service else self.client
        
        try:
            result = client.table('folders').select('*').eq('parent_id', parent_id).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération sous-dossiers de {parent_id}: {e}")
            return []
    
    def update_folder(self, folder_id: str, updates: dict, use_service: bool = True) -> dict:
        """
        Met à jour un dossier
        
        Args:
            folder_id: ID du dossier
            updates: Dictionnaire des champs à mettre à jour
            use_service: Utiliser le client service
        
        Returns:
            dict: Données mises à jour
        """
        client = self.service_client if use_service else self.client
        
        try:
            result = client.table('folders').update(updates).eq('id', folder_id).execute()
            logger.info(f"✅ Dossier {folder_id} mis à jour")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour dossier {folder_id}: {e}")
            raise
    
    def delete_folder(self, folder_id: str, use_service: bool = True) -> bool:
        """
        Supprime un dossier et tout son contenu (cascade)
        
        Args:
            folder_id: ID du dossier
            use_service: Utiliser le client service
        
        Returns:
            bool: True si supprimé avec succès
        """
        client = self.service_client if use_service else self.client
        
        try:
            # Supprimer d'abord toutes les vidéos du dossier
            client.table('videos').delete().eq('folder_id', folder_id).execute()
            
            # Supprimer les sous-dossiers récursivement
            subfolders = self.get_subfolders(folder_id, use_service)
            for sub in subfolders:
                self.delete_folder(sub['id'], use_service)
            
            # Supprimer le dossier lui-même
            client.table('folders').delete().eq('id', folder_id).execute()
            
            logger.info(f"✅ Dossier {folder_id} supprimé avec tout son contenu")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur suppression dossier {folder_id}: {e}")
            return False
    
    # =========================================================================
    # OPÉRATIONS SUR LES VIDÉOS
    # =========================================================================
    
    def create_video(self, video_data: dict, use_service: bool = True) -> dict:
        """
        Crée une nouvelle entrée vidéo
        
        Args:
            video_data: Dictionnaire avec les données de la vidéo
                Required: folder_id, title, file_id, zeex_url
                Optional: episode_number, season_number, filemoon_url, 
                         caption, duration, file_size, poster_url, etc.
            use_service: Utiliser le client service
        
        Returns:
            dict: Données de la vidéo créée
        """
        client = self.service_client if use_service else self.client
        
        # S'assurer que les champs requis sont présents
        required = ['folder_id', 'title', 'file_id', 'zeex_url']
        for field in required:
            if field not in video_data or not video_data[field]:
                raise ValueError(f"Champ requis manquant: {field}")
        
        try:
            result = client.table('videos').insert(video_data).execute()
            logger.info(f"✅ Vidéo créée: {video_data.get('title', 'Unknown')}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur création vidéo: {e}")
            raise
    
    def get_video_by_id(self, video_id: str, use_service: bool = False) -> dict:
        """
        Récupère une vidéo par son ID
        
        Args:
            video_id: UUID de la vidéo
            use_service: Utiliser le client service (False pour respecter RLS)
        
        Returns:
            dict: Données de la vidéo ou None
        """
        client = self.service_client if use_service else self.client
        
        try:
            # ✅ CORRECTION: Utiliser .limit(1) au lieu de .single()
            result = client.table('videos').select('*').eq('id', video_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur récupération vidéo {video_id}: {e}")
            return None
    
    def get_videos_by_folder(self, folder_id: str, order_by: str = 'episode_number', use_service: bool = True) -> list:
        """
        Récupère toutes les vidéos d'un dossier
        
        Args:
            folder_id: ID du dossier
            order_by: Champ pour le tri (episode_number, created_at, title)
            use_service: Utiliser le client service
        
        Returns:
            list: Liste des vidéos
        """
        client = self.service_client if use_service else self.client
        
        try:
            query = client.table('videos').select('*').eq('folder_id', folder_id)
            
            if order_by == 'episode_number':
                query = query.order('season_number', desc=False).order('episode_number', desc=False)
            elif order_by == 'created_at':
                query = query.order('created_at', desc=True)
            else:
                query = query.order(order_by)
            
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération vidéos du dossier {folder_id}: {e}")
            return []
    
    def get_video_by_file_id(self, file_id: str, use_service: bool = True) -> dict:
        """
        Récupère une vidéo par son file_id Telegram
        
        Args:
            file_id: file_id Telegram unique
            use_service: Utiliser le client service
        
        Returns:
            dict: Données de la vidéo ou None
        """
        client = self.service_client if use_service else self.client
        
        try:
            # ✅ CORRECTION: Utiliser .limit(1) au lieu de .single()
            result = client.table('videos').select('*').eq('file_id', file_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur récupération vidéo par file_id: {e}")
            return None
    
    def update_video(self, video_id: str, updates: dict, use_service: bool = True) -> dict:
        """
        Met à jour une vidéo
        
        Args:
            video_id: ID de la vidéo
            updates: Dictionnaire des champs à mettre à jour
            use_service: Utiliser le client service
        
        Returns:
            dict: Données mises à jour
        """
        client = self.service_client if use_service else self.client
        
        try:
            result = client.table('videos').update(updates).eq('id', video_id).execute()
            logger.info(f"✅ Vidéo {video_id} mise à jour")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour vidéo {video_id}: {e}")
            raise
    
    def delete_video(self, video_id: str, use_service: bool = True) -> bool:
        """
        Supprime une vidéo
        
        Args:
            video_id: ID de la vidéo
            use_service: Utiliser le client service
        
        Returns:
            bool: True si supprimée avec succès
        """
        client = self.service_client if use_service else self.client
        
        try:
            client.table('videos').delete().eq('id', video_id).execute()
            logger.info(f"✅ Vidéo {video_id} supprimée")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur suppression vidéo {video_id}: {e}")
            return False
    
    def search_videos(self, query: str, filters: dict = None, limit: int = 20, use_service: bool = False) -> list:
        """
        Recherche de vidéos par titre (recherche textuelle)
        
        Args:
            query: Terme de recherche
            filters: Filtres additionnels (genre, year, etc.)
            limit: Nombre maximum de résultats
            use_service: Utiliser le client service
        
        Returns:
            list: Liste des vidéos correspondantes
        """
        client = self.service_client if use_service else self.client
        
        try:
            # ✅ CORRECTION: Gérer le cas où query est vide
            if query and query.strip():
                # Recherche par titre (ilike = insensible à la casse)
                db_query = client.table('videos').select('*, folders(folder_name)').ilike('title', f'%{query}%')
            else:
                # Si pas de query, retourner les plus récents
                db_query = client.table('videos').select('*, folders(folder_name)').order('created_at', desc=True)
            
            # Appliquer les filtres additionnels
            if filters:
                if 'genre' in filters and filters['genre']:
                    db_query = db_query.contains('genre', [filters['genre']])
                if 'year' in filters and filters['year']:
                    db_query = db_query.eq('year', filters['year'])
                if 'rating' in filters and filters['rating']:
                    db_query = db_query.gte('rating', filters['rating'])
            
            result = db_query.limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur recherche vidéos: {e}")
            return []
    
    def get_recent_videos(self, limit: int = 12, use_service: bool = False) -> list:
        """
        Récupère les vidéos les plus récentes
        
        Args:
            limit: Nombre de vidéos à récupérer
            use_service: Utiliser le client service
        
        Returns:
            list: Liste des vidéos récentes
        """
        client = self.service_client if use_service else self.client
        
        try:
            result = client.table('videos').select('*, folders(folder_name)').order('created_at', desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération vidéos récentes: {e}")
            return []
    
    # =========================================================================
    # OPÉRATIONS SUR LES COMMENTAIRES
    # =========================================================================
    
    def create_comment(self, video_id: str, user_id: str, comment_text: str) -> dict:
        """
        Crée un nouveau commentaire (utilise client standard pour RLS)
        
        Args:
            video_id: ID de la vidéo
            user_id: ID de l'utilisateur (depuis auth.users)
            comment_text: Texte du commentaire
        
        Returns:
            dict: Données du commentaire créé
        """
        if len(comment_text) > 1000:
            raise ValueError("Le commentaire ne doit pas dépasser 1000 caractères")
        
        data = {
            'video_id': video_id,
            'user_id': user_id,
            'comment_text': comment_text
        }
        
        try:
            result = self.client.table('comments').insert(data).execute()
            logger.info(f"✅ Commentaire créé par {user_id} sur {video_id}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur création commentaire: {e}")
            raise
    
    def get_comments_by_video(self, video_id: str, limit: int = 50) -> list:
        """
        Récupère les commentaires d'une vidéo avec infos utilisateur
        
        Args:
            video_id: ID de la vidéo
            limit: Nombre maximum de commentaires
        
        Returns:
            list: Liste des commentaires avec données utilisateur
        """
        try:
            result = self.client.table('comments').select(
                '*, users(email, display_name, avatar_url)'
            ).eq('video_id', video_id).order('created_at', desc=True).limit(limit).execute()
            
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération commentaires: {e}")
            return []
    
    def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """
        Supprime un commentaire (vérifie que l'utilisateur est le propriétaire via RLS)
        
        Args:
            comment_id: ID du commentaire
            user_id: ID de l'utilisateur (pour vérification RLS)
        
        Returns:
            bool: True si supprimé avec succès
        """
        try:
            # RLS vérifie automatiquement que user_id = auth.uid()
            self.client.table('comments').delete().eq('id', comment_id).execute()
            logger.info(f"✅ Commentaire {comment_id} supprimé")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur suppression commentaire {comment_id}: {e}")
            return False
    
    # =========================================================================
    # OPÉRATIONS SUR L'HISTORIQUE ET WATCHLIST
    # =========================================================================
    
    def add_to_watchlist(self, user_id: str, video_id: str) -> dict:
        """
        Ajoute une vidéo à la liste de l'utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            video_id: ID de la vidéo
        
        Returns:
            dict: Données de l'entrée créée
        """
        try:
            result = self.client.table('watchlist').insert({
                'user_id': user_id,
                'video_id': video_id
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            # Gérer le cas où l'entrée existe déjà (contrainte UNIQUE)
            if 'duplicate key' in str(e).lower() or '23505' in str(e):
                logger.info(f"ℹ️ Vidéo {video_id} déjà dans la watchlist de {user_id}")
                # Retourner l'entrée existante
                existing = self.client.table('watchlist').select('*').eq('user_id', user_id).eq('video_id', video_id).limit(1).execute()
                return existing.data[0] if existing.data else None
            logger.error(f"❌ Erreur ajout watchlist: {e}")
            raise
    
    def get_watchlist(self, user_id: str) -> list:
        """
        Récupère la liste de l'utilisateur avec détails des vidéos
        
        Args:
            user_id: ID de l'utilisateur
        
        Returns:
            list: Liste des vidéos dans la watchlist
        """
        try:
            # ✅ CORRECTION: Syntaxe de jointure correcte pour Supabase
            result = self.client.table('watchlist').select(
                '*, video: videos(*)'
            ).eq('user_id', user_id).order('added_at', desc=True).execute()
            
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération watchlist: {e}")
            return []
    
    def remove_from_watchlist(self, user_id: str, video_id: str) -> bool:
        """
        Retire une vidéo de la liste de l'utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            video_id: ID de la vidéo
        
        Returns:
            bool: True si retiré avec succès
        """
        try:
            self.client.table('watchlist').delete().eq('user_id', user_id).eq('video_id', video_id).execute()
            logger.info(f"✅ Vidéo {video_id} retirée de la watchlist de {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur retrait watchlist: {e}")
            return False
    
    def update_watch_history(self, user_id: str, video_id: str, progress: int, completed: bool = False) -> dict:
        """
        Met à jour ou crée l'historique de visionnage
        
        Args:
            user_id: ID de l'utilisateur
            video_id: ID de la vidéo
            progress: Progression en secondes
            completed: True si la vidéo est terminée (>90%)
        
        Returns:
            dict: Données de l'historique mis à jour
        """
        try:
            # Utiliser upsert pour créer ou mettre à jour
            result = self.client.table('watch_history').upsert({
                'user_id': user_id,
                'video_id': video_id,
                'progress': progress,
                'completed': completed
            }).execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour historique: {e}")
            raise
    
    def get_watch_history(self, user_id: str, completed_only: bool = False, limit: int = 20) -> list:
        """
        Récupère l'historique de visionnage de l'utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            completed_only: Ne récupérer que les vidéos terminées
            limit: Nombre maximum d'entrées
        
        Returns:
            list: Liste de l'historique avec détails vidéo
        """
        try:
            # ✅ CORRECTION: Syntaxe de jointure correcte et gestion des filtres
            query = self.client.table('watch_history').select(
                '*, video: videos(*)'
            ).eq('user_id', user_id)
            
            if completed_only:
                query = query.eq('completed', True)
            else:
                # Par défaut, exclure les complétés pour "Continuer à regarder"
                query = query.eq('completed', False)
            
            result = query.order('last_watched', desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Erreur récupération historique: {e}")
            return []
    
    # =========================================================================
    # OPÉRATIONS SUR LES MAPPINGS DE STREAM
    # =========================================================================
    
    def create_stream_mapping(self, unique_id: str, file_id: str) -> dict:
        """
        Crée un mapping entre unique_id et file_id Telegram
        
        Args:
            unique_id: Hash MD5 unique généré
            file_id: file_id Telegram
        
        Returns:
            dict: Données du mapping créé
        """
        try:
            result = self.service_client.table('stream_mappings').insert({
                'unique_id': unique_id,
                'file_id': file_id
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            # Si le mapping existe déjà, on le retourne
            existing = self.get_stream_mapping(unique_id)
            if existing:
                return existing
            logger.error(f"❌ Erreur création stream mapping: {e}")
            raise
    
    def get_stream_mapping(self, unique_id: str) -> dict:
        """
        Récupère le mapping par unique_id
        
        Args:
            unique_id: ID unique du stream
        
        Returns:
            dict: Mapping avec file_id ou None
        """
        try:
            # ✅ CORRECTION: Utiliser .limit(1) au lieu de .single()
            result = self.service_client.table('stream_mappings').select('*').eq('unique_id', unique_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur récupération stream mapping: {e}")
            return None
    
    def get_stream_mapping_by_file_id(self, file_id: str) -> dict:
        """
        Récupère le mapping par file_id
        
        Args:
            file_id: file_id Telegram
        
        Returns:
            dict: Mapping ou None
        """
        try:
            # ✅ CORRECTION: Utiliser .limit(1) au lieu de .single()
            result = self.service_client.table('stream_mappings').select('*').eq('file_id', file_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Erreur récupération stream mapping par file_id: {e}")
            return None


# Instance singleton globale
supabase_manager = SupabaseManager()

# Fonction helper pour compatibilité avec l'ancien code
def get_supabase_client(service: bool = False):
    """
    Retourne le client Supabase approprié
    
    Args:
        service: True pour le client service (admin), False pour standard
    
    Returns:
        Client: Instance du client Supabase
    """
    return supabase_manager.service_client if service else supabase_manager.client
