// frontend/js/supabase-client.js
/**
 * Client Supabase initialisé pour ZeeXClub
 */

import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
import CONFIG from './config.js';

// Initialisation du client Supabase
const supabase = createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY, {
    auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true
    }
});

// Gestion des états d'authentification
let currentUser = null;
let authListeners = [];

/**
 * S'abonner aux changements d'authentification
 * @param {Function} callback - Fonction appelée lors des changements
 */
export function onAuthStateChange(callback) {
    authListeners.push(callback);
    
    // Appel immédiat si déjà connecté
    if (currentUser) {
        callback('SIGNED_IN', currentUser);
    }
    
    // Retourner fonction de désabonnement
    return () => {
        authListeners = authListeners.filter(cb => cb !== callback);
    };
}

/**
 * Notifie tous les listeners d'un changement d'état
 */
function notifyAuthListeners(event, user) {
    authListeners.forEach(callback => {
        try {
            callback(event, user);
        } catch (e) {
            console.error('Erreur listener auth:', e);
        }
    });
}

// Écouter les changements Supabase
supabase.auth.onAuthStateChange((event, session) => {
    currentUser = session?.user || null;
    notifyAuthListeners(event, currentUser);
});

/**
 * Récupère l'utilisateur courant
 */
export async function getCurrentUser() {
    if (currentUser) return currentUser;
    
    const { data: { user } } = await supabase.auth.getUser();
    currentUser = user;
    return user;
}

/**
 * Récupère le token JWT pour les requêtes API
 */
export async function getAuthToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token;
}

/**
 * Vérifie si l'utilisateur est authentifié
 */
export async function isAuthenticated() {
    const user = await getCurrentUser();
    return !!user;
}

export { supabase };
export default supabase;
