// frontend/js/api.js
/**
 * Client API pour communiquer avec le backend ZeeXClub
 */

import CONFIG from './config.js';
import { getAuthToken } from './supabase-client.js';

/**
 * Effectue une requête API avec gestion d'erreurs
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    
    // Headers par défaut
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    // Ajouter token d'authentification si disponible
    const token = await getAuthToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    try {
        const response = await fetch(url, {
            ...options,
            headers
        });
        
        // Gérer les erreurs HTTP
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        // Retourner données JSON ou vide
        return await response.json().catch(() => ({}));
        
    } catch (error) {
        console.error(`❌ API Error (${endpoint}):`, error);
        throw error;
    }
}

// Export des fonctions API

export const api = {
    baseUrl: CONFIG.API_BASE_URL,
    
    // ========== ANCIENS ENDPOINTS (compatibilité) ==========
    getRecentVideos: (limit = 12) => 
        apiRequest(`/videos/recent/?limit=${limit}`),
    
    getVideoDetail: (videoId) => 
        apiRequest(`/videos/${videoId}/`),
    
    searchVideos: (query, filters = {}) => {
        const params = new URLSearchParams({ q: query, ...filters });
        return apiRequest(`/videos/search/?${params}`);
    },
    
    getMovies: (filters = {}) => {
        if (!filters.query) {
            return apiRequest(`/videos/recent/?limit=${filters.limit || 20}`);
        }
        const params = new URLSearchParams(filters);
        return apiRequest(`/videos/search/?${params}`);
    },
    
    getTrending: (limit = 12) => 
        apiRequest(`/videos/trending/?limit=${limit}`),
    
    search: (query, filters = {}) => {
        const params = new URLSearchParams({ q: query, ...filters });
        return apiRequest(`/videos/search/?${params}`);
    },
    
    getAllFolders: () => 
        apiRequest('/folders/'),
    
    getFolderContents: (folderId) => 
        apiRequest(`/folders/${folderId}/`),
    
    // ========== NOUVEAUX ENDPOINTS NETFLIX-STYLE ==========
    
    /**
     * Recherche de séries/films (dossiers) - pas d'épisodes individuels
     */
    searchFolders: (query, filters = {}) => {
        const params = new URLSearchParams({ q: query, ...filters });
        return apiRequest(`/search/?${params}`);
    },
    
    /**
     * Détails d'une série/film avec saisons et épisodes
     */
    getFolderDetails: (folderId) => 
        apiRequest(`/folders/${folderId}/details/`),
    
    /**
     * Détails d'un épisode spécifique avec next/prev
     */
    getEpisodeDetails: (videoId) => 
        apiRequest(`/episodes/${videoId}/`),
    
    // ========== USER (inchangé) ==========
    getWatchHistory: (completed = false) => 
        apiRequest(`/user/history/?completed=${completed}`),
    
    updateWatchProgress: (videoId, progress, completed = false) => 
        apiRequest('/user/history/update/', {
            method: 'POST',
            body: JSON.stringify({ video_id: videoId, progress, completed })
        }),
    
    getWatchlist: () => 
        apiRequest('/user/watchlist/'),
    
    addToWatchlist: (videoId) => 
        apiRequest('/user/watchlist/add/', {
            method: 'POST',
            body: JSON.stringify({ video_id: videoId })
        }),
    
    removeFromWatchlist: (videoId) => 
        apiRequest(`/user/watchlist/${videoId}/`, { method: 'DELETE' }),
    
    addToFavorites: (videoId) => 
        apiRequest('/user/watchlist/add/', {
            method: 'POST',
            body: JSON.stringify({ video_id: videoId, favorite: true })
        }),
    
    removeFromFavorites: (videoId) => 
        apiRequest(`/user/watchlist/${videoId}/`, { method: 'DELETE' }),
    
    // ========== COMMENTAIRES ==========
    getComments: (videoId, limit = 50) => 
        apiRequest(`/comments/${videoId}/?limit=${limit}`),
    
    postComment: (videoId, text) => 
        apiRequest('/comments/post/', {
            method: 'POST',
            body: JSON.stringify({ video_id: videoId, text })
        }),
    
    // ========== TMDB ==========
    enrichFolder: (folderId) => 
        apiRequest(`/tmdb/enrich/${folderId}/`, { method: 'POST' }),
    
    searchTMDB: (query, year) => {
        const params = new URLSearchParams({ q: query });
        if (year) params.append('year', year);
        return apiRequest(`/tmdb/search/?${params}`);
    },
    
    // ========== Health ==========
    healthCheck: () => 
        apiRequest('/health/')
};

export default api;
