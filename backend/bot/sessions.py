# backend/bot/sessions.py
"""
Gestionnaire de sessions utilisateurs pour le bot
Stocke l'état temporaire des conversations (mode ajout, sélection, etc.)
"""

import time
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Gère les sessions utilisateurs avec expiration automatique
    Chaque session stocke l'état actuel de l'interaction avec le bot
    """
    
    def __init__(self, expiry_seconds: int = 3600):
        """
        Args:
            expiry_seconds: Durée de vie d'une session en secondes (défaut: 1 heure)
        """
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.expiry_seconds = expiry_seconds
        self._last_cleanup = time.time()
    
    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère la session d'un utilisateur
        
        Args:
            user_id: ID Telegram de l'utilisateur
        
        Returns:
            dict: Données de session ou None si inexistant/expiré
        """
        self._cleanup_expired()
        
        if user_id not in self.sessions:
            return None
        
        session = self.sessions[user_id]
        
        # Vérifier expiration
        if time.time() - session.get('created_at', 0) > self.expiry_seconds:
            del self.sessions[user_id]
            return None
        
        # Mettre à jour last_access
        session['last_access'] = time.time()
        return session
    
    def set(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crée ou met à jour une session
        
        Args:
            user_id: ID Telegram de l'utilisateur
            data: Données à stocker
        
        Returns:
            dict: Session complète avec métadonnées
        """
        session = {
            'user_id': user_id,
            'created_at': time.time(),
            'last_access': time.time(),
            **data
        }
        
        self.sessions[user_id] = session
        logger.info(f"✅ Session créée pour user {user_id}: {data.get('mode', 'unknown')}")
        return session
    
    def update(self, user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Met à jour des champs spécifiques d'une session existante
        
        Args:
            user_id: ID Telegram de l'utilisateur
            updates: Champs à mettre à jour
        
        Returns:
            dict: Session mise à jour ou None si inexistante
        """
        session = self.get(user_id)
        if not session:
            return None
        
        session.update(updates)
        session['last_access'] = time.time()
        self.sessions[user_id] = session
        return session
    
    def delete(self, user_id: int) -> bool:
        """
        Supprime une session
        
        Args:
            user_id: ID Telegram de l'utilisateur
        
        Returns:
            bool: True si supprimée, False si inexistante
        """
        if user_id in self.sessions:
            del self.sessions[user_id]
            logger.info(f"🗑️ Session supprimée pour user {user_id}")
            return True
        return False
    
    def clear_all(self) -> int:
        """
        Supprime toutes les sessions (utile pour maintenance)
        
        Returns:
            int: Nombre de sessions supprimées
        """
        count = len(self.sessions)
        self.sessions.clear()
        logger.info(f"🗑️ {count} sessions supprimées (clear_all)")
        return count
    
    def _cleanup_expired(self):
        """Nettoie les sessions expirées (appelé automatiquement)"""
        now = time.time()
        
        # Nettoyer toutes les 5 minutes maximum
        if now - self._last_cleanup < 300:
            return
        
        expired = [
            uid for uid, session in self.sessions.items()
            if now - session.get('created_at', 0) > self.expiry_seconds
        ]
        
        for uid in expired:
            del self.sessions[uid]
        
        if expired:
            logger.info(f"🧹 {len(expired)} sessions expirées nettoyées")
        
        self._last_cleanup = now
    
    def get_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques des sessions
        
        Returns:
            dict: Nombre total, actives, par mode
        """
        self._cleanup_expired()
        
        stats = {
            'total': len(self.sessions),
            'adding_files': 0,
            'creating_subfolder': 0,
            'selecting_parent': 0,
            'other': 0
        }
        
        for session in self.sessions.values():
            mode = session.get('mode', 'unknown')
            if mode in stats:
                stats[mode] += 1
            else:
                stats['other'] += 1
        
        return stats


# Instance globale pour import facile
session_manager = SessionManager()
