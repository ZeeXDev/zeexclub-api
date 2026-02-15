/**
 * Client API ZeeXClub
 * Gestion des appels API avec cache et retry
 */

import { API_BASE_URL, APP_CONFIG } from './config.js';

class ZeeXAPI {
    constructor() {
        this.baseURL = API_BASE_URL;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    }

    /**
     * Requête API générique avec retry
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const cacheKey = `${endpoint}${JSON.stringify(options)}`;
        
        // Vérification cache pour GET
        if (options.method === 'GET' || !options.method) {
            const cached = this.getCache(cacheKey);
            if (cached) return cached;
        }

        let lastError;
        
        for (let attempt = 0; attempt < APP_CONFIG.maxRetries; attempt++) {
            try {
                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        ...options.headers
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                
                // Mise en cache pour GET
                if (options.method === 'GET' || !options.method) {
                    this.setCache(cacheKey, data);
                }
                
                return data;
                
            } catch (error) {
                lastError = error;
                console.warn(`Tentative ${attempt + 1} échouée pour ${endpoint}:`, error);
                
                if (attempt < APP_CONFIG.maxRetries - 1) {
                    await this.delay(APP_CONFIG.retryDelay * (attempt + 1));
                }
            }
        }

        throw lastError;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    getCache(key) {
        const item = this.cache.get(key);
        if (item && Date.now() - item.timestamp < this.cacheTimeout) {
            return item.data;
        }
        this.cache.delete(key);
        return null;
    }

    setCache(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
    }

    clearCache() {
        this.cache.clear();
    }

    // =========================================================================
    // ENDPOINTS SHOWS
    // =========================================================================

    /**
     * Liste tous les shows
     */
    async getShows(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/shows${queryString ? '?' + queryString : ''}`;
        return this.request(endpoint);
    }

    /**
     * Recherche de shows
     */
    async searchShows(query, type = null) {
        const params = { q: query };
        if (type) params.type = type;
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/shows/search?${queryString}`);
    }

    /**
     * Détails d'un show
     */
    async getShow(showId) {
        return this.request(`/shows/${showId}`);
    }

    /**
     * Épisodes d'un show
     */
    async getShowEpisodes(showId, season = null) {
        let endpoint = `/shows/${showId}/episodes`;
        if (season) endpoint += `?season=${season}`;
        return this.request(endpoint);
    }

    /**
     * Shows similaires
     */
    async getRelatedShows(showId) {
        return this.request(`/shows/${showId}/related`);
    }

    // =========================================================================
    // ENDPOINTS ÉPISODES
    // =========================================================================

    /**
     * Détails d'un épisode
     */
    async getEpisode(episodeId) {
        return this.request(`/episodes/${episodeId}`);
    }

    /**
     * Sources vidéo d'un épisode
     */
    async getEpisodeSources(episodeId) {
        return this.request(`/episodes/${episodeId}/sources`);
    }

    // =========================================================================
    // ENDPOINTS CATALOGUE
    // =========================================================================

    /**
     * Shows tendance
     */
    async getTrending(type = 'all', timeWindow = 'week') {
        return this.request(`/trending?type=${type}&time_window=${timeWindow}`);
    }

    /**
     * Nouveautés
     */
    async getRecent(type = null) {
        const params = type ? `?type=${type}` : '';
        return this.request(`/recent${params}`);
    }

    /**
     * Liste des genres
     */
    async getGenres() {
        return this.request('/genres');
    }

    // =========================================================================
    // ENDPOINTS TMDB (Proxy)
    // =========================================================================

    /**
     * Recherche TMDB
     */
    async searchTMDB(query, type = 'movie') {
        return this.request(`/tmdb/search?q=${encodeURIComponent(query)}&type=${type}`);
    }

    /**
     * Détails TMDB
     */
    async getTMDBDetails(tmdbId, type = 'movie') {
        return this.request(`/tmdb/${tmdbId}?type=${type}`);
    }

    // =========================================================================
    // UTILITAIRES
    // =========================================================================

    /**
     * Construction URL image TMDB
     */
    getImageUrl(path, size = 'w500') {
        if (!path) return '/img/default-poster.png';
        if (path.startsWith('http')) return path;
        return `https://image.tmdb.org/t/p/${size}${path}`;
    }

    /**
     * Construction URL streaming
     */
    getStreamUrl(source) {
        if (source.server === 'filemoon') {
            return source.embed_url;
        } else if (source.server === 'telegram') {
            return source.direct_link;
        }
        return null;
    }
}

// Instance singleton
const api = new ZeeXAPI();
export default api;

// Export global
window.ZeeXAPI = api;
