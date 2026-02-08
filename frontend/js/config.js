// frontend/js/config.js
/**
 * Configuration globale du frontend ZeeXClub
 */

const CONFIG = {
    // URLs API
    API_BASE_URL: window.location.hostname === 'localhost' 
        ? 'http://localhost:8000/api' 
        : 'https://zeexclub-api.onrender.com/api',
    
    SUPABASE_URL: 'https://votre-projet.supabase.co',
    SUPABASE_ANON_KEY: 'votre-cle-anon',
    
    // Configuration TMDB (public)
    TMDB_IMAGE_BASE_URL: 'https://image.tmdb.org/t/p',
    
    // Paramètres
    DEFAULT_POSTER: '/img/default-poster.png',
    ITEMS_PER_PAGE: 20,
    MAX_COMMENT_LENGTH: 1000,
    
    // Délais
    DEBOUNCE_DELAY: 300,
    TOAST_DURATION: 3000,
    
    // Version
    VERSION: '1.0.0'
};

// Export pour modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}
