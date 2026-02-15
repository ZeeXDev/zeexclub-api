/**
 * Page Lecteur - Lecture vidéo multi-serveurs
 */

import api from './api.js';
import { APP_CONFIG } from './config.js';

class PlayerPage {
    constructor() {
        const params = new URLSearchParams(window.location.search);
        this.episodeId = params.get('episode');
        this.showId = params.get('show');
        
        this.currentSource = null;
        this.sources = [];
        this.player = null;
        
        this.init();
    }

    async init() {
        if (!this.episodeId && !this.showId) {
            window.location.href = 'catalog.html';
            return;
        }

        this.showLoading(true);
        
        try {
            if (this.episodeId) {
                await this.loadEpisode(this.episodeId);
            } else {
                await this.loadMovie(this.showId);
            }
        } catch (error) {
            console.error('Erreur chargement player:', error);
            this.showError('Impossible de charger la vidéo');
        }
    }

    async loadEpisode(episodeId) {
        // Récupération des détails de l'épisode et des sources
        const [episodeRes, sourcesRes] = await Promise.all([
            api.getEpisode(episodeId),
            api.getEpisodeSources(episodeId)
        ]);

        this.episodeData = episodeRes.data;
        this.sources = sourcesRes.sources || [];
        
        this.renderPlayer();
        this.renderSources();
        this.renderEpisodeNav();
    }

    async loadMovie(showId) {
        // Pour les films, récupérer le show et ses sources
        const showRes = await api.getShow(showId);
        this.showData = showRes.data;
        
        // Récupérer les épisodes (pour un film, c'est la "saison 0")
        const episodesRes = await api.getShowEpisodes(showId);
        
        if (episodesRes.type === 'movie' && episodesRes.sources) {
            this.sources = episodesRes.sources;
        } else if (episodesRes.seasons?.[0]?.episodes?.[0]) {
            // Charger le premier épisode (le film)
            const episodeId = episodesRes.seasons[0].episodes[0].id;
            await this.loadEpisode(episodeId);
            return;
        }
        
        this.renderPlayer();
        this.renderSources();
    }

    renderPlayer() {
        const container = document.querySelector('.player-container');
        if (!container) return;

        const title = this.episodeData?.title || this.showData?.title || 'Lecture';
        const subtitle = this.episodeData ? 
            `S${this.episodeData.season_number}E${this.episodeData.episode_number}` : 
            'Film';

        // Mise à jour des infos
        document.querySelector('.player-title').textContent = title;
        document.querySelector('.player-meta').textContent = subtitle;

        // Sélection automatique de la meilleure source
        if (this.sources.length > 0) {
            // Priorité: Filemoon > Telegram
            const preferred = this.sources.find(s => s.server === 'filemoon') || this.sources[0];
            this.selectSource(preferred.id);
        }
    }

    selectSource(sourceId) {
        const source = this.sources.find(s => s.id === sourceId);
        if (!source) return;

        this.currentSource = source;
        
        // Mise à jour UI
        document.querySelectorAll('.server-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sourceId === sourceId);
        });

        // Chargement vidéo
        this.loadVideo(source);
    }

    loadVideo(source) {
        const container = document.querySelector('.player-container');
        
        if (source.server === 'filemoon') {
            // Filemoon: utiliser iframe
            container.innerHTML = `
                <iframe 
                    src="${source.embed_url}" 
                    width="100%" 
                    height="100%" 
                    frameborder="0" 
                    allowfullscreen
                    allow="autoplay; encrypted-media"
                    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                ></iframe>
            `;
        } else {
            // Telegram: utiliser balise video avec notre proxy
            container.innerHTML = `
                <video 
                    id="videoPlayer" 
                    class="video-element"
                    controls
                    autoplay
                    preload="${APP_CONFIG.preload}"
                    poster="${this.episodeData?.thumbnail || ''}"
                >
                    <source src="${source.direct_link}" type="video/mp4">
                    Votre navigateur ne supporte pas la lecture vidéo.
                </video>
            `;
            
            this.setupVideoControls();
        }
    }

    setupVideoControls() {
        const video = document.getElementById('videoPlayer');
        if (!video) return;

        // Sauvegarde de la position
        const saveKey = `progress_${this.episodeId || this.showId}`;
        
        video.addEventListener('timeupdate', () => {
            localStorage.setItem(saveKey, video.currentTime);
        });

        video.addEventListener('loadedmetadata', () => {
            const saved = localStorage.getItem(saveKey);
            if (saved && video.duration - parseFloat(saved) > 10) {
                video.currentTime = parseFloat(saved);
            }
        });

        // Marquer comme vu à 90%
        video.addEventListener('ended', () => {
            this.markAsWatched();
        });
    }

    renderSources() {
        const container = document.querySelector('.server-buttons');
        if (!container || this.sources.length <= 1) return;

        container.innerHTML = this.sources.map(source => `
            <button 
                class="server-btn ${source.id === this.currentSource?.id ? 'active' : ''}" 
                data-source-id="${source.id}"
                onclick="player.selectSource('${source.id}')"
            >
                <i class="fas fa-${source.server === 'filemoon' ? 'cloud' : 'paper-plane'}"></i>
                <div>
                    <div class="server-name">${source.server === 'filemoon' ? 'Filemoon' : 'Telegram'}</div>
                    <div class="server-quality">${source.quality || 'HD'}</div>
                </div>
            </button>
        `).join('');
    }

    renderEpisodeNav() {
        // Implémentation navigation épisodes précédent/suivant
        // Nécessite de connaître la liste complète des épisodes de la saison
    }

    markAsWatched() {
        // API call pour marquer comme vu (si authentification implémentée)
        console.log('Marqué comme vu:', this.episodeId);
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) overlay.classList.toggle('active', show);
    }

    showError(message) {
        const container = document.querySelector('.player-container');
        if (container) {
            container.innerHTML = `
                <div class="player-error active">
                    <i class="fas fa-exclamation-circle"></i>
                    <h3>Erreur de lecture</h3>
                    <p>${message}</p>
                    <button class="btn btn-primary" onclick="location.reload()">
                        <i class="fas fa-redo"></i> Réessayer
                    </button>
                </div>
            `;
        }
    }
}

// Initialisation
let player;
document.addEventListener('DOMContentLoaded', () => {
    player = new PlayerPage();
});
