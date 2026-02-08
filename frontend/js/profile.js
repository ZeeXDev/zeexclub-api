// frontend/js/profile.js
/**
 * Script pour la page profil utilisateur
 */

import { initAuth, requireAuth, signOut } from './auth.js';
import api from './api.js';
import { 
    showLoading, 
    hideLoading, 
    showToast,
    handleApiError,
    formatDuration,
    createMovieCard
} from './utils.js';

/**
 * Initialise la page profil
 */
document.addEventListener('DOMContentLoaded', async () => {
    const user = await requireAuth();
    if (!user) return;
    
    await initAuth();
    loadUserProfile(user);
    loadWatchHistory();
    loadWatchlist();
    loadStats();
});

/**
 * Charge les infos du profil
 */
function loadUserProfile(user) {
    const nameEl = document.getElementById('profile-name');
    const emailEl = document.getElementById('profile-email');
    const avatarEl = document.getElementById('profile-avatar');
    
    const displayName = user.user_metadata?.full_name || user.email;
    const avatarUrl = user.user_metadata?.avatar_url || '/img/default-avatar.png';
    
    if (nameEl) nameEl.textContent = displayName;
    if (emailEl) emailEl.textContent = user.email;
    if (avatarEl) avatarEl.src = avatarUrl;
    
    // Bouton déconnexion
    document.getElementById('btn-logout')?.addEventListener('click', signOut);
}

/**
 * Charge l'historique de visionnage
 */
async function loadWatchHistory() {
    const container = document.getElementById('history-list');
    if (!container) return;
    
    showLoading();
    
    try {
        const { data } = await api.getWatchHistory();
        
        container.innerHTML = '';
        
        if (!data || data.length === 0) {
            container.innerHTML = '<p class="empty-message">Aucun historique</p>';
            return;
        }
        
        data.forEach(item => {
            const video = item.videos;
            const progress = video.duration 
                ? Math.round((item.progress / video.duration) * 100) 
                : 0;
            
            const el = document.createElement('div');
            el.className = 'history-item';
            el.innerHTML = `
                <img src="${video.poster_url || '/img/default-poster.png'}" alt="${video.title}">
                <div class="history-info">
                    <h4>${video.title}</h4>
                    <p>${item.completed ? '✅ Terminé' : `⏱️ ${progress}% regardé`}</p>
                    <small>${new Date(item.last_watched).toLocaleDateString()}</small>
                </div>
                <button class="btn-resume" data-id="${video.id}">
                    ${item.completed ? 'Revoir' : 'Reprendre'}
                </button>
            `;
            
            el.querySelector('.btn-resume')?.addEventListener('click', () => {
                window.location.href = `player.html?id=${video.id}`;
            });
            
            container.appendChild(el);
        });
        
    } catch (error) {
        handleApiError(error);
    } finally {
        hideLoading();
    }
}

/**
 * Charge la liste de l'utilisateur
 */
async function loadWatchlist() {
    const grid = document.getElementById('watchlist-grid');
    if (!grid) return;
    
    try {
        const { data } = await api.getWatchlist();
        
        grid.innerHTML = '';
        
        if (!data || data.length === 0) {
            grid.innerHTML = '<p class="empty-message">Votre liste est vide</p>';
            return;
        }
        
        data.forEach((item, index) => {
            const video = item.videos;
            const card = createMovieCard(video, {
                onClick: () => {
                    window.location.href = `player.html?id=${video.id}`;
                }
            });
            
            // Bouton suppression
            const removeBtn = document.createElement('button');
            removeBtn.className = 'btn-remove';
            removeBtn.innerHTML = '✕';
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                removeFromWatchlist(video.id, card);
            };
            
            card.appendChild(removeBtn);
            grid.appendChild(card);
        });
        
    } catch (error) {
        handleApiError(error);
    }
}

async function removeFromWatchlist(videoId, element) {
    try {
        await api.removeFromWatchlist(videoId);
        element.remove();
        showToast('Retiré de votre liste', 'success');
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Charge les statistiques
 */
async function loadStats() {
    try {
        // Calculer depuis l'historique
        const { data: history } = await api.getWatchHistory(true); // Tout l'historique
        
        const totalWatched = history?.length || 0;
        const totalTime = history?.reduce((sum, item) => {
            return sum + (item.videos?.duration || 0);
        }, 0) || 0;
        
        const statsEl = document.getElementById('user-stats');
        if (statsEl) {
            statsEl.innerHTML = `
                <div class="stat-item">
                    <span class="stat-value">${totalWatched}</span>
                    <span class="stat-label">Vidéos regardées</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">${formatDuration(totalTime)}</span>
                    <span class="stat-label">Temps total</span>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}
