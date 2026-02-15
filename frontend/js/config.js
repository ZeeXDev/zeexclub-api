/**
 * Configuration globale ZeeXClub Frontend
 */

// Détection environnement
const isProduction = window.location.hostname !== 'localhost' && 
                     !window.location.hostname.includes('127.0.0.1');

// URLs API
const API_BASE_URL = isProduction 
    ? 'https://zeexclub.onrender.com/api'  // Remplacer par votre URL Render
    : 'http://zeexclub.onrender.com/api';

// Configuration Supabase (lecture seule pour le frontend)
const SUPABASE_CONFIG = {
    url: 'https://hxdtaqnfnpzqndhqiopi.supabase.co',  // Remplacer
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh4ZHRhcW5mbnB6cW5kaHFpb3BpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1NzE5MDIsImV4cCI6MjA4NjE0NzkwMn0.HbvHp5WRt1AmbKB1FuGixXTjzPAQChIxQhEVOIaa_Ws'  // Remplacer par clé anon (pas la service key!)
};

// Configuration App
const APP_CONFIG = {
    name: 'ZeeXClub',
    version: '1.0.0',
    defaultLanguage: 'fr',
    itemsPerPage: 20,
    maxRetries: 3,
    retryDelay: 1000,
    
    // TMDB Images
    tmdbImageBase: 'https://image.tmdb.org/t/p/',
    posterSize: 'w500',
    backdropSize: 'original',
    thumbnailSize: 'w300',
    
    // Player
    defaultServer: 'filemoon',
    autoplay: false,
    preload: 'metadata'
};

// Export pour modules
export { API_BASE_URL, SUPABASE_CONFIG, APP_CONFIG };

// Export global pour scripts non-modules
window.ZeeXConfig = { API_BASE_URL, SUPABASE_CONFIG, APP_CONFIG };
