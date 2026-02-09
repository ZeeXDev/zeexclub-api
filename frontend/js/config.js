// frontend/js/config.js
/**
 * Configuration globale du frontend ZeeXClub
 */

const CONFIG = {
    // URLs API - ✅ CORRECTION: Détection plus robuste de l'environnement
    API_BASE_URL: (() => {
        // En local (localhost ou IP locale)
        if (window.location.hostname === 'localhost' || 
            window.location.hostname === '127.0.0.1' ||
            window.location.hostname.startsWith('192.168.') ||
            window.location.hostname.startsWith('10.')) {
            return 'http://localhost:8000/api';
        }
        // Production (Vercel, Netlify, etc.)
        return 'https://zeexclub-api.onrender.com/api';
    })(),
    
    // ✅ CORRECTION: Clés Supabase depuis les variables d'environnement ou valeurs par défaut
    // En production, ces valeurs devraient être injectées par le build ou le serveur
    SUPABASE_URL: window.__ENV__?.SUPABASE_URL || 'https://hxdtaqnfnpzqndhqiopi.supabase.co',
    SUPABASE_ANON_KEY: window.__ENV__?.SUPABASE_ANON_KEY || 'sb_publishable_LKwjDQ-9Oy9gvpO29YWlCg_vsY7xuyW',
    
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

// ✅ CORRECTION: Export ES module standard pour le frontend
export default CONFIG;

// Export nommé pour compatibilité
export { CONFIG };

// Pour compatibilité avec les scripts non-module (rare mais possible)
if (typeof window !== 'undefined') {
    window.ZEEX_CONFIG = CONFIG;
}
