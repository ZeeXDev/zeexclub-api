// frontend/js/player.js
/**
 * Script pour la page lecteur vidéo
 */

import { initAuth } from './auth.js';
import api from './api.js';
import { 
    showLoading, 
    hideLoading, 
    showToast,
    handleApiError,
    formatDuration,
    formatDate,
    escapeHtml,
    copyToClipboard
} from './utils.js';

// État
let currentVideo = null;
let currentServer = 'zeex';
let watchInterval = null;
let player = null;

/**
 * Initialise la page lecteur
 */
document.addEventListener('DOMContentLoaded', async () => {
    await initAuth();
    
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('id');
    
    if (!videoId) {
        showToast('Vidéo non spécifiée', 'error');
        window.location.href = 'index.html';
        return;
    }
    
    await loadVideo(videoId);
    initPlayerControls();
    initComments();
    initServerSelector();
});

/**
 * Charge la vidéo
 */
async function loadVideo(videoId) {
    showLoading('Chargement de la vidéo...');
    
    try {
        const { data } = await api.getVideoDetail(videoId);
        
        if (!data) {
            throw new Error('Vidéo introuvable');
        }
        
        currentVideo = data;
        
        // Mettre à jour l'UI
        updateVideoInfo(data);
        setupPlayer(data);
        loadComments(videoId);
        loadSimilarVideos(data);
        
        // Démarrer le tracking de visionnage
        startWatchTracking(videoId);
        
    } catch (error) {
        handleApiError(error, 'Erreur de chargement de la vidéo');
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 3000);
    } finally {
        hideLoading();
    }
}

/**
 * Met à jour les informations de la vidéo
 */
function updateVideoInfo(video) {
    // Titre
    const titleEl = document.getElementById('video-title');
    if (titleEl) titleEl.textContent = video.title;
    
    // Meta
    const metaEl = document.getElementById('video-meta');
    if (metaEl) {
        const parts = [];
        if (video.year) parts.push(`<span class="video-year">${video.year}</span>`);
        if (video.duration) parts.push(`<span class="video-duration">${formatDuration(video.duration)}</span>`);
        if (video.rating) parts.push(`<span class="video-rating">⭐ ${video.rating.toFixed(1)}</span>`);
        if (video.views_count) parts.push(`<span class="video-views">${video.views_count} vues</span>`);
        
        metaEl.innerHTML = parts.join(' • ');
    }
    
    // Description
    const descEl = document.getElementById('video-description');
    if (descEl) {
        descEl.textContent = video.description || 'Aucune description disponible.';
    }
    
    // Genres
    const genresEl = document.getElementById('video-genres');
    if (genresEl && video.genre?.length) {
        genresEl.innerHTML = video.genre
            .map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`)
            .join('');
    }
    
    // Page title
    document.title = `${video.title} - ZeeXClub`;
}

/**
 * Configure le lecteur
 */
function setupPlayer(video) {
    const container = document.getElementById('player-container');
    if (!container) return;
    
    // URL de streaming
    const streamUrl = video.zeex_url;
    
    container.innerHTML = `
        <video id="main-player" controls autoplay playsinline style="width: 100%; height: 100%;">
            <source src="${streamUrl}" type="${video.mime_type || 'video/mp4'}">
            Votre navigateur ne supporte pas la lecture vidéo.
        </video>
    `;
    
    player = document.getElementById('main-player');
    
    // Restaurer la progression si disponible
    restoreProgress();
    
    // Événements du player
    player.addEventListener('timeupdate', onTimeUpdate);
    player.addEventListener('ended', onVideoEnded);
    player.addEventListener('error', onPlayerError);
}

/**
 * Change de serveur
 */
function switchServer(server) {
    if (!currentVideo) return;
    
    currentServer = server;
    const container = document.getElementById('player-container');
    
    // Mettre à jour les boutons
    document.querySelectorAll('.server-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.server === server);
    });
    
    if (server === 'zeex') {
        // Lecteur natif
        setupPlayer(currentVideo);
    } else if (server === 'filemoon' && currentVideo.filemoon_url) {
        // Iframe Filemoon
        container.innerHTML = `
            <iframe 
                src="${currentVideo.filemoon_url}" 
                width="100%" 
                height="100%" 
                frameborder="0" 
                allowfullscreen
                allow="autoplay; encrypted-media"
            ></iframe>
        `;
        player = null; // Pas de tracking sur Filemoon
    } else {
        showToast('Serveur non disponible', 'error');
    }
}

/**
 * Initialise le sélecteur de serveur
 */
function initServerSelector() {
    const selector = document.getElementById('server-list');
    if (!selector) return;
    
    selector.addEventListener('click', (e) => {
        const btn = e.target.closest('.server-btn');
        if (!btn) return;
        
        const server = btn.dataset.server;
        if (server !== currentServer) {
            switchServer(server);
        }
    });
}

/**
 * Tracking du visionnage
 */
function startWatchTracking(videoId) {
    // Sauvegarder la progression toutes les 10 secondes
    watchInterval = setInterval(() => {
        saveProgress();
    }, 10000);
    
    // Sauvegarder à la fermeture de la page
    window.addEventListener('beforeunload', () => {
        saveProgress();
    });
}

function onTimeUpdate() {
    if (!player || !currentVideo) return;
    
    const progress = Math.floor(player.currentTime);
    const duration = player.duration || currentVideo.duration || 1;
    const percent = (progress / duration) * 100;
    
    // Mettre à jour la barre de progression UI
    const progressBar = document.getElementById('watch-progress');
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
    }
}

async function saveProgress() {
    if (!player || !currentVideo) return;
    
    const progress = Math.floor(player.currentTime);
    const duration = player.duration || currentVideo.duration || 1;
    const completed = progress / duration > 0.9; // 90% = terminé
    
    try {
        await api.updateWatchProgress(currentVideo.id, progress, completed);
    } catch (error) {
        // Silencieux, on réessaiera plus tard
        console.warn('Failed to save progress:', error);
    }
}

function onVideoEnded() {
    saveProgress();
    showToast('Vidéo terminée ! 🎉', 'success');
    
    // Proposer la vidéo suivante si disponible
    // TODO: Implémenter la logique de playlist
}

function onPlayerError(e) {
    console.error('Player error:', e);
    showToast('Erreur de lecture. Essayez un autre serveur.', 'error');
}

function restoreProgress() {
    // La progression sera restaurée automatiquement par l'API
    // qui retourne l'historique utilisateur
    // Pour l'instant, on commence au début
}

/**
 * Initialise les contrôles du player
 */
function initPlayerControls() {
    // Bouton ajouter à ma liste
    document.getElementById('btn-watchlist')?.addEventListener('click', async () => {
        if (!currentVideo) return;
        
        try {
            await api.addToWatchlist(currentVideo.id);
            showToast('Ajouté à votre liste !', 'success');
        } catch (error) {
            if (error.message?.includes('duplicate')) {
                showToast('Déjà dans votre liste', 'info');
            } else {
                handleApiError(error);
            }
        }
    });
    
    // Bouton partager
    document.getElementById('btn-share')?.addEventListener('click', () => {
        const url = window.location.href;
        copyToClipboard(url);
    });
    
    // Bouton plein écran
    document.getElementById('btn-fullscreen')?.addEventListener('click', () => {
        const container = document.getElementById('player-wrapper');
        if (container?.requestFullscreen) {
            container.requestFullscreen();
        }
    });
}

/**
 * Gestion des commentaires
 */
async function initComments() {
    const toggleBtn = document.getElementById('toggle-comments');
    const section = document.getElementById('comments-section');
    const form = document.getElementById('comment-form');
    
    toggleBtn?.addEventListener('click', () => {
        section?.classList.toggle('visible');
        const isVisible = section?.classList.contains('visible');
        toggleBtn.innerHTML = isVisible 
            ? '💬 Masquer les commentaires' 
            : '💬 Afficher les commentaires';
    });
    
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const textarea = form.querySelector('textarea');
        const text = textarea?.value.trim();
        
        if (!text) return;
        
        // ✅ CORRECTION: Vérifier authentification sans redirection forcée
        const { data: { user } } = await import('./supabase-client.js').then(m => m.supabase.auth.getUser());
        if (!user) {
            showToast('Connectez-vous pour commenter', 'error');
            return;
        }
        
        try {
            await api.postComment(currentVideo.id, text);
            textarea.value = '';
            showToast('Commentaire publié !', 'success');
            loadComments(currentVideo.id); // Recharger
        } catch (error) {
            handleApiError(error);
        }
    });
}

async function loadComments(videoId) {
    const list = document.getElementById('comments-list');
    const countEl = document.getElementById('comments-count');
    
    if (!list) return;
    
    try {
        const { data } = await api.getComments(videoId);
        
        if (countEl) {
            countEl.textContent = data?.length || 0;
        }
        
        list.innerHTML = '';
        
        if (!data || data.length === 0) {
            list.innerHTML = '<p class="no-comments">Soyez le premier à commenter !</p>';
            return;
        }
        
        data.forEach(comment => {
            const item = createCommentElement(comment);
            list.appendChild(item);
        });
        
    } catch (error) {
        console.error('Failed to load comments:', error);
    }
}

function createCommentElement(comment) {
    const div = document.createElement('div');
    div.className = 'comment-item';
    
    const user = comment.users || {};
    const avatar = user.avatar_url || '/img/default-avatar.png';
    const name = user.display_name || user.email || 'Anonyme';
    const date = formatDate(comment.created_at);
    
    div.innerHTML = `
        <div class="comment-header">
            <img src="${avatar}" alt="${name}" class="comment-avatar">
            <div class="comment-meta">
                <span class="comment-author">${escapeHtml(name)}</span>
                <span class="comment-date">${date}</span>
            </div>
        </div>
        <p class="comment-text">${escapeHtml(comment.comment_text)}</p>
        <div class="comment-actions">
            <button class="like-btn" data-id="${comment.id}">
                👍 ${comment.likes || 0}
            </button>
        </div>
    `;
    
    return div;
}

/**
 * Charge les vidéos similaires
 */
async function loadSimilarVideos(video) {
    const container = document.getElementById('similar-videos');
    if (!container) return;
    
    try {
        // Recherche par genre similaire
        const genre = video.genre?.[0];
        const { data } = await api.searchVideos('', { genre });
        
        // Filtrer pour exclure la vidéo actuelle
        const similar = (data || [])
            .filter(v => v.id !== video.id)
            .slice(0, 6);
        
        if (similar.length === 0) {
            container.style.display = 'none';
            return;
        }
        
        const grid = container.querySelector('.movie-grid') || container;
        if (!grid) return;
        
        grid.innerHTML = '';
        
        similar.forEach((v, index) => {
            // ✅ CORRECTION: Importer createMovieCard dynamiquement si nécessaire
            const card = document.createElement('div');
            card.className = 'movie-card';
            card.style.animationDelay = `${index * 0.1}s`;
            card.innerHTML = `
                <div class="card-image">
                    <img src="${v.poster_url || '/img/default-poster.png'}" alt="${v.title}" loading="lazy">
                    <div class="card-overlay">
                        <button class="play-btn">
                            <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        </button>
                    </div>
                </div>
                <div class="card-content">
                    <h3 class="card-title">${escapeHtml(v.title)}</h3>
                    ${v.year ? `<span class="card-year">${v.year}</span>` : ''}
                </div>
            `;
            
            card.addEventListener('click', () => {
                window.location.href = `player.html?id=${v.id}`;
            });
            
            grid.appendChild(card);
        });
        
    } catch (error) {
        console.error('Failed to load similar videos:', error);
    }
}

// Nettoyage à la fermeture
window.addEventListener('beforeunload', () => {
    if (watchInterval) {
        clearInterval(watchInterval);
    }
    saveProgress();
});
