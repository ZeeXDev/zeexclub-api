# backend/services/tmdb_api.py
"""
Intégration API TMDB (The Movie Database) pour ZeeXClub
Récupération automatique des métadonnées: posters, descriptions, notes, etc.
"""

import os
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p'

@dataclass
class TMDBMedia:
    """Classe représentant un média TMDB"""
    id: int
    title: str
    original_title: str
    overview: str
    poster_path: Optional[str]
    backdrop_path: Optional[str]
    release_date: Optional[str]
    year: Optional[int]
    rating: float
    vote_count: int
    genre_ids: List[int]
    genres: List[str]
    media_type: str  # 'movie' ou 'tv'
    
    @property
    def poster_url(self) -> Optional[str]:
        """URL complète du poster (taille originale)"""
        if self.poster_path:
            return f"{TMDB_IMAGE_BASE_URL}/original{self.poster_path}"
        return None
    
    @property
    def poster_url_small(self) -> Optional[str]:
        """URL du poster (taille réduite)"""
        if self.poster_path:
            return f"{TMDB_IMAGE_BASE_URL}/w342{self.poster_path}"
        return None
    
    @property
    def backdrop_url(self) -> Optional[str]:
        """URL du backdrop (fond)"""
        if self.backdrop_path:
            return f"{TMDB_IMAGE_BASE_URL}/original{self.backdrop_path}"
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour stockage"""
        return {
            'tmdb_id': self.id,
            'title': self.title,
            'original_title': self.original_title,
            'description': self.overview,
            'poster_url': self.poster_url,
            'poster_url_small': self.poster_url_small,
            'backdrop_url': self.backdrop_url,
            'release_date': self.release_date,
            'year': self.year,
            'rating': self.rating,
            'vote_count': self.vote_count,
            'genres': self.genres,
            'media_type': self.media_type
        }


class TMDBClient:
    """
    Client pour l'API TMDB avec cache et gestion de rate limiting
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TMDB_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Any] = {}
        self.last_request_time = 0
        self.min_interval = 0.25  # 4 requêtes par seconde max (respect rate limit)
        
        if not self.api_key:
            logger.warning("⚠️ TMDB_API_KEY non configuré - L'enrichissement sera désactivé")
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json;charset=utf-8'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Effectue une requête à l'API TMDB avec rate limiting
        
        Args:
            endpoint: Endpoint API (ex: '/search/movie')
            params: Paramètres de requête
        
        Returns:
            dict: Réponse JSON ou None en cas d'erreur
        """
        if not self.api_key:
            return None
        
        # Rate limiting
        import time
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        
        url = f"{TMDB_BASE_URL}{endpoint}"
        params = params or {}
        params['api_key'] = self.api_key
        
        try:
            async with self.session.get(url, params=params) as response:
                self.last_request_time = time.time()
                
                if response.status == 429:
                    logger.warning("⚠️ Rate limit TMDB atteint, attente...")
                    await asyncio.sleep(1)
                    return await self._make_request(endpoint, params)
                
                if response.status != 200:
                    logger.error(f"❌ Erreur TMDB {response.status}: {await response.text()}")
                    return None
                
                return await response.json()
                
        except Exception as e:
            logger.error(f"❌ Erreur requête TMDB: {e}")
            return None
    
    async def search_multi(self, query: str, year: Optional[int] = None, page: int = 1) -> List[TMDBMedia]:
        """
        Recherche multi-types (films + séries)
        
        Args:
            query: Terme de recherche
            year: Filtrer par année (optionnel)
            page: Page de résultats
        
        Returns:
            list: Liste des médias trouvés
        """
        params = {
            'query': query,
            'page': page,
            'include_adult': False,
            'language': 'fr-FR'
        }
        
        if year:
            params['year'] = year
        
        data = await self._make_request('/search/multi', params)
        
        if not data or 'results' not in data:
            return []
        
        results = []
        for item in data['results']:
            if item.get('media_type') not in ['movie', 'tv']:
                continue
            
            media = self._parse_media(item)
            if media:
                results.append(media)
        
        return results
    
    async def search_movie(self, query: str, year: Optional[int] = None) -> List[TMDBMedia]:
        """
        Recherche spécifique de films
        
        Args:
            query: Titre du film
            year: Année de sortie (optionnel)
        
        Returns:
            list: Liste des films trouvés
        """
        params = {
            'query': query,
            'include_adult': False,
            'language': 'fr-FR'
        }
        
        if year:
            params['year'] = year
        
        data = await self._make_request('/search/movie', params)
        
        if not data or 'results' not in data:
            return []
        
        return [self._parse_media(item, 'movie') for item in data['results'] if self._parse_media(item, 'movie')]
    
    async def search_tv(self, query: str, year: Optional[int] = None) -> List[TMDBMedia]:
        """
        Recherche spécifique de séries TV
        
        Args:
            query: Nom de la série
            year: Année de première diffusion (optionnel)
        
        Returns:
            list: Liste des séries trouvées
        """
        params = {
            'query': query,
            'include_adult': False,
            'language': 'fr-FR'
        }
        
        if year:
            params['first_air_date_year'] = year
        
        data = await self._make_request('/search/tv', params)
        
        if not data or 'results' not in data:
            return []
        
        return [self._parse_media(item, 'tv') for item in data['results'] if self._parse_media(item, 'tv')]
    
    async def get_movie_details(self, tmdb_id: int) -> Optional[TMDBMedia]:
        """
        Récupère les détails complets d'un film
        
        Args:
            tmdb_id: ID TMDB du film
        
        Returns:
            TMDBMedia: Détails du film ou None
        """
        data = await self._make_request(f'/movie/{tmdb_id}', {'language': 'fr-FR'})
        
        if not data:
            return None
        
        return self._parse_media(data, 'movie')
    
    async def get_tv_details(self, tmdb_id: int) -> Optional[TMDBMedia]:
        """
        Récupère les détails complets d'une série
        
        Args:
            tmdb_id: ID TMDB de la série
        
        Returns:
            TMDBMedia: Détails de la série ou None
        """
        data = await self._make_request(f'/tv/{tmdb_id}', {'language': 'fr-FR'})
        
        if not data:
            return None
        
        return self._parse_media(data, 'tv')
    
    async def get_season_details(self, tv_id: int, season_number: int) -> Optional[Dict]:
        """
        Récupère les détails d'une saison spécifique
        
        Args:
            tv_id: ID de la série
            season_number: Numéro de la saison
        
        Returns:
            dict: Détails de la saison avec épisodes
        """
        return await self._make_request(
            f'/tv/{tv_id}/season/{season_number}',
            {'language': 'fr-FR'}
        )
    
    def _parse_media(self, data: Dict, media_type: Optional[str] = None) -> Optional[TMDBMedia]:
        """
        Parse les données API en objet TMDBMedia
        
        Args:
            data: Données brutes de l'API
            media_type: Type forcé ('movie' ou 'tv')
        
        Returns:
            TMDBMedia: Objet parsé ou None
        """
        try:
            mtype = media_type or data.get('media_type', 'movie')
            
            # Déterminer titre et date selon le type
            if mtype == 'movie':
                title = data.get('title') or data.get('name', 'Inconnu')
                original_title = data.get('original_title', '')
                release_date = data.get('release_date')
            else:
                title = data.get('name') or data.get('title', 'Inconnu')
                original_title = data.get('original_original_name', '')
                release_date = data.get('first_air_date')
            
            # Extraire l'année
            year = None
            if release_date and len(release_date) >= 4:
                try:
                    year = int(release_date[:4])
                except ValueError:
                    pass
            
            # Récupérer les noms de genres
            genres = []
            if 'genres' in data:
                genres = [g['name'] for g in data['genres']]
            elif 'genre_ids' in data:
                # Mapping des IDs de genres communs
                genre_map = {
                    28: 'Action', 12: 'Aventure', 16: 'Animation', 35: 'Comédie',
                    80: 'Crime', 99: 'Documentaire', 18: 'Drame', 10751: 'Familial',
                    14: 'Fantastique', 36: 'Histoire', 27: 'Horreur', 10402: 'Musique',
                    9648: 'Mystère', 10749: 'Romance', 878: 'Science-Fiction',
                    10770: 'Téléfilm', 53: 'Thriller', 10752: 'Guerre', 37: 'Western',
                    # Genres TV
                    10759: 'Action & Aventure', 10762: 'Enfants', 10763: 'Actualités',
                    10764: 'Réalité', 10765: 'Science-Fiction & Fantastique',
                    10766: 'Feuilleton', 10767: 'Talk', 10768: 'Guerre & Politique'
                }
                genres = [genre_map.get(gid, 'Inconnu') for gid in data.get('genre_ids', [])]
            
            return TMDBMedia(
                id=data.get('id'),
                title=title,
                original_title=original_title,
                overview=data.get('overview', 'Aucune description disponible'),
                poster_path=data.get('poster_path'),
                backdrop_path=data.get('backdrop_path'),
                release_date=release_date,
                year=year,
                rating=data.get('vote_average', 0),
                vote_count=data.get('vote_count', 0),
                genre_ids=data.get('genre_ids', []),
                genres=genres,
                media_type=mtype
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing média TMDB: {e}")
            return None
    
    async def find_best_match(self, title: str, year: Optional[int] = None, 
                              media_type: Optional[str] = None) -> Optional[TMDBMedia]:
        """
        Trouve la meilleure correspondance pour un titre
        
        Args:
            title: Titre recherché
            year: Année (optionnel)
            media_type: 'movie' ou 'tv' pour forcer le type
        
        Returns:
            TMDBMedia: Meilleure correspondance ou None
        """
        if media_type == 'movie':
            results = await self.search_movie(title, year)
        elif media_type == 'tv':
            results = await self.search_tv(title, year)
        else:
            results = await self.search_multi(title, year)
        
        if not results:
            return None
        
        # Scoring pour trouver la meilleure correspondance
        best_score = 0
        best_match = None
        
        title_lower = title.lower()
        
        for media in results:
            score = 0
            
            # Correspondance exacte du titre
            if media.title.lower() == title_lower:
                score += 100
            elif media.title.lower() in title_lower or title_lower in media.title.lower():
                score += 50
            
            # Correspondance titre original
            if media.original_title.lower() == title_lower:
                score += 80
            
            # Bonus année exacte
            if year and media.year == year:
                score += 30
            
            # Bonus popularité (nombre de votes)
            score += min(media.vote_count / 1000, 20)  # Max 20 points
            
            if score > best_score:
                best_score = score
                best_match = media
        
        return best_match


class TMDBEnricher:
    """
    Enrichisseur automatique de métadonnées pour ZeeXClub
    Intègre TMDB avec la base de données Supabase
    """
    
    def __init__(self):
        self.tmdb = None
    
    async def __aenter__(self):
        self.tmdb = await TMDBClient().__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.tmdb:
            await self.tmdb.__aexit__(exc_type, exc_val, exc_tb)
    
    async def enrich_folder(self, folder_id: str, force_update: bool = False) -> Dict[str, Any]:
        """
        Enrichit un dossier entier avec les données TMDB
        
        Args:
            folder_id: ID du dossier Supabase
            force_update: Forcer la mise à jour même si déjà enrichi
        
        Returns:
            dict: Résultat de l'enrichissement
        """
        from database.supabase_client import supabase_manager
        
        # Récupérer le dossier
        folder = supabase_manager.get_folder_by_id(folder_id)
        if not folder:
            return {'success': False, 'error': 'Dossier introuvable'}
        
        folder_name = folder['folder_name']
        
        # Détecter si c'est une série (présence de sous-dossiers type "Saison X")
        subfolders = supabase_manager.get_subfolders(folder_id)
        is_tv = any('saison' in s['folder_name'].lower() or 
                   'season' in s['folder_name'].lower() or
                   any(char.isdigit() for char in s['folder_name'])
                   for s in subfolders[:3]) if subfolders else False
        
        # Rechercher sur TMDB
        media_type = 'tv' if is_tv else None  # Auto-détect si film
        match = await self.tmdb.find_best_match(folder_name, media_type=media_type)
        
        if not match:
            # Essayer sans indication de type
            match = await self.tmdb.find_best_match(folder_name)
        
        if not match:
            return {
                'success': False,
                'error': f'Aucune correspondance trouvée pour "{folder_name}"',
                'suggestions': []
            }
        
        # Mettre à jour le dossier avec les données TMDB
        updates = {
            'tmdb_id': match.id,
            'title': match.title,
            'description': match.overview,
            'poster_url': match.poster_url,
            'poster_url_small': match.poster_url_small,
            'backdrop_url': match.backdrop_url,
            'year': match.year,
            'rating': match.rating,
            'genres': match.genres,
            'media_type': match.media_type,
            'tmdb_updated_at': datetime.utcnow().isoformat()
        }
        
        try:
            supabase_manager.update_folder(folder_id, updates)
            
            # Si c'est une série, enrichir aussi les saisons/épisodes si possible
            if match.media_type == 'tv' and subfolders:
                await self._enrich_seasons(folder_id, match.id, subfolders)
            
            return {
                'success': True,
                'data': match.to_dict(),
                'folder_updated': True
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour dossier {folder_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _enrich_seasons(self, folder_id: str, tmdb_id: int, subfolders: List[Dict]):
        """
        Enrichit les sous-dossiers (saisons) avec les données épisodes
        
        Args:
            folder_id: ID du dossier parent
            tmdb_id: ID TMDB de la série
            subfolders: Liste des sous-dossiers (saisons)
        """
        import re
        
        for subfolder in subfolders:
            # Extraire numéro de saison du nom
            season_match = re.search(r'saison\s*(\d+)|season\s*(\d+)|s(\d+)|(\d+)', 
                                    subfolder['folder_name'], re.IGNORECASE)
            
            if not season_match:
                continue
            
            season_num = int(next(g for g in season_match.groups() if g is not None))
            
            # Récupérer détails de la saison
            season_data = await self.tmdb.get_season_details(tmdb_id, season_num)
            
            if not season_data:
                continue
            
            # Mettre à jour le sous-dossier
            season_updates = {
                'tmdb_season_id': season_data.get('id'),
                'season_number': season_num,
                'season_overview': season_data.get('overview', ''),
                'season_poster': f"{TMDB_IMAGE_BASE_URL}/original{season_data['poster_path']}" if season_data.get('poster_path') else None,
                'episode_count': len(season_data.get('episodes', []))
            }
            
            try:
                supabase_manager.update_folder(subfolder['id'], season_updates)
                
                # Enrichir aussi les vidéos individuelles si elles correspondent aux épisodes
                await self._enrich_episodes(subfolder['id'], season_data.get('episodes', []))
                
            except Exception as e:
                logger.error(f"❌ Erreur mise à jour saison {season_num}: {e}")
    
    async def _enrich_episodes(self, folder_id: str, episodes_data: List[Dict]):
        """
        Enrichit les vidéos individuelles avec les données épisodes TMDB
        
        Args:
            folder_id: ID du dossier (saison)
            episodes_data: Liste des épisodes depuis TMDB
        """
        from database.supabase_client import supabase_manager
        
        # Récupérer les vidéos existantes
        videos = supabase_manager.get_videos_by_folder(folder_id)
        
        for video in videos:
            ep_num = video.get('episode_number')
            if not ep_num:
                continue
            
            # Trouver l'épisode correspondant dans les données TMDB
            tmdb_ep = next((ep for ep in episodes_data if ep.get('episode_number') == ep_num), None)
            
            if not tmdb_ep:
                continue
            
            # Mettre à jour la vidéo
            updates = {
                'title': tmdb_ep.get('name', video['title']),
                'description': tmdb_ep.get('overview', ''),
                'still_path': f"{TMDB_IMAGE_BASE_URL}/original{tmdb_ep['still_path']}" if tmdb_ep.get('still_path') else None,
                'tmdb_episode_id': tmdb_ep.get('id'),
                'air_date': tmdb_ep.get('air_date')
            }
            
            try:
                supabase_manager.update_video(video['id'], updates)
            except Exception as e:
                logger.error(f"❌ Erreur mise à jour épisode {ep_num}: {e}")
    
    async def batch_enrich(self, limit: int = 10) -> Dict[str, Any]:
        """
        Enrichit automatiquement les dossiers sans données TMDB
        
        Args:
            limit: Nombre maximum de dossiers à traiter
        
        Returns:
            dict: Statistiques du batch
        """
        from database.supabase_client import supabase_manager
        
        # Récupérer les dossiers sans tmdb_id
        # Note: Cette requête nécessite un index sur tmdb_id
        folders = supabase_manager.service_client.table('folders').select('*').is_('tmdb_id', 'null').limit(limit).execute()
        
        if not folders.data:
            return {'processed': 0, 'success': 0, 'failed': 0, 'details': []}
        
        results = {
            'processed': len(folders.data),
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        for folder in folders.data:
            try:
                result = await self.enrich_folder(folder['id'])
                
                if result['success']:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                
                results['details'].append({
                    'folder_id': folder['id'],
                    'folder_name': folder['folder_name'],
                    'result': result
                })
                
                # Petite pause pour respecter le rate limit
                await asyncio.sleep(0.5)
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'folder_id': folder['id'],
                    'folder_name': folder['folder_name'],
                    'error': str(e)
                })
        
        return results


# Fonctions utilitaires pour utilisation facile

async def enrich_folder_async(folder_id: str) -> Dict[str, Any]:
    """
    Enrichit un dossier de manière asynchrone (fonction utilitaire)
    
    Args:
        folder_id: ID du dossier à enrichir
    
    Returns:
        dict: Résultat de l'opération
    """
    async with TMDBEnricher() as enricher:
        return await enricher.enrich_folder(folder_id)


def enrich_folder_sync(folder_id: str) -> Dict[str, Any]:
    """
    Version synchrone pour appels depuis code non-async
    
    Args:
        folder_id: ID du dossier à enrichir
    
    Returns:
        dict: Résultat de l'opération
    """
    return asyncio.run(enrich_folder_async(folder_id))


async def search_and_suggest(title: str, year: Optional[int] = None) -> List[Dict]:
    """
    Recherche un titre et retourne les suggestions pour l'admin
    
    Args:
        title: Titre recherché
        year: Année (optionnel)
    
    Returns:
        list: Liste des suggestions formatées
    """
    async with TMDBClient() as tmdb:
        results = await tmdb.search_multi(title, year)
        return [r.to_dict() for r in results[:10]]  # Top 10 résultats
