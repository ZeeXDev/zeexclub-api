// frontend/js/auth.js
/**
 * Gestion de l'authentification utilisateur
 */

import { supabase, getCurrentUser, onAuthStateChange } from './supabase-client.js';
import { showToast, showLoading, hideLoading } from './utils.js';

// État global
let authInitialized = false;

/**
 * Initialise l'authentification au chargement de la page
 */
export async function initAuth() {
    if (authInitialized) return;
    
    showLoading('Vérification de la session...');
    
    try {
        const user = await getCurrentUser();
        updateUIForAuthState(user);
        
        // Écouter les changements futurs
        onAuthStateChange((event, user) => {
            console.log('🔐 Auth event:', event);
            updateUIForAuthState(user);
            
            if (event === 'SIGNED_OUT') {
                window.location.href = 'login.html';
            }
        });
        
        authInitialized = true;
        
    } catch (error) {
        console.error('❌ Erreur init auth:', error);
        showToast('Erreur de connexion', 'error');
    } finally {
        hideLoading();
    }
}

/**
 * Met à jour l'UI selon l'état d'authentification
 */
function updateUIForAuthState(user) {
    const authElements = document.querySelectorAll('[data-auth]');
    const noAuthElements = document.querySelectorAll('[data-no-auth]');
    const userNameElements = document.querySelectorAll('[data-user-name]');
    const userAvatarElements = document.querySelectorAll('[data-user-avatar]');
    
    if (user) {
        // Utilisateur connecté
        authElements.forEach(el => el.style.display = '');
        noAuthElements.forEach(el => el.style.display = 'none');
        
        // Mettre à jour infos utilisateur
        const displayName = user.user_metadata?.full_name || user.email;
        const avatarUrl = user.user_metadata?.avatar_url || '/img/default-avatar.png';
        
        userNameElements.forEach(el => el.textContent = displayName);
        userAvatarElements.forEach(el => el.src = avatarUrl);
        
        // Stocker pour usage futur
        localStorage.setItem('zeex_user', JSON.stringify({
            id: user.id,
            email: user.email,
            name: displayName,
            avatar: avatarUrl
        }));
        
    } else {
        // Utilisateur déconnecté
        authElements.forEach(el => el.style.display = 'none');
        noAuthElements.forEach(el => el.style.display = '');
        
        localStorage.removeItem('zeex_user');
    }
}

/**
 * Connexion avec Google OAuth
 */
export async function signInWithGoogle(redirectTo = null) {
    showLoading('Connexion en cours...');
    
    try {
        const { data, error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: redirectTo || window.location.origin + '/index.html',
                queryParams: {
                    access_type: 'offline',
                    prompt: 'consent'
                }
            }
        });
        
        if (error) throw error;
        
        // La redirection est gérée par Supabase
        return data;
        
    } catch (error) {
        console.error('❌ Erreur connexion Google:', error);
        showToast('Erreur de connexion: ' + error.message, 'error');
        hideLoading();
        throw error;
    }
}

/**
 * Déconnexion
 */
export async function signOut() {
    showLoading('Déconnexion...');
    
    try {
        const { error } = await supabase.auth.signOut();
        if (error) throw error;
        
        showToast('Déconnecté avec succès');
        window.location.href = 'login.html';
        
    } catch (error) {
        console.error('❌ Erreur déconnexion:', error);
        showToast('Erreur de déconnexion', 'error');
        hideLoading();
    }
}

/**
 * Récupère les infos utilisateur stockées
 */
export function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem('zeex_user'));
    } catch {
        return null;
    }
}

/**
 * Vérifie si l'utilisateur est connecté (pour guards)
 */
export async function requireAuth() {
    const user = await getCurrentUser();
    
    if (!user) {
        // Sauvegarder la page demandée pour redirection post-login
        sessionStorage.setItem('redirectAfterLogin', window.location.href);
        window.location.href = 'login.html';
        return null;
    }
    
    return user;
}

/**
 * Redirige après login si une page était demandée
 */
export function handlePostLoginRedirect() {
    const redirect = sessionStorage.getItem('redirectAfterLogin');
    if (redirect) {
        sessionStorage.removeItem('redirectAfterLogin');
        window.location.href = redirect;
    } else {
        window.location.href = 'index.html';
    }
}

// Exposer fonctions globales pour HTML onclick
window.signInWithGoogle = signInWithGoogle;
window.signOut = signOut;
