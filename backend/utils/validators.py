# backend/utils/validators.py
"""
Validateurs de données pour ZeeXClub
"""

import re
from typing import Tuple, List


def validate_video_file(filename: str) -> Tuple[bool, str]:
    """
    Valide qu'un fichier est bien une vidéo supportée
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not filename:
        return (False, "Nom de fichier vide")
    
    # Extensions supportées
    valid_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv'}
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    if f'.{ext}' not in valid_extensions:
        return (False, f"Format non supporté. Utilisez: {', '.join(valid_extensions)}")
    
    return (True, "")


def validate_folder_name(name: str) -> Tuple[bool, str]:
    """
    Valide un nom de dossier
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not name or not name.strip():
        return (False, "Le nom ne peut pas être vide")
    
    name = name.strip()
    
    if len(name) > 100:
        return (False, "Le nom ne doit pas dépasser 100 caractères")
    
    if len(name) < 2:
        return (False, "Le nom doit faire au moins 2 caractères")
    
    # Caractères interdits
    forbidden = r'<>:"/\\|?*'
    for char in forbidden:
        if char in name:
            return (False, f"Caractère interdit: '{char}'")
    
    # Doit contenir au moins un alphanumérique
    if not re.search(r'[a-zA-Z0-9]', name):
        return (False, "Le nom doit contenir au moins une lettre ou un chiffre")
    
    # Pas de nom réservé
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    
    if name.upper() in reserved:
        return (False, "Nom réservé par le système")
    
    return (True, "")


def validate_caption(caption: str) -> Tuple[bool, List[str], str]:
    """
    Valide et analyse une caption de vidéo
    
    Returns:
        tuple: (is_valid, warnings, clean_caption)
    """
    if not caption:
        return (True, ["Aucune caption détectée"], "")
    
    warnings = []
    clean = caption.strip()
    
    # Vérifier patterns épisode
    has_episode = bool(re.search(r'[eE][pP]?\s*\d+|[eE]pisode\s*\d+|[sS]\d+[eE]\d+', clean))
    
    if not has_episode:
        warnings.append("Aucun numéro d'épisode détecté dans la caption")
    
    # Vérifier longueur
    if len(clean) > 200:
        warnings.append("Caption très longue, sera tronquée")
        clean = clean[:200]
    
    # Détecter qualité
    qualities = re.findall(r'\b(480p|720p|1080p|2160p|4K|HDR|BluRay|WEB-DL)\b', clean, re.IGNORECASE)
    if qualities:
        warnings.append(f"Qualité détectée: {', '.join(qualities)}")
    
    return (True, warnings, clean)


def validate_stream_id(stream_id: str) -> bool:
    """
    Valide un ID de stream (doit être un hash MD5 valide)
    """
    if not stream_id or len(stream_id) != 32:
        return False
    
    try:
        int(stream_id, 16)
        return True
    except ValueError:
        return False


def validate_tmdb_id(tmdb_id: str) -> bool:
    """
    Valide un ID TMDB (numérique positif)
    """
    if not tmdb_id:
        return False
    
    try:
        id_int = int(tmdb_id)
        return id_int > 0
    except ValueError:
        return False


def sanitize_comment(text: str) -> Tuple[str, List[str]]:
    """
    Nettoie et valide un commentaire utilisateur
    
    Returns:
        tuple: (clean_text, violations)
    """
    violations = []
    
    if not text:
        return ("", ["Commentaire vide"])
    
    # Nettoyer
    clean = text.strip()
    
    # Vérifier longueur
    if len(clean) > 1000:
        clean = clean[:1000]
        violations.append("Commentaire tronqué (max 1000 caractères)")
    
    if len(clean) < 3:
        violations.append("Commentaire trop court")
    
    # Détecter spam/mots interdits
    spam_patterns = [
        r'(https?://\S+)',  # URLs
        r'(\b\d{10,}\b)',   # Numéros de téléphone
    ]
    
    for pattern in spam_patterns:
        if re.search(pattern, clean):
            violations.append("Liens externes détectés et supprimés")
            clean = re.sub(pattern, '[lien supprimé]', clean)
    
    # Normaliser les sauts de ligne
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    
    return (clean, violations)
