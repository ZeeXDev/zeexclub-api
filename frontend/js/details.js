// frontend/js/details.js
/**
 * Page de détails d'une série/film (style Netflix)
 * Affiche les saisons et épisodes
 */

import api from './api.js';
import { 
    showLoading, 
    hideLoading, 
    showToast,
    handleApiError,
    formatDuration,
    formatDate,
    escapeHtml
} from './utils.js';

// État global
let currentSeries = null;
let currentSeason = 0;
let currentEpisode = null;

/**
 * Initialise la page de détails
 */
document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const folderId = urlParams.get('id');
    
    if (!folderId) {
        showToast('Série/Film non spécifié', 'error');
        window.location.href = 'index.html';
        return;
    }
    
    await loadSeriesDetails(folderId);
});

/**
 * Charge les détails de la série/film
 */
async function loadSeriesDetails(folderId) {
    showLoading('Chargement...');
    
    try {
        const response = await fetch(`${api.baseUrl}/folders/${folderId}/details/`);
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Erreur de chargement');
        }
        
        currentSeries = result.data;
        renderSeriesPage(currentSeries);
        
    } catch (error) {
        handleApiError(error, 'Erreur de chargement');
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 3000);
    } finally {
        hideLoading();
    }
}

/**
 * Rend la page série complète
 */
function renderSeriesPage(data) {
    const { folder, is_series, seasons, episodes } = data;
    
    // Mettre à jour le titre de la page
    document.title = `${folder.title || folder.folder_name} - ZeeXClub`;
    
    // Hero section avec backdrop
    renderHero(folder);
    
    // Info section
    renderInfo(folder);
    
    // Saisons ou épisodes directs
    if (is_series && seasons.length > 0) {
        renderSeasons(seasons);
    } else {
        renderEpisodesList(episodes || [], 'Épisodes');
    }
    
    // Boutons d'action
    initActionButtons(folder);
}

/**
 * Rend le hero avec backdrop
 */
function renderHero(folder) {
    const hero = document.getElementById('series-hero');
    if (!hero) return;
    
    const backdrop = folder.backdrop_url || folder.poster_url || '/img/default-backdrop.png';
    const title = folder.title || folder.folder_name;
    
    hero.style.backgroundImage = `
        linear-gradient(to bottom, rgba(10,10,10,0.3) 0%, rgba(10,10,10,0.8) 60%, var(--background-black) 100%),
        url(${backdrop})
    `;
    
    hero.innerHTML = `
        <div class="hero-content">
            <h1 class="series-title">${escapeHtml(title)}</h1>
            ${folder.year ? `<span class="series-year">${folder.year}</span>` : ''}
            ${folder.rating ? `<span class="series-rating">⭐ ${folder.rating.toFixed(1)}</span>` : ''}
            ${folder.genres ? `<span class="series-genres">${folder.genres.join(' • ')}</span>` : ''}
        </div>
    `;
}

/**
 * Rend les infos de la série
 */
function renderInfo(folder) {
    const container = document.getElementById('series-info');
    if (!container) return;
    
    container.innerHTML = `
        <p class="series-description">${escapeHtml(folder.description || 'Aucune description disponible.')}</p>
        <div class="series-meta">
            <span>${folder.total_episodes || 0} épisodes</span>
            ${folder.season_count ? `<span>${folder.season_count} saisons</span>` : ''}
        </div>
    `;
}

/**
 * Rend le sélecteur de saisons et les épisodes
 */
function renderSeasons(seasons) {
    const container = document.getElementById('seasons-container');
    if (!container) return;
    
    // Créer le sélecteur de saisons
    const selectorHTML = `
        <div class="season-selector">
            <select id="season-select" class="season-select">
                ${seasons.map((season, idx) => `
                    <option value="${idx}" ${idx === 0 ? 'selected' : ''}>
                        ${season.season_name} (${season.episode_count} épisodes)
                    </option>
                `).join('')}
            </select>
        </div>
        <div id="episodes-list" class="episodes-list"></div>
    `;
    
    container.innerHTML = selectorHTML;
    
    // Afficher la première saison par défaut
    renderEpisodesList(seasons[0].episodes, seasons[0].season_name);
    
    // Écouteur de changement de saison
    const select = document.getElementById('season-select');
    select.addEventListener('change', (e) => {
        const seasonIdx = parseInt(e.target.value);
        currentSeason = seasonIdx;
        renderEpisodesList(seasons[seasonIdx].episodes, seasons[seasonIdx].season_name);
    });
}

/**
 * Rend la liste des épisodes
 */
function renderEpisodesList(episodes, title) {
    const container = document.getElementById('episodes-list');
    if (!container) return;
    
    if (!episodes || episodes.length === 0) {
        container.innerHTML = '<p class="no-episodes">Aucun épisode disponible</p>';
        return;
    }
    
    const listHTML = episodes.map((ep, index) => `
        <div class="episode-card" data-id="${ep.id}" data-index="${index}">
            <div class="episode-number">${ep.episode_number || index + 1}</div>
            <div class="episode-image">
                <img src="${ep.still_path || ep.poster_url || '/img/default-episode.png'}" alt="${escapeHtml(ep.title)}">
                <div class="episode-play-overlay">
                    <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                </div>
            </div>
            <div class="episode-info">
                <h4 class="episode-title">${escapeHtml(ep.title)}</h4>
                ${ep.description ? `<p class="episode-desc">${escapeHtml(ep.description.substring(0, 150))}...</p>` : ''}
                <div class="episode-meta">
                    ${ep.duration ? `<span>${formatDuration(ep.duration)}</span>` : ''}
                    ${ep.air_date ? `<span>${formatDate(ep.air_date)}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = `
        <h3 class="episodes-section-title">${escapeHtml(title)}</h3>
        ${listHTML}
    `;
    
    // Ajouter les événements de clic
    container.querySelectorAll('.episode-card').forEach(card => {
        card.addEventListener('click', () => {
            const episodeId = card.dataset.id;
            playEpisode(episodeId);
        });
    });
}

/**
 * Initialise les boutons d'action
 */
function initActionButtons(folder) {
    // Bouton Lecture (premier épisode ou épisode en cours)
    const playBtn = document.getElementById('btn-play-series');
    if (playBtn) {
        playBtn.addEventListener('click', () => {
            // Trouver le premier épisode disponible
            let firstEpisode = null;
            
            if (currentSeries.seasons && currentSeries.seasons.length > 0) {
                firstEpisode = currentSeries.seasons[0].episodes[0];
            } else if (currentSeries.episodes && currentSeries.episodes.length > 0) {
                firstEpisode = currentSeries.episodes[0];
            }
            
            if (firstEpisode) {
                playEpisode(firstEpisode.id);
            } else {
                showToast('Aucun épisode disponible', 'error');
            }
        });
    }
    
    // Bouton Ajouter à ma liste
    const listBtn = document.getElementById('btn-add-list');
    if (listBtn) {
        listBtn.addEventListener('click', async () => {
            try {
                // Ajouter le dossier à la watchlist (nécessite adaptation API)
                showToast('Ajouté à votre liste !', 'success');
                listBtn.classList.add('active');
            } catch (error) {
                handleApiError(error);
            }
        });
    }
    
    // Bouton Partager
    const shareBtn = document.getElementById('btn-share-series');
    if (shareBtn) {
        shareBtn.addEventListener('click', async () => {
            const url = window.location.href;
            try {
                await navigator.clipboard.writeText(url);
                showToast('Lien copié !', 'success');
            } catch (err) {
                showToast('Impossible de copier', 'error');
            }
        });
    }
}

/**
 * Lance la lecture d'un épisode
 */
function playEpisode(episodeId) {
    // Animation de transition
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    
    setTimeout(() => {
        window.location.href = `player.html?id=${episodeId}`;
    }, 300);
}

// Export pour utilisation externe
window.loadSeriesDetails = loadSeriesDetails;
window.playEpisode = playEpisode;
