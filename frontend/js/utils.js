// frontend/js/utils.js
/**
 * Fonctions utilitaires pour le frontend
 */

import CONFIG from './config.js';

/**
 * Affiche un toast notification
 */
export function showToast(message, type = 'info', duration = CONFIG.TOAST_DURATION) {
    // Créer ou récupérer le container
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        document.body.appendChild(container);
    }
    
    // Créer le toast
    const toast = document.createElement('div');
    const colors = {
        info: 'var(--primary-blue)',
        success: '#22c55e',
        error: 'var(--primary-red)',
        warning: '#f59e0b'
    };
    
    toast.style.cssText = `
        background: var(--dark-gray);
        border-left: 4px solid ${colors[type] || colors.info};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        animation: slideInRight 0.3s ease;
        max-width: 400px;
        font-size: 14px;
    `;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    // Auto-remove
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Affiche un overlay de chargement
 */
export function showLoading(text = 'Chargement...') {
    let overlay = document.getElementById('loading-overlay');
    
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.cssText = `
            position: fixed;
            inset: 0;
            background: rgba(10, 10, 10, 0.9);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            backdrop-filter: blur(5px);
        `;
        
        overlay.innerHTML = `
            <div class="spinner" style="
                width: 50px;
                height: 50px;
                border: 3px solid var(--dark-gray);
                border-top-color: var(--primary-red);
                border-radius: 50%;
                animation: spin 1s linear infinite;
            "></div>
            <p id="loading-text" style="
                margin-top: 20px;
                color: var(--light-gray);
                font-size: 14px;
            ">${text}</p>
        `;
        
        document.body.appendChild(overlay);
    } else {
        const textEl = document.getElementById('loading-text');
        if (textEl) textEl.textContent = text;
        overlay.style.display = 'flex';
    }
}

/**
 * Cache l'overlay de chargement
 */
export function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

/**
 * Formate une durée en secondes
 */
export function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0min';
    
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}h ${mins}min`;
    }
    if (secs > 0) {
        return `${mins}min ${secs}s`;
    }
    return `${mins}min`;
}

/**
 * Formate une taille en bytes
 */
export function formatFileSize(bytes) {
    if (!bytes || bytes < 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(2)} ${units[unitIndex]}`;
}

/**
 * Formate une date
 */
export function formatDate(dateString) {
    if (!dateString) return 'Date inconnue';
    
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('fr-FR', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
    } catch {
        return dateString;
    }
}

/**
 * Debounce une fonction
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle une fonction
 */
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Crée une carte de film/série
 */
export function createMovieCard(video, options = {}) {
    const {
        showEpisode = false,
        showProgress = false,
        progress = 0,
        onClick
    } = options;
    
    const card = document.createElement('div');
    card.className = 'movie-card';
    
    // Image poster
    const posterUrl = video.poster_url || video.still_path || CONFIG.DEFAULT_POSTER;
    
    // Badge épisode
    let badge = '';
    if (showEpisode && (video.episode_number || video.season_number)) {
        const epText = video.season_number 
            ? `S${video.season_number}E${video.episode_number}` 
            : `E${video.episode_number}`;
        badge = `<span class="episode-badge">${epText}</span>`;
    }
    
    // Barre de progression
    let progressBar = '';
    if (showProgress && progress > 0) {
        progressBar = `
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%"></div>
            </div>
        `;
    }
    
    card.innerHTML = `
        <div class="card-image">
            <img src="${posterUrl}" alt="${video.title}" loading="lazy">
            ${badge}
            <div class="card-overlay">
                <button class="play-btn">
                    <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                </button>
            </div>
        </div>
        <div class="card-content">
            <h3 class="card-title">${escapeHtml(video.title)}</h3>
            ${video.year ? `<span class="card-year">${video.year}</span>` : ''}
            ${video.rating ? `<span class="card-rating">⭐ ${video.rating.toFixed(1)}</span>` : ''}
            ${progressBar}
        </div>
    `;
    
    if (onClick) {
        card.addEventListener('click', () => onClick(video));
    }
    
    return card;
}

/**
 * Échappe le HTML pour sécurité
 */
export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Anime un élément
 */
export function animate(element, animation, duration = 300) {
    element.style.animation = 'none';
    element.offsetHeight; // Trigger reflow
    element.style.animation = `${animation} ${duration}ms ease`;
    
    setTimeout(() => {
        element.style.animation = '';
    }, duration);
}

/**
 * Intersection Observer pour lazy loading
 */
export function observeElements(selector, callback, options = {}) {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                callback(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, {
        rootMargin: '50px',
        ...options
    });
    
    document.querySelectorAll(selector).forEach(el => observer.observe(el));
    return observer;
}

/**
 * Gère les erreurs API de manière uniforme
 */
export function handleApiError(error, defaultMessage = 'Une erreur est survenue') {
    console.error('API Error:', error);
    
    const message = error.message || defaultMessage;
    showToast(message, 'error');
    
    return message;
}

/**
 * Copie dans le presse-papiers
 */
export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copié dans le presse-papiers', 'success');
        return true;
    } catch (err) {
        showToast('Impossible de copier', 'error');
        return false;
    }
}

/**
 * Partage natif ou fallback
 */
export async function shareContent(data) {
    if (navigator.share) {
        try {
            await navigator.share(data);
            return true;
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('Share failed:', err);
            }
        }
    }
    
    // Fallback: copier le lien
    if (data.url) {
        return copyToClipboard(data.url);
    }
    
    return false;
}
