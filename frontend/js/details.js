// frontend/js/details.js
/**
 * Page de détails d'une série/film (style Netflix)
 * Affiche les saisons et épisodes
 */

import api from './api.js';
import { 
    showToast,
    handleApiError,
    formatDuration,
    formatDate,
    escapeHtml
} from './utils.js';

// État global
let currentSeries = null;
let currentSeason = 0;

/**
 * Initialise la page de détails
 */
document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const folderId = urlParams.get('id');
    
    if (!folderId) {
        showError('ID du contenu manquant dans l\'URL');
        return;
    }
    
    await loadSeriesDetails(folderId);
});

/**
 * Affiche une erreur et cache le chargement
 */
function showError(message) {
    document.getElementById('loading-container').style.display = 'none';
    document.getElementById('main-content').style.display = 'none';
    document.getElementById('error-container').style.display = 'block';
    document.getElementById('error-message').textContent = message;
    showToast(message, 'error');
}

/**
 * Charge les détails de la série/film
 */
async function loadSeriesDetails(folderId) {
    try {
        console.log('Chargement du dossier:', folderId);
        
        // Utiliser l'API pour récupérer les détails
        const result = await api.getFolderDetails(folderId);
        
        console.log('Résultat API:', result);
        
        if (!result || !result.success) {
            throw new Error(result?.error || 'Erreur lors du chargement des données');
        }
        
        currentSeries = result.data;
        
        if (!currentSeries || !currentSeries.folder) {
            throw new Error('Données du contenu invalides');
        }
        
        // Rendre la page
        renderSeriesPage(currentSeries);
        
        // Cacher le loading, montrer le contenu
        document.getElementById('loading-container').style.display = 'none';
        document.getElementById('main-content').style.display = 'block';
        
    } catch (error) {
        console.error('Erreur loadSeriesDetails:', error);
        showError(error.message || 'Erreur de chargement du contenu');
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
    renderInfo(folder, is_series, seasons, episodes);
    
    // Saisons ou épisodes directs
    if (is_series && seasons && seasons.length > 0) {
        renderSeasons(seasons);
    } else if (episodes && episodes.length > 0) {
        renderEpisodesList(episodes, 'Épisodes');
    } else {
        document.getElementById('seasons-container').innerHTML = 
            '<p style="color: var(--light-gray); text-align: center; padding: 2rem;">Aucun épisode disponible</p>';
    }
    
    // Boutons d'action
    initActionButtons(folder, episodes, seasons);
}

/**
 * Rend le hero avec backdrop
 */
function renderHero(folder) {
    const hero = document.getElementById('series-hero');
    const titleEl = document.getElementById('series-title');
    const yearEl = document.getElementById('series-year');
    const ratingEl = document.getElementById('series-rating');
    const genresEl = document.getElementById('series-genres');
    
    if (!hero) return;
    
    // Image de fond
    const backdrop = folder.backdrop_url || folder.poster_url || '/img/default-backdrop.png';
    hero.style.backgroundImage = `
        linear-gradient(to bottom, rgba(10,10,10,0.3) 0%, rgba(10,10,10,0.8) 60%, var(--background-black) 100%),
        url(${backdrop})
    `;
    
    // Titre
    if (titleEl) {
        titleEl.textContent = folder.title || folder.folder_name;
    }
    
    // Année
    if (yearEl) {
        yearEl.textContent = folder.year || '';
        yearEl.style.display = folder.year ? 'inline' : 'none';
    }
    
    // Note
    if (ratingEl) {
        if (folder.rating) {
            ratingEl.innerHTML = `⭐ ${folder.rating.toFixed(1)}`;
            ratingEl.style.display = 'inline';
        } else {
            ratingEl.style.display = 'none';
        }
    }
    
    // Genres
    if (genresEl) {
        if (folder.genres && folder.genres.length > 0) {
            genresEl.textContent = folder.genres.join(' • ');
            genresEl.style.display = 'inline';
        } else {
            genresEl.style.display = 'none';
        }
    }
}

/**
 * Rend les infos de la série
 */
function renderInfo(folder, is_series, seasons, episodes) {
    const descEl = document.getElementById('series-description');
    const metaEl = document.getElementById('series-meta-info');
    
    // Description
    if (descEl) {
        descEl.textContent = folder.description || 'Aucune description disponible.';
    }
    
    // Meta info (épisodes, saisons, etc.)
    if (metaEl) {
        const parts = [];
        
        if (is_series) {
            const seasonCount = seasons ? seasons.length : 0;
            const episodeCount = episodes ? episodes.length : 0;
            
            if (seasonCount > 0) parts.push(`${seasonCount} saison${seasonCount > 1 ? 's' : ''}`);
            if (episodeCount > 0) parts.push(`${episodeCount} épisode${episodeCount > 1 ? 's' : ''}`);
        } else {
            const episodeCount = episodes ? episodes.length : 0;
            if (episodeCount > 0) parts.push(`${episodeCount} épisode${episodeCount > 1 ? 's' : ''}`);
        }
        
        metaEl.innerHTML = parts.map(p => `<span>${p}</span>`).join('');
    }
}

/**
 * Rend le sélecteur de saisons et les épisodes
 */
function renderSeasons(seasons) {
    const selectorContainer = document.getElementById('season-selector');
    const episodesContainer = document.getElementById('episodes-list');
    
    if (!selectorContainer || !episodesContainer) return;
    
    if (!seasons || seasons.length === 0) {
        selectorContainer.innerHTML = '';
        episodesContainer.innerHTML = '<p>Aucune saison disponible</p>';
        return;
    }
    
    // Créer le sélecteur de saisons
    if (seasons.length > 1) {
        selectorContainer.innerHTML = `
            <select id="season-select" class="season-select">
                ${seasons.map((season, idx) => `
                    <option value="${idx}" ${idx === 0 ? 'selected' : ''}>
                        ${season.season_name} (${season.episode_count || 0} épisodes)
                    </option>
                `).join('')}
            </select>
        `;
        
        // Écouteur de changement de saison
        const select = document.getElementById('season-select');
        select.addEventListener('change', (e) => {
            const seasonIdx = parseInt(e.target.value);
            currentSeason = seasonIdx;
            renderEpisodesList(seasons[seasonIdx].episodes, seasons[seasonIdx].season_name);
        });
    } else {
        selectorContainer.innerHTML = `<h3 style="color: white; margin-bottom: 1rem;">${seasons[0].season_name}</h3>`;
    }
    
    // Afficher la première saison par défaut
    renderEpisodesList(seasons[0].episodes, seasons[0].season_name);
}

/**
 * Rend la liste des épisodes
 */
function renderEpisodesList(episodes, title) {
    const container = document.getElementById('episodes-list');
    
    if (!container) return;
    
    if (!episodes || episodes.length === 0) {
        container.innerHTML = '<p class="no-episodes" style="color: var(--light-gray); padding: 2rem;">Aucun épisode disponible</p>';
        return;
    }
    
    const listHTML = episodes.map((ep, index) => {
        const epNum = ep.episode_number || (index + 1);
        const stillPath = ep.still_path || ep.poster_url || '/img/default-episode.png';
        
        return `
            <div class="episode-card" data-id="${ep.id}" data-index="${index}">
                <div class="episode-number">${epNum}</div>
                <div class="episode-image">
                    <img src="${stillPath}" alt="${escapeHtml(ep.title)}" loading="lazy" onerror="this.src='/img/default-episode.png'">
                    <div class="episode-play-overlay">
                        <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                </div>
                <div class="episode-info">
                    <h4 class="episode-title">${escapeHtml(ep.title)}</h4>
                    ${ep.description ? `<p class="episode-desc">${escapeHtml(ep.description.substring(0, 150))}${ep.description.length > 150 ? '...' : ''}</p>` : ''}
                    <div class="episode-meta">
                        ${ep.duration ? `<span>⏱️ ${formatDuration(ep.duration)}</span>` : ''}
                        ${ep.air_date ? `<span>📅 ${formatDate(ep.air_date)}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = listHTML;
    
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
function initActionButtons(folder, episodes, seasons) {
    // Bouton Lecture (premier épisode disponible)
    const playBtn = document.getElementById('btn-play-series');
    if (playBtn) {
        playBtn.addEventListener('click', () => {
            let firstEpisode = null;
            
            if (seasons && seasons.length > 0 && seasons[0].episodes && seasons[0].episodes.length > 0) {
                firstEpisode = seasons[0].episodes[0];
            } else if (episodes && episodes.length > 0) {
                firstEpisode = episodes[0];
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
            // Pour l'instant, juste un feedback visuel
            // TODO: Implémenter l'ajout à la watchlist quand l'API sera prête
            showToast('Ajouté à votre liste !', 'success');
            listBtn.style.background = 'rgba(16, 185, 129, 0.2)';
            listBtn.style.borderColor = '#10B981';
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
    if (!episodeId) {
        showToast('ID d\'épisode invalide', 'error');
        return;
    }
    
    // Animation de transition
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    
    setTimeout(() => {
        window.location.href = `player.html?id=${episodeId}`;
    }, 300);
}

// Export pour utilisation externe si nécessaire
window.loadSeriesDetails = loadSeriesDetails;
window.playEpisode = playEpisode;
