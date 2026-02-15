/**
 * Page Détails - Affichage complet d'un show avec saisons/épisodes
 */

import api from './api.js';
import { APP_CONFIG } from './config.js';

class DetailsPage {
    constructor() {
        this.showId = new URLSearchParams(window.location.search).get('id');
        this.showData = null;
        this.currentSeason = 1;
        
        if (!this.showId) {
            window.location.href = 'catalog.html';
            return;
        }
        
        this.init();
    }

    async init() {
        this.showLoading(true);
        
        try {
            // Chargement parallèle des données
            const [showResponse, episodesResponse] = await Promise.all([
                api.getShow(this.showId),
                api.getShowEpisodes(this.showId)
            ]);
            
            this.showData = showResponse.data;
            this.episodesData = episodesResponse;
            
            this.renderHero();
            this.renderDetails();
            
            if (this.showData.type === 'series') {
                this.renderSeasons();
            }
            
            this.loadRelated();
            
        } catch (error) {
            console.error('Erreur chargement détails:', error);
            this.showError();
        } finally {
            this.showLoading(false);
        }
    }

    renderHero() {
        const show = this.showData;
        
        // Backdrop
        const backdrop = document.querySelector('.details-backdrop');
        if (backdrop) {
            const imageUrl = api.getImageUrl(show.backdrop_path || show.poster_path, 'original');
            backdrop.style.backgroundImage = `url(${imageUrl})`;
        }

        // Poster
        const poster = document.querySelector('.details-poster');
        if (poster) {
            poster.src = api.getImageUrl(show.poster_path, APP_CONFIG.posterSize);
            poster.alt = show.title;
        }

        // Infos
        const title = document.querySelector('.details-title');
        if (title) title.textContent = show.title;

        const meta = document.querySelector('.details-meta');
        if (meta) {
            const year = show.release_date ? new Date(show.release_date).getFullYear() : 'N/A';
            const rating = show.rating ? `<span class="match">${show.rating.toFixed(1)}/10</span>` : '';
            const duration = show.runtime ? `${Math.floor(show.runtime / 60)}h ${show.runtime % 60}min` : '';
            
            meta.innerHTML = `
                ${rating}
                <span>${year}</span>
                <span class="maturity">16+</span>
                ${duration ? `<span>${duration}</span>` : ''}
                <span><i class="fas fa-eye"></i> ${show.views || 0} vues</span>
            `;
        }

        const description = document.querySelector('.details-description');
        if (description) {
            description.textContent = show.overview || 'Aucun synopsis disponible.';
        }

        // Genres
        const genres = document.querySelector('.details-genres');
        if (genres && show.genres) {
            const genreList = Array.isArray(show.genres) ? show.genres : show.genres.split(',');
            genres.innerHTML = genreList.map(g => `<span class="genre-tag">${g.trim()}</span>`).join('');
        }

        // Bouton lecture
        const playBtn = document.querySelector('.btn-play');
        if (playBtn) {
            playBtn.onclick = () => {
                if (show.type === 'movie') {
                    window.location.href = `player.html?show=${show.id}`;
                } else {
                    // Pour les séries, jouer le premier épisode
                    const firstEpisode = this.getFirstEpisode();
                    if (firstEpisode) {
                        window.location.href = `player.html?episode=${firstEpisode.id}`;
                    }
                }
            };
        }
    }

    getFirstEpisode() {
        if (this.episodesData.type === 'series' && this.episodesData.seasons?.length > 0) {
            return this.episodesData.seasons[0].episodes?.[0];
        }
        return null;
    }

    renderDetails() {
        // Informations additionnelles
        const detailsGrid = document.querySelector('.details-grid');
        if (detailsGrid) {
            const show = this.showData;
            detailsGrid.innerHTML = `
                <div class="detail-item">
                    <span class="detail-label">Titre original</span>
                    <span class="detail-value">${show.original_title || show.title}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Date de sortie</span>
                    <span class="detail-value">${show.release_date ? new Date(show.release_date).toLocaleDateString('fr-FR') : 'N/A'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Genres</span>
                    <span class="detail-value">${Array.isArray(show.genres) ? show.genres.join(', ') : show.genres}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Type</span>
                    <span class="detail-value">${show.type === 'movie' ? 'Film' : 'Série'}</span>
                </div>
            `;
        }
    }

    renderSeasons() {
        const container = document.querySelector('.seasons-container');
        if (!container) return;

        const seasons = this.episodesData.seasons || [];
        
        if (seasons.length === 0) {
            container.innerHTML = '<p class="no-content">Aucun épisode disponible pour le moment.</p>';
            return;
        }

        // Sélecteur de saison
        const selector = document.createElement('div');
        selector.className = 'season-selector';
        selector.innerHTML = `
            <select id="seasonSelect">
                ${seasons.map(s => `
                    <option value="${s.season_number}" ${s.season_number === this.currentSeason ? 'selected' : ''}>
                        ${s.name || `Saison ${s.season_number}`} (${s.episodes?.length || 0} épisodes)
                    </option>
                `).join('')}
            </select>
        `;
        
        container.appendChild(selector);

        // Liste des épisodes
        const episodesList = document.createElement('div');
        episodesList.className = 'episodes-list';
        episodesList.id = 'episodesList';
        container.appendChild(episodesList);

        // Event listener
        selector.querySelector('select').addEventListener('change', (e) => {
            this.currentSeason = parseInt(e.target.value);
            this.renderEpisodesList();
        });

        this.renderEpisodesList();
    }

    renderEpisodesList() {
        const container = document.getElementById('episodesList');
        if (!container) return;

        const season = this.episodesData.seasons?.find(s => s.season_number === this.currentSeason);
        if (!season) return;

        const episodes = season.episodes || [];

        container.innerHTML = episodes.map((ep, idx) => `
            <div class="episode-item" onclick="window.location.href='player.html?episode=${ep.id}'">
                <img src="${api.getImageUrl(ep.thumbnail, 'w300')}" 
                     alt="${ep.title}" 
                     class="episode-thumbnail"
                     onerror="this.src='/img/default-thumb.jpg'">
                <div class="episode-info">
                    <h3>${ep.episode_number}. ${ep.title || `Épisode ${ep.episode_number}`}</h3>
                    <p>${ep.overview || 'Aucune description disponible.'}</p>
                </div>
                <div class="episode-meta">
                    ${ep.runtime ? `<span>${ep.runtime} min</span>` : ''}
                    <button class="episode-play">
                        <i class="fas fa-play"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    async loadRelated() {
        try {
            const response = await api.getRelatedShows(this.showId);
            const shows = response.data || [];
            
            const container = document.querySelector('.related-grid');
            if (!container || shows.length === 0) return;

            container.innerHTML = shows.map(show => `
                <div class="movie-card" onclick="window.location.href='details.html?id=${show.id}'">
                    <img src="${api.getImageUrl(show.poster_path, APP_CONFIG.posterSize)}" 
                         alt="${show.title}" 
                         class="movie-poster"
                         loading="lazy">
                    <div class="movie-info">
                        <h3 class="movie-title">${show.title}</h3>
                    </div>
                </div>
            `).join('');
            
        } catch (error) {
            console.error('Erreur chargement suggestions:', error);
        }
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) overlay.classList.toggle('active', show);
    }

    showError() {
        const container = document.querySelector('.details-content');
        if (container) {
            container.innerHTML = `
                <div class="error-container">
                    <div class="error-code">404</div>
                    <p class="error-message">Contenu non trouvé</p>
                    <a href="catalog.html" class="btn btn-primary">Retour au catalogue</a>
                </div>
            `;
        }
    }
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    new DetailsPage();
});
