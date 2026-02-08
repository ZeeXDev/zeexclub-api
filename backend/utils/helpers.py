# backend/utils/helpers.py
"""
Fonctions utilitaires générales
"""

import re
import uuid
from datetime import datetime
from typing import Optional


def generate_uuid() -> str:
    """Génère un UUID v4"""
    return str(uuid.uuid4())


def slugify(text: str) -> str:
    """
    Convertit un texte en slug URL-friendly
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse une durée en format humain (ex: "1h 30min") en secondes
    """
    if not duration_str:
        return None
    
    total_seconds = 0
    
    # Heures
    hours_match = re.search(r'(\d+)\s*h', duration_str, re.IGNORECASE)
    if hours_match:
        total_seconds += int(hours_match.group(1)) * 3600
    
    # Minutes
    minutes_match = re.search(r'(\d+)\s*min', duration_str, re.IGNORECASE)
    if minutes_match:
        total_seconds += int(minutes_match.group(1)) * 60
    
    # Secondes
    seconds_match = re.search(r'(\d+)\s*s', duration_str, re.IGNORECASE)
    if seconds_match:
        total_seconds += int(seconds_match.group(1))
    
    return total_seconds if total_seconds > 0 else None


def format_datetime(dt: Optional[str]) -> str:
    """
    Formate une datetime ISO en format lisible
    """
    if not dt:
        return "Inconnu"
    
    try:
        parsed = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except:
        return dt


def truncate_text(text: Optional[str], max_length: int = 100, suffix: str = "...") -> str:
    """
    Tronque un texte à une longueur maximum
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)].rsplit(' ', 1)[0] + suffix


def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier pour la sécurité
    """
    # Remplacer les caractères dangereux
    dangerous = '<>:"/\\|?*'
    for char in dangerous:
        filename = filename.replace(char, '_')
    
    # Limiter la longueur
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:195] + ext
    
    return filename.strip()


def is_valid_email(email: str) -> bool:
    """
    Vérifie si une adresse email est valide
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def chunk_list(lst, chunk_size):
    """
    Divise une liste en sous-listes de taille définie
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def merge_dicts(base: dict, override: dict) -> dict:
    """
    Fusionne deux dictionnaires (override prend priorité)
    """
    result = base.copy()
    result.update(override)
    return result


def get_client_ip(request) -> str:
    """
    Récupère l'IP client depuis une requête Django
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or 'unknown'
