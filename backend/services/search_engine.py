# backend/services/search_engine.py
"""
Moteur de recherche avancé pour ZeeXClub
Recherche fuzzy, full-text et filtrage
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from difflib import get_close_matches, SequenceMatcher
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SearchField(Enum):
    """Champs de recherche disponibles"""
    TITLE = 'title'
    DESCRIPTION = 'description'
    GENRE = 'genre'
    ACTOR = 'actor'
    DIRECTOR = 'director'
    YEAR = 'year'


@dataclass
class SearchResult:
    """Résultat de recherche avec score"""
    item: Dict[str, Any]
    score: float
    matched_fields: List[str]
    highlights: Dict[str, str]


class SearchEngine:
    """
    Moteur de recherche multi-stratégie
    Combine recherche exacte, fuzzy et full-text
    """
    
    def __init__(self):
        self.min_score = 0.3  # Score minimum pour considérer un match
    
    def search(
        self,
        query: str,
        items: List[Dict[str, Any]],
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """
        Recherche dans une liste d'items
        
        Args:
            query: Terme de recherche
            items: Liste d'items à chercher
            fields: Champs à indexer (défaut: title, description)
            filters: Filtres additionnels
            limit: Nombre max de résultats
        
        Returns:
            list: Résultats triés par pertinence
        """
        if not query or not items:
            return []
        
        fields = fields or ['title', 'description']
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        
        results = []
        
        for item in items:
            # Appliquer filtres d'abord
            if filters and not self._apply_filters(item, filters):
                continue
            
            # Calculer score de pertinence
            score, matched_fields, highlights = self._calculate_score(
                item, query_lower, query_words, fields
            )
            
            if score >= self.min_score:
                results.append(SearchResult(
                    item=item,
                    score=score,
                    matched_fields=matched_fields,
                    highlights=highlights
                ))
        
        # Trier par score décroissant
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:limit]
    
    def _apply_filters(self, item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Applique les filtres à un item"""
        for key, value in filters.items():
            if value is None:
                continue
            
            item_value = item.get(key)
            
            if key in ['year', 'rating', 'duration']:
                # Filtres numériques
                if isinstance(value, dict):
                    # Range filter: {'min': x, 'max': y}
                    min_val = value.get('min', float('-inf'))
                    max_val = value.get('max', float('inf'))
                    if not (min_val <= (item_value or 0) <= max_val):
                        return False
                else:
                    # Valeur exacte ou minimum
                    if isinstance(value, (int, float)):
                        if (item_value or 0) < value:
                            return False
            
            elif key == 'genre':
                # Filtre genre (liste)
                if isinstance(value, list):
                    item_genres = item.get('genre', []) or []
                    if not any(g in item_genres for g in value):
                        return False
                else:
                    if value not in (item.get('genre', []) or []):
                        return False
            
            elif key == 'type':
                # Film vs Série
                is_series = bool(item.get('episode_number') or item.get('season_number'))
                if value == 'series' and not is_series:
                    return False
                if value == 'movie' and is_series:
                    return False
            
            else:
                # Filtre texte exact
                if str(item_value).lower() != str(value).lower():
                    return False
        
        return True
    
    def _calculate_score(
        self,
        item: Dict[str, Any],
        query: str,
        query_words: List[str],
        fields: List[str]
    ) -> Tuple[float, List[str], Dict[str, str]]:
        """
        Calcule le score de pertinence d'un item
        
        Returns:
            tuple: (score, champs_matchés, highlights)
        """
        scores = []
        matched_fields = []
        highlights = {}
        
        for field in fields:
            value = str(item.get(field, '')).lower()
            if not value:
                continue
            
            field_score = 0
            highlights[field] = value
            
            # 1. Match exact (boost important)
            if query == value:
                field_score = 1.0
                matched_fields.append(f"{field}:exact")
                highlights[field] = self._highlight_match(value, query)
            
            # 2. Début de chaîne
            elif value.startswith(query):
                field_score = 0.9
                matched_fields.append(f"{field}:start")
                highlights[field] = self._highlight_match(value, query)
            
            # 3. Contient la query complète
            elif query in value:
                field_score = 0.8
                matched_fields.append(f"{field}:contains")
                highlights[field] = self._highlight_match(value, query)
            
            # 4. Tous les mots présents
            elif all(word in value for word in query_words):
                field_score = 0.6
                matched_fields.append(f"{field}:words")
                highlights[field] = self._highlight_words(value, query_words)
            
            # 5. Fuzzy match
            else:
                fuzzy_score = self._fuzzy_score(query, value)
                if fuzzy_score > 0.6:
                    field_score = fuzzy_score * 0.5
                    matched_fields.append(f"{field}:fuzzy")
            
            # Boost pour le titre
            if field == 'title':
                field_score *= 1.5
            
            scores.append(field_score)
        
        # Score final: max des scores avec bonus si plusieurs champs matchent
        final_score = max(scores) if scores else 0
        if len(matched_fields) > 1:
            final_score *= 1.1
        
        return min(final_score, 1.0), matched_fields, highlights
    
    def _fuzzy_score(self, query: str, text: str) -> float:
        """Calcule un score de similarité fuzzy"""
        # Ratio de similarité
        ratio = SequenceMatcher(None, query, text).ratio()
        
        # Bonus pour mots individuels
        query_words = query.split()
        word_matches = sum(
            1 for word in query_words 
            if any(SequenceMatcher(None, word, tw).ratio() > 0.8 for tw in text.split())
        )
        word_bonus = (word_matches / len(query_words)) * 0.3 if query_words else 0
        
        return min(ratio + word_bonus, 1.0)
    
    def _highlight_match(self, text: str, query: str) -> str:
        """Met en évidence le match dans le texte"""
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return pattern.sub(r'<mark>\g<0></mark>', text)
    
    def _highlight_words(self, text: str, words: List[str]) -> str:
        """Met en évidence plusieurs mots"""
        result = text
        for word in words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub(r'<mark>\g<0></mark>', result)
        return result
    
    def suggest(
        self,
        partial: str,
        items: List[Dict[str, Any]],
        field: str = 'title',
        limit: int = 5
    ) -> List[str]:
        """
        Suggère des complétions basées sur une entrée partielle
        
        Args:
            partial: Texte partiel entré
            items: Liste d'items
            field: Champ à utiliser pour les suggestions
            limit: Nombre de suggestions
        
        Returns:
            list: Suggestions triées par pertinence
        """
        if not partial or len(partial) < 2:
            return []
        
        # Extraire tous les titres uniques
        titles = list(set(
            str(item.get(field, '')) 
            for item in items 
            if item.get(field)
        ))
        
        # Recherche fuzzy
        matches = get_close_matches(
            partial.lower(),
            [t.lower() for t in titles],
            n=limit,
            cutoff=0.4
        )
        
        # Retourner les titres originaux (avec casse)
        result = []
        for match in matches:
            original = next(
                (t for t in titles if t.lower() == match),
                match
            )
            result.append(original)
        
        # Ajouter les titres qui commencent par le texte
        starts_with = [
            t for t in titles 
            if t.lower().startswith(partial.lower()) and t not in result
        ]
        
        return (result + starts_with)[:limit]
    
    def advanced_search(
        self,
        query: str,
        items: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Recherche avancée avec support de syntaxe de requête
        
        Syntaxe supportée:
        - "mot exact" : recherche phrase exacte
        - genre:action : filtre par genre
        - year:2023 : filtre par année
        - rating>8 : filtre par note
        """
        # Parser la requête
        filters = {}
        search_terms = []
        
        # Pattern pour filtres: champ:valeur
        filter_pattern = r'(\w+):([^\s]+)'
        filter_matches = re.findall(filter_pattern, query)
        
        for field, value in filter_matches:
            if field in ['year', 'rating', 'duration']:
                # Parse les opérateurs
                if value.startswith('>'):
                    filters[field] = {'min': float(value[1:])}
                elif value.startswith('<'):
                    filters[field] = {'max': float(value[1:])}
                else:
                    filters[field] = float(value)
            else:
                filters[field] = value
        
        # Extraire les termes de recherche (hors filtres)
        clean_query = re.sub(filter_pattern, '', query).strip()
        
        # Gérer les guillemets pour phrases exactes
        exact_phrases = re.findall(r'"([^"]+)"', clean_query)
        for phrase in exact_phrases:
            search_terms.append(phrase)
        
        # Mots restants
        remaining = re.sub(r'"[^"]+"', '', clean_query).strip()
        if remaining:
            search_terms.extend(remaining.split())
        
        final_query = ' '.join(search_terms) if search_terms else clean_query
        
        return self.search(final_query, items, filters=filters)


# Instance globale
search_engine = SearchEngine()


def quick_search(
    query: str,
    items: List[Dict[str, Any]],
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Fonction utilitaire de recherche rapide
    
    Returns:
        list: Items matchés (sans métadonnées de score)
    """
    results = search_engine.search(query, items, **kwargs)
    return [r.item for r in results]
