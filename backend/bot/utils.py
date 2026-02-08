# backend/bot/utils.py
"""
Fonctions utilitaires pour le bot Telegram
Parsing, formatage, validation
"""

import re
import hashlib
import logging
from typing import Optional, Tuple, List
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# =============================================================================
# PARSING DES CAPTIONS (ÉPISODES/SAISONS)
# =============================================================================

def extract_episode(caption: Optional[str]) -> Optional[int]:
    """
    Extrait le numéro d'épisode depuis une caption
    
    Patterns supportés:
    - E01, E12, E1
    - Ep01, Ep 12, Ep.5, EP 3
    - Épisode 1, Episode 3
    - #01, #1
    - 01, 1 (si précédé de mot-clé épisode)
    
    Args:
        caption: Texte de la caption Telegram
    
    Returns:
        int: Numéro d'épisode ou None
    """
    if not caption:
        return None
    
    caption = caption.strip()
    
    patterns = [
        (r'\bE(\d{1,3})\b', 1),                    # E01, E12
        (r'\bEp\.?\s*(\d{1,3})\b', 1),             # Ep01, Ep 12, Ep.5
        (r'\b[ÉE]pisode\s*(\d{1,3})\b', 1),        # Épisode 1, Episode 3
        (r'\b#(\d{1,3})\b', 1),                    # #01, #12
        (r'S\d{1,2}E(\d{1,3})\b', 1),              # S01E05 (groupe 1 = épisode)
        (r'Saison\s*\d+\s*[ÉE]p\.?\s*(\d{1,3})', 1),  # Saison 1 Ep 5
    ]
    
    for pattern, group in patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            try:
                episode = int(match.group(group))
                if 0 < episode < 1000:  # Validation plage raisonnable
                    return episode
            except (ValueError, IndexError):
                continue
    
    # Pattern fallback: numéro isolé après mot-clé épisode
    fallback = re.search(r'[ÉE]pisode.*?(\d{1,3})', caption, re.IGNORECASE)
    if fallback:
        try:
            return int(fallback.group(1))
        except ValueError:
            pass
    
    return None


def extract_season(caption: Optional[str]) -> Optional[int]:
    """
    Extrait le numéro de saison depuis une caption
    
    Patterns supportés:
    - S01, S2, S12
    - Saison 1, Saison 2
    - Season 1, Season 2
    - S01E05 (extrait S01)
    
    Args:
        caption: Texte de la caption Telegram
    
    Returns:
        int: Numéro de saison ou None
    """
    if not caption:
        return None
    
    caption = caption.strip()
    
    patterns = [
        (r'\bS(\d{1,2})\b', 1),                     # S01, S2
        (r'\bSaison\s*(\d{1,2})\b', 1),             # Saison 1
        (r'\bSeason\s*(\d{1,2})\b', 1),             # Season 2
        (r'\bS(\d{1,2})E\d{1,3}\b', 1),             # S01E05 (groupe 1 = saison)
    ]
    
    for pattern, group in patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            try:
                season = int(match.group(group))
                if 0 < season < 100:  # Validation plage raisonnable
                    return season
            except (ValueError, IndexError):
                continue
    
    return None


def parse_caption(caption: Optional[str]) -> Tuple[Optional[int], Optional[int], str]:
    """
    Parse complet d'une caption pour extraire saison, épisode et titre
    
    Args:
        caption: Texte de la caption
    
    Returns:
        tuple: (season, episode, clean_title)
    """
    season = extract_season(caption)
    episode = extract_episode(caption)
    
    # Nettoyer le titre (enlever les codes épisode/saison)
    clean_title = caption or ""
    
    # Patterns à supprimer pour le titre propre
    patterns_to_remove = [
        r'\bS\d{1,2}E\d{1,3}\b',           # S01E05
        r'\bE\d{1,3}\b',                    # E05
        r'\bEp\.?\s*\d{1,3}\b',             # Ep 5
        r'\b[ÉE]pisode\s*\d{1,3}\b',        # Épisode 5
        r'\bS\d{1,2}\b',                    # S01
        r'\bSaison\s*\d{1,2}\b',           # Saison 1
        r'\b#\d{1,3}\b',                    # #05
    ]
    
    for pattern in patterns_to_remove:
        clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
    
    # Nettoyer les espaces multiples et ponctuation résiduelle
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    clean_title = re.sub(r'^[-–—\s]+|[-–—\s]+$', '', clean_title)
    
    # Si titre vide après nettoyage, générer un titre par défaut
    if not clean_title:
        if season and episode:
            clean_title = f"Saison {season} Épisode {episode}"
        elif episode:
            clean_title = f"Épisode {episode}"
        else:
            clean_title = "Vidéo sans titre"
    
    return season, episode, clean_title


# =============================================================================
# FORMATAGE ET UTILITAIRES
# =============================================================================

def format_file_size(size_bytes: Optional[int]) -> str:
    """
    Formate une taille en bytes en format lisible
    
    Args:
        size_bytes: Taille en bytes
    
    Returns:
        str: Taille formatée (ex: "1.5 GB")
    """
    if not size_bytes or size_bytes < 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    
    return f"{size:.2f} {units[unit_index]}"


def format_duration(seconds: Optional[int]) -> str:
    """
    Formate une durée en secondes en format lisible
    
    Args:
        seconds: Durée en secondes
    
    Returns:
        str: Durée formatée (ex: "1h 30min" ou "45min 30s")
    """
    if not seconds or seconds < 0:
        return "0min"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        if secs > 0:
            return f"{hours}h {minutes}min {secs}s"
        return f"{hours}h {minutes}min"
    
    if secs > 0:
        return f"{minutes}min {secs}s"
    
    return f"{minutes}min"


def generate_stream_id(file_id: str) -> str:
    """
    Génère un ID unique pour le streaming à partir d'un file_id Telegram
    
    Args:
        file_id: file_id Telegram unique
    
    Returns:
        str: Hash MD5 hexadécimal (32 caractères)
    """
    return hashlib.md5(file_id.encode('utf-8')).hexdigest()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Tronque un texte à une longueur maximum
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximum
        suffix: Suffixe à ajouter si tronqué
    
    Returns:
        str: Texte tronqué
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)].rsplit(' ', 1)[0] + suffix


def escape_markdown(text: Optional[str]) -> str:
    """
    Échappe les caractères spéciaux Markdown pour Telegram
    
    Args:
        text: Texte à échapper
    
    Returns:
        str: Texte sécurisé pour Markdown
    """
    if not text:
        return ""
    
    # Caractères à échapper: _ * [ ] ( ) ~ ` > # + - = | { } . !
    chars_to_escape = r'_*[]()~`>#+-=|{}.!'
    
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    
    return text


# =============================================================================
# RECHERCHE FUZZY
# =============================================================================

def fuzzy_search(query: str, choices: List[str], limit: int = 5, cutoff: float = 0.6) -> List[str]:
    """
    Recherche floue dans une liste de choix (tolérance aux fautes)
    
    Args:
        query: Terme recherché
        choices: Liste des choix possibles
        limit: Nombre maximum de résultats
        cutoff: Score minimum de similarité (0-1)
    
    Returns:
        list: Liste des correspondances ordonnées par pertinence
    """
    if not query or not choices:
        return []
    
    query = query.lower().strip()
    
    # Recherche exacte d'abord
    exact_matches = [c for c in choices if c.lower() == query]
    if exact_matches:
        return exact_matches[:limit]
    
    # Recherche contient
    contains_matches = [c for c in choices if query in c.lower()]
    
    # Recherche fuzzy
    fuzzy_matches = get_close_matches(query, [c.lower() for c in choices], n=limit, cutoff=cutoff)
    
    # Combiner et dédupliquer en préservant l'ordre de pertinence
    seen = set()
    results = []
    
    for match_list in [exact_matches, contains_matches, fuzzy_matches]:
        for match in match_list:
            # Retrouver le choix original (case-sensitive)
            original = next((c for c in choices if c.lower() == match), match)
            if original not in seen:
                seen.add(original)
                results.append(original)
                if len(results) >= limit:
                    return results
    
    return results


def find_best_match(query: str, choices: List[str]) -> Optional[Tuple[str, float]]:
    """
    Trouve la meilleure correspondance unique
    
    Args:
        query: Terme recherché
        choices: Liste des choix possibles
    
    Returns:
        tuple: (meilleure_correspondance, score) ou None
    """
    matches = fuzzy_search(query, choices, limit=1, cutoff=0.5)
    if not matches:
        return None
    
    best = matches[0]
    # Calculer un score simple basé sur la longueur commune
    query_lower = query.lower()
    best_lower = best.lower()
    
    # Score de similarité simple
    max_len = max(len(query_lower), len(best_lower))
    if max_len == 0:
        return (best, 1.0)
    
    # Utiliser la distance de Levenshtein simplifiée
    # Pour l'instant, on utilise un score basé sur la correspondance exacte
    if query_lower == best_lower:
        score = 1.0
    elif query_lower in best_lower or best_lower in query_lower:
        score = 0.8
    else:
        score = 0.6  # Score minimum pour fuzzy match
    
    return (best, score)


# =============================================================================
# VALIDATION
# =============================================================================

def is_valid_folder_name(name: str) -> Tuple[bool, str]:
    """
    Valide un nom de dossier
    
    Args:
        name: Nom à valider
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not name:
        return (False, "Le nom ne peut pas être vide")
    
    if len(name) > 100:
        return (False, "Le nom ne doit pas dépasser 100 caractères")
    
    # Caractères interdits pour la sécurité et la compatibilité
    forbidden_chars = r'<>:"/\\|?*'
    for char in forbidden_chars:
        if char in name:
            return (False, f"Caractère interdit: '{char}'")
    
    # Doit contenir au moins un caractère alphanumérique
    if not re.search(r'[a-zA-Z0-9]', name):
        return (False, "Le nom doit contenir au moins une lettre ou un chiffre")
    
    return (True, "")


# backend/bot/utils.py (SUITE ET FIN)
def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier pour la sécurité
    
    Args:
        filename: Nom de fichier original
    
    Returns:
        str: Nom sécurisé
    """
    # Remplacer les caractères dangereux
    dangerous = r'<>:"/\\|?*'
    for char in dangerous:
        filename = filename.replace(char, '_')
    
    # Limiter la longueur
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:195] + ext
    
    return filename.strip()


def parse_folder_path(path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse un chemin de dossier type "Parent/Enfant"
    
    Args:
        path: Chemin complet (ex: "Marvel/Avengers Endgame")
    
    Returns:
        tuple: (parent_name, subfolder_name) ou (folder_name, None) si racine
    """
    if not path:
        return (None, None)
    
    parts = [p.strip() for p in path.split('/') if p.strip()]
    
    if len(parts) == 0:
        return (None, None)
    elif len(parts) == 1:
        return (parts[0], None)
    else:
        return (parts[0], parts[1])


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """
    Divise une liste en sous-listes de taille définie
    
    Args:
        lst: Liste à diviser
        chunk_size: Taille de chaque chunk
    
    Returns:
        list: Liste de chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def format_number(num: int) -> str:
    """
    Formate un grand nombre avec séparateurs (ex: 1,234,567)
    
    Args:
        num: Nombre à formater
    
    Returns:
        str: Nombre formaté
    """
    return f"{num:,}".replace(',', ' ')


# =============================================================================
# GÉNÉRATION DE TEXTES ET MESSAGES
# =============================================================================

def create_video_summary(videos: List[dict]) -> str:
    """
    Crée un résumé textuel d'une liste de vidéos
    
    Args:
        videos: Liste des vidéos
    
    Returns:
        str: Résumé formaté
    """
    if not videos:
        return "Aucune vidéo"
    
    total_size = sum(v.get('file_size', 0) for v in videos)
    total_duration = sum(v.get('duration', 0) for v in videos)
    
    lines = [
        f"📊 **Statistiques:**",
        f"  • Total: **{len(videos)}** vidéos",
        f"  • Taille: **{format_file_size(total_size)}**",
        f"  • Durée: **{format_duration(total_duration)}**",
        f"",
        f"📝 **Liste:**"
    ]
    
    for i, video in enumerate(videos[:20], 1):  # Limiter à 20 pour éviter message trop long
        season = video.get('season_number')
        episode = video.get('episode_number')
        
        if season and episode:
            ep_text = f"S{season:02d}E{episode:02d}"
        elif episode:
            ep_text = f"E{episode:02d}"
        else:
            ep_text = "Film"
        
        title = truncate_text(video.get('title', 'Sans titre'), 40)
        lines.append(f"  {i}. `{ep_text}` {escape_markdown(title)}")
    
    if len(videos) > 20:
        lines.append(f"  ... et {len(videos) - 20} autres")
    
    return "\n".join(lines)


def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """
    Crée une barre de progression ASCII
    
    Args:
        current: Valeur actuelle
        total: Valeur totale
        length: Longueur de la barre
    
    Returns:
        str: Barre de progression
    """
    if total == 0:
        return "□" * length
    
    filled = int(length * current / total)
    bar = "■" * filled + "□" * (length - filled)
    percent = int(100 * current / total)
    
    return f"[{bar}] {percent}%"

