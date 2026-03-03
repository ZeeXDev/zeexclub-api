/**
 * Page Lecteur - Lecture vidéo multi-serveurs (CORRIGÉ)
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
        this.showData = null;
        this.episodeData = null;
        
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
            } else if (this.showId) {
                await this.loadMovie(this.showId);
            }
        } catch (error) {
            console.error('Erreur chargement player:', error);
            this.showError('Impossible de charger la vidéo. Vérifiez votre connexion.');
        } finally {
            this.showLoading(false);
        }
    }

    async loadEpisode(episodeId) {
        try {
            const sourcesRes = await api.getEpisodeSources(episodeId);
            
            if (!sourcesRes || !sourcesRes.sources || sourcesRes.sources.length === 0) {
                throw new Error('Aucune source disponible');
            }

            this.sources = sourcesRes.sources.filter(s => s.is_active);
            this.episodeData = sourcesRes.episode || { title: 'Épisode' };
            
            if (this.sources.length === 0) {
                throw new Error('Aucune source active');
            }

            this.renderPlayer();
            this.renderSources();
        } catch (error) {
            console.error('Erreur loadEpisode:', error);
            throw error;
        }
    }

    async loadMovie(showId) {
        try {
            const showRes = await api.getShow(showId);
            
            if (!showRes || !showRes.data) {
                throw new Error('Film introuvable');
            }

            this.showData = showRes.data;
            const episodesRes = await api.getShowEpisodes(showId);
            
            console.log('Episodes response:', episodesRes);

            if (episodesRes.type === 'movie') {
                if (episodesRes.sources && episodesRes.sources.length > 0) {
                    this.sources = episodesRes.sources.filter(s => s.is_active);
                } else {
                    throw new Error('Aucune source disponible');
                }
            } else if (episodesRes.seasons && episodesRes.seasons.length > 0) {
                const firstEpisode = episodesRes.seasons[0].episodes[0];
                window.location.href = `player.html?episode=${firstEpisode.id}`;
                return;
            }

            if (this.sources.length === 0) {
                throw new Error('Aucune source active');
            }

            this.renderPlayer();
            this.renderSources();
            
        } catch (error) {
            console.error('Erreur loadMovie:', error);
            throw error;
        }
    }

    renderPlayer() {
        const title = this.episodeData?.title || this.showData?.title || 'Lecture';
        const subtitle = this.episodeData ? 
            `S${this.episodeData.season_number || '?'}E${this.episodeData.episode_number || '?'}` : 
            'Film';

        const titleEl = document.querySelector('.player-title');
        const metaEl = document.querySelector('.player-meta');
        
        if (titleEl) titleEl.textContent = title;
        if (metaEl) metaEl.textContent = subtitle;

        if (this.sources.length > 0) {
            const preferred = this.sources.find(s => s.server === 'filemoon') || this.sources[0];
            this.selectSource(preferred.id);
        }
    }

    selectSource(sourceId) {
        const source = this.sources.find(s => s.id === sourceId);
        if (!source) return;

        this.currentSource = source;
        
        document.querySelectorAll('.server-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sourceId === sourceId);
        });

        this.loadVideo(source);
    }

    loadVideo(source) {
        const container = document.getElementById('playerContainer');
        const loading = document.getElementById('playerLoading');
        const error = document.getElementById('playerError');
        
        if (!container) return;

        if (loading) loading.classList.remove('active');
        if (error) error.classList.remove('active');
        
        console.log('Chargement source:', source);

        if (source.server === 'filemoon' && source.embed_url) {
            container.innerHTML = `
                <iframe 
                    src="${source.embed_url}" 
                    width="100%" 
                    height="100%" 
                    frameborder="0" 
                    allowfullscreen
                    allow="autoplay; encrypted-media; picture-in-picture"
                    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                ></iframe>
            `;
        } else if (source.direct_link) {
            const posterUrl = this.episodeData?.thumbnail || this.showData?.poster_url || '';
            
            container.innerHTML = `
                <video 
                    id="videoPlayer" 
                    class="video-element"
                    controls
                    autoplay
                    preload="metadata"
                    poster="${posterUrl}"
                    style="width: 100%; height: 100%; background: #000;"
                >
                    <source src="${source.direct_link}" type="video/mp4">
                    Votre navigateur ne supporte pas la lecture vidéo.
                </video>
            `;
            
            this.setupVideoControls();
        } else {
            this.showError('Source invalide');
        }
    }

    setupVideoControls() {
        const video = document.getElementById('videoPlayer');
        if (!video) return;

        const saveKey = `progress_${this.episodeId || this.showId}`;
        
        video.addEventListener('timeupdate', () => {
            if (video.currentTime > 0) {
                localStorage.setItem(saveKey, video.currentTime);
            }
        });

        video.addEventListener('loadedmetadata', () => {
            const saved = localStorage.getItem(saveKey);
            if (saved && video.duration - parseFloat(saved) > 10) {
                video.currentTime = parseFloat(saved);
            }
        });

        video.addEventListener('error', (e) => {
            console.error('Erreur vidéo:', e);
            this.showError('Erreur de lecture. Essayez un autre serveur.');
        });
    }

    renderSources() {
        const container = document.getElementById('serverButtons');
        if (!container || this.sources.length === 0) return;

        container.innerHTML = this.sources.map(source => {
            const serverName = source.server === 'filemoon' ? 'Filemoon' : 
                              source.server === 'telegram' ? 'Telegram' : 'Serveur';
            
            const serverIcon = source.server === 'filemoon' ? 'cloud' : 'paper-plane';

            return `
                <button 
                    class="server-btn ${source.id === this.currentSource?.id ? 'active' : ''}" 
                    data-source-id="${source.id}"
                    onclick="window.playerInstance.selectSource('${source.id}')"
                >
                    <i class="fas fa-${serverIcon}"></i>
                    <div>
                        <div class="server-name">${serverName}</div>
                        <div class="server-quality">${source.quality || 'HD'}</div>
                    </div>
                </button>
            `;
        }).join('');
    }

    showLoading(show) {
        const loading = document.getElementById('playerLoading');
        if (loading) loading.classList.toggle('active', show);
    }

    showError(message) {
        const error = document.getElementById('playerError');
        const loading = document.getElementById('playerLoading');
        
        if (loading) loading.classList.remove('active');
        
        if (error) {
            error.classList.add('active');
            const errorText = error.querySelector('p');
            if (errorText) errorText.textContent = message;
        }
    }
}

window.playerInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    window.playerInstance = new PlayerPage();
});
