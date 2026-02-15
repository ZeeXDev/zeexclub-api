"""
Validateurs et utilitaires de validation de données
"""

import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from uuid import UUID

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception de validation personnalisée"""
    pass


# ============================================================================
# VALIDATION TMDB & SHOWS
# ============================================================================

def validate_tmdb_id(tmdb_id: Any) -> int:
    """
    Valide un ID TMDB
    
    Args:
        tmdb_id: ID à valider
    
    Returns:
        int: ID validé
    
    Raises:
        ValidationError: Si l'ID est invalide
    """
    try:
        tmdb_id = int(tmdb_id)
        if tmdb_id <= 0:
            raise ValueError("ID doit être positif")
        return tmdb_id
    except (ValueError, TypeError):
        raise ValidationError(f"ID TMDB invalide: {tmdb_id}")


def validate_show_type(show_type: str) -> str:
    """
    Valide le type de show (movie/series)
    
    Args:
        show_type: Type à valider
    
    Returns:
        str: Type validé et normalisé
    
    Raises:
        ValidationError: Si le type est invalide
    """
    valid_types = ['movie', 'series', 'tv']
    normalized = show_type.lower().strip()
    
    if normalized in valid_types:
        return 'series' if normalized == 'tv' else normalized
    
    raise ValidationError(f"Type invalide: {show_type}. Doit être 'movie' ou 'series'")


def validate_season_episode_caption(caption: Optional[str]) -> Dict[str, Any]:
    """
    Parse et valide une caption pour extraire saison/épisode
    
    Args:
        caption: Texte de la caption (ex: "S01E05", "Episode 3", "2x15")
    
    Returns:
        Dict avec season, episode, et raw_text
    
    Raises:
        ValidationError: Si impossible de parser
    """
    if not caption:
        raise ValidationError("Caption vide")
    
    caption = caption.strip()
    
    # Patterns de recherche
    patterns = [
        (r'[Ss](\d+)[Ee](\d+)', True),           # S01E01, s1e1
        (r'(\d+)[xX](\d+)', True),                # 1x01, 2x15
        (r'[Ss]eason\s*(\d+).*?[Ee]pisode\s*(\d+)', True),  # Season 1 Episode 1
        (r'[Ss]aison\s*(\d+).*?[ÉEe]pisode\s*(\d+)', True), # Saison 1 Épisode 1
        (r'[ÉEe]pisode\s*(\d+)', False),         # Épisode 5 (saison 1 par défaut)
        (r'[Ee]p\s*(\d+)', False),               # Ep 5
        (r'^(\d+)$', False),                      # Juste "5"
    ]
    
    for pattern, has_season in patterns:
        match = re.search(pattern, caption)
        if match:
            if has_season:
                return {
                    'season': int(match.group(1)),
                    'episode': int(match.group(2)),
                    'raw_text': caption
                }
            else:
                return {
                    'season': 1,
                    'episode': int(match.group(1)),
                    'raw_text': caption
                }
    
    # Aucun pattern ne correspond
    raise ValidationError(
        f"Impossible de parser la caption: '{caption}'. "
        "Formats acceptés: S01E05, 1x05, Saison 1 Episode 5, Épisode 5"
    )


# ============================================================================
# VALIDATION URLS & LIENS
# ============================================================================

def validate_url(url: str, allowed_schemes: List[str] = None) -> str:
    """
    Valide une URL
    
    Args:
        url: URL à valider
        allowed_schemes: Schémas autorisés (default: http, https)
    
    Returns:
        str: URL validée
    
    Raises:
        ValidationError: Si l'URL est invalide
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL vide ou invalide")
    
    allowed_schemes = allowed_schemes or ['http', 'https']
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            raise ValidationError("URL sans schéma (http/https)")
        
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"Schéma non autorisé: {parsed.scheme}")
        
        if not parsed.netloc:
            raise ValidationError("URL sans domaine")
        
        return url.strip()
        
    except Exception as e:
        raise ValidationError(f"URL invalide: {str(e)}")


def validate_telegram_file_id(file_id: str) -> str:
    """
    Valide un file_id Telegram
    
    Args:
        file_id: ID de fichier Telegram
    
    Returns:
        str: file_id validé
    
    Raises:
        ValidationError: Si invalide
    """
    if not file_id:
        raise ValidationError("File ID vide")
    
    # Les file_id Telegram sont généralement des strings alphanumériques
    # avec des underscores et des tirets, commençant souvent par "AgAA" ou similaire
    
    if len(file_id) < 10:
        raise ValidationError("File ID trop court")
    
    # Vérification caractères autorisés
    if not re.match(r'^[A-Za-z0-9_-]+$', file_id):
        raise ValidationError("File ID contient des caractères invalides")
    
    return file_id


def validate_filemoon_code(code: str) -> str:
    """
    Valide un code Filemoon
    
    Args:
        code: Code Filemoon (ex: "abcd1234")
    
    Returns:
        str: Code validé
    
    Raises:
        ValidationError: Si invalide
    """
    if not code:
        raise ValidationError("Code Filemoon vide")
    
    # Les codes Filemoon sont généralement alphanumériques, 6-12 caractères
    if not re.match(r'^[a-zA-Z0-9]{6,20}$', code):
        raise ValidationError("Format code Filemoon invalide (6-20 caractères alphanumériques)")
    
    return code.lower()


# ============================================================================
# VALIDATION DONNÉES SHOW/EPISODE
# ============================================================================

def validate_show_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide les données de création d'un show
    
    Args:
        data: Dict avec les données du show
    
    Returns:
        Dict: Données nettoyées et validées
    
    Raises:
        ValidationError: Si données invalides
    """
    required = ['tmdb_id', 'title', 'type']
    
    # Vérification champs requis
    for field in required:
        if field not in data or data[field] is None:
            raise ValidationError(f"Champ requis manquant: {field}")
    
    # Validation et nettoyage
    validated = {
        'tmdb_id': validate_tmdb_id(data['tmdb_id']),
        'title': sanitize_text(data['title'], max_length=500, required=True),
        'type': validate_show_type(data['type']),
        'overview': sanitize_text(data.get('overview', ''), max_length=5000),
        'poster_path': sanitize_text(data.get('poster_path', ''), max_length=500),
        'backdrop_path': sanitize_text(data.get('backdrop_path', ''), max_length=500),
        'release_date': validate_date(data.get('release_date')),
        'genres': validate_genres(data.get('genres', [])),
        'runtime': validate_positive_int(data.get('runtime'), allow_none=True),
        'rating': validate_rating(data.get('rating')),
        'language': sanitize_text(data.get('language', 'fr'), max_length=10)
    }
    
    return validated


def validate_episode_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide les données de création d'un épisode
    """
    required = ['season_id', 'episode_number']
    
    for field in required:
        if field not in data or data[field] is None:
            raise ValidationError(f"Champ requis manquant: {field}")
    
    return {
        'season_id': validate_uuid(data['season_id']),
        'episode_number': validate_positive_int(data['episode_number']),
        'title': sanitize_text(data.get('title', ''), max_length=500),
        'overview': sanitize_text(data.get('overview', ''), max_length=2000),
        'thumbnail': sanitize_text(data.get('thumbnail', ''), max_length=500),
        'air_date': validate_date(data.get('air_date')),
        'runtime': validate_positive_int(data.get('runtime'), allow_none=True)
    }


def validate_video_source_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide les données d'une source vidéo
    """
    required = ['episode_id', 'server_name', 'link']
    
    for field in required:
        if field not in data or data[field] is None:
            raise ValidationError(f"Champ requis manquant: {field}")
    
    server = data['server_name'].lower()
    valid_servers = ['filemoon', 'telegram']
    
    if server not in valid_servers:
        raise ValidationError(f"Serveur invalide: {server}")
    
    validated = {
        'episode_id': validate_uuid(data['episode_id']),
        'server_name': server,
        'link': validate_url(data['link']),
        'quality': sanitize_text(data.get('quality', 'HD'), max_length=10),
        'language': sanitize_text(data.get('language', 'FR'), max_length=10),
        'is_active': bool(data.get('is_active', True)),
        'file_size': validate_positive_int(data.get('file_size'), allow_none=True),
        'duration': validate_positive_int(data.get('duration'), allow_none=True)
    }
    
    # Champs spécifiques par serveur
    if server == 'filemoon':
        validated['filemoon_code'] = validate_filemoon_code(
            data.get('filemoon_code') or extract_filemoon_code(data['link'])
        )
    else:
        validated['file_id'] = validate_telegram_file_id(data.get('file_id', ''))
    
    return validated


# ============================================================================
# UTILITAIRES DE NETTOYAGE
# ============================================================================

def sanitize_text(text: Any, max_length: int = 255, required: bool = False) -> Optional[str]:
    """
    Nettoie et valide un texte
    
    Args:
        text: Texte à nettoyer
        max_length: Longueur maximale
        required: Si True, lève une erreur si vide
    
    Returns:
        str: Texte nettoyé ou None
    """
    if text is None:
        if required:
            raise ValidationError("Texte requis")
        return None
    
    text = str(text).strip()
    
    if not text:
        if required:
            raise ValidationError("Texte requis")
        return None
    
    # Suppression des caractères de contrôle
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Troncature si nécessaire
    if len(text) > max_length:
        logger.warning(f"Texte tronqué ({len(text)} > {max_length}): {text[:50]}...")
        text = text[:max_length]
    
    return text


def validate_uuid(uuid_str: Any) -> str:
    """
    Valide un UUID
    """
    if isinstance(uuid_str, UUID):
        return str(uuid_str)
    
    try:
        UUID(str(uuid_str))
        return str(uuid_str)
    except ValueError:
        raise ValidationError(f"UUID invalide: {uuid_str}")


def validate_date(date_str: Optional[str]) -> Optional[str]:
    """
    Valide une date au format YYYY-MM-DD
    """
    if not date_str:
        return None
    
    try:
        # Vérification basique du format
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(date_str)):
            raise ValueError("Format invalide")
        return str(date_str)
    except Exception:
        logger.warning(f"Date invalide ignorée: {date_str}")
        return None


def validate_positive_int(value: Any, allow_none: bool = False) -> Optional[int]:
    """
    Valide un entier positif
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError("Valeur requise")
    
    try:
        num = int(value)
        if num < 0:
            raise ValueError("Doit être positif")
        return num
    except (ValueError, TypeError):
        if allow_none:
            return None
        raise ValidationError(f"Valeur entière positive requise: {value}")


def validate_rating(rating: Any) -> Optional[float]:
    """
    Valide une note (0-10)
    """
    if rating is None:
        return None
    
    try:
        num = float(rating)
        if num < 0 or num > 10:
            raise ValueError("Hors limites")
        return round(num, 1)
    except (ValueError, TypeError):
        return None


def validate_genres(genres: Any) -> List[str]:
    """
    Valide et normalise une liste de genres
    """
    if not genres:
        return []
    
    if isinstance(genres, str):
        # Si string, essayer de parser comme JSON ou liste séparée par virgules
        try:
            import json
            genres = json.loads(genres)
        except:
            genres = [g.strip() for g in genres.split(',') if g.strip()]
    
    if not isinstance(genres, (list, tuple)):
        return []
    
    # Nettoyage
    cleaned = []
    for genre in genres:
        if genre and isinstance(genre, str):
            cleaned.append(sanitize_text(genre, max_length=50))
    
    return list(set(cleaned))  # Déduplication


# ============================================================================
# EXTRACTION & PARSING
# ============================================================================

def extract_filemoon_code(url: str) -> str:
    """
    Extrait le code Filemoon d'une URL
    
    Args:
        url: URL Filemoon (ex: https://filemoon.sx/e/abcd1234)
    
    Returns:
        str: Code extrait
    
    Raises:
        ValidationError: Si impossible d'extraire
    """
    if not url:
        raise ValidationError("URL vide")
    
    # Patterns possibles
    patterns = [
        r'/e/([a-zA-Z0-9]+)',           # /e/abcd1234
        r'filemoon\.sx/e/([a-zA-Z0-9]+)',  # filemoon.sx/e/abcd1234
        r'[?&]file=([a-zA-Z0-9]+)',     # ?file=abcd1234
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1).lower()
    
    # Si l'URL est juste le code
    if re.match(r'^[a-zA-Z0-9]{6,20}$', url):
        return url.lower()
    
    raise ValidationError(f"Impossible d'extraire le code Filemoon de: {url}")


def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier
    """
    if not filename:
        return "unknown"
    
    # Remplacement des caractères invalides
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    
    # Limite de longueur
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:200] + ('.' + ext if ext else '')
    
    return filename or "unknown"


# ============================================================================
# VALIDATION BATCH
# ============================================================================

def validate_batch(items: List[Dict], validator_func) -> Dict[str, Any]:
    """
    Valide un batch d'items avec une fonction de validation
    
    Returns:
        Dict avec 'valid' (liste) et 'errors' (liste)
    """
    valid = []
    errors = []
    
    for idx, item in enumerate(items):
        try:
            validated = validator_func(item)
            valid.append(validated)
        except ValidationError as e:
            errors.append({
                'index': idx,
                'error': str(e),
                'data': item
            })
        except Exception as e:
            errors.append({
                'index': idx,
                'error': f"Erreur inattendue: {str(e)}",
                'data': item
            })
    
    return {
        'valid': valid,
        'errors': errors,
        'total': len(items),
        'success_count': len(valid),
        'error_count': len(errors)
    }
