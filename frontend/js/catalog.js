// frontend/js/catalog.js
/**
 * Logique spécifique au catalogue - VERSION NETFLIX
 * Recherche de SÉRIES/FILMS (dossiers) pas d'épisodes individuels
 */

import api from './api.js';
import { createMovieCard, showToast, handleApiError, debounce } from './utils.js';

class CatalogManager {
    constructor() {
        this.filters = {
            type: 'all',        // 'all', 'movie', 'tv'
            genre: null,
            year: null,
            rating: 0,
            query: ''
        };
        this.page = 1;
        this.isLoading = false;
        this.init();
    }
    
    init() {
        this.loadSeries();
        this.initInfiniteScroll();
        this.initFilters();
    }
    
    /**
     * ✅ NOUVEAU: Charge les SÉRIES/FILMS (dossiers) pas les épisodes
     */
    async loadSeries(append = false) {
        if (this.isLoading) return;
        this.isLoading = true;
        
        try {
            const result = await api.searchFolders(this.filters.query, {
                type: this.filters.type === 'all' ? null : this.filters.type,
                genre: this.filters.genre,
                year: this.filters.year,
                limit: 20
            });
            
            this.renderSeriesCards(result.results || [], append);
            this.updateResultsCount(result.count || 0);
            
        } catch (error) {
            handleApiError(error);
        } finally {
            this.isLoading = false;
        }
    }
    
    /**
     * ✅ NOUVEAU: Rend les cartes de SÉRIES (pas d'épisodes)
     */
    renderSeriesCards(series, append = false) {
        const grid = document.getElementById('catalog-grid');
        if (!grid) return;
        
        // Retirer les skeletons si première charge
        if (!append) {
            grid.innerHTML = '';
        }
        
        if (!series || series.length === 0) {
            if (!append) {
                grid.innerHTML = `
                    <div class="empty-catalog">
                        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                        <h3>Aucun résultat trouvé</h3>
                        <p>Essayez de modifier vos filtres ou votre recherche</p>
                    </div>
                `;
            }
            return;
        }
        
        series.forEach((item, index) => {
            const card = this.createSeriesCard(item, index);
            if (card) {
                grid.appendChild(card);
            }
        });
    }
    
    /**
     * ✅ NOUVEAU: Crée une carte de SÉRIE/FILM (redirige vers details.html)
     */
    createSeriesCard(series, index) {
        const card = document.createElement('div');
        card.className = 'series-card';
        card.style.animationDelay = `${index * 0.05}s`;
        
        const posterUrl = series.poster_url || series.poster_url_small || '/img/default-poster.png';
        const title = series.title || series.folder_name;
        const isSeries = series.has_subfolders || series.season_count > 0;
        
        card.innerHTML = `
            <div class="card-image">
                <img src="${posterUrl}" alt="${escapeHtml(title)}" loading="lazy">
                <div class="card-overlay">
                    <button class="info-btn">
                        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                    </button>
                </div>
                ${isSeries ? '<span class="series-badge">SÉRIE</span>' : '<span class="movie-badge">FILM</span>'}
            </div>
            <div class="card-content">
                <h3 class="card-title">${escapeHtml(title)}</h3>
                <div class="card-meta">
                    ${series.year ? `<span class="card-year">${series.year}</span>` : ''}
                    ${series.rating ? `<span class="card-rating">⭐ ${series.rating.toFixed(1)}</span>` : ''}
                    ${isSeries ? `<span class="card-episodes">${series.total_episodes || 0} épisodes</span>` : ''}
                </div>
                ${series.genres ? `<div class="card-genres">${series.genres.slice(0, 3).join(' • ')}</div>` : ''}
            </div>
        `;
        
        // ✅ Redirection vers la page de détails (pas le player directement)
        card.addEventListener('click', () => {
            window.location.href = `details.html?id=${series.id}`;
        });
        
        return card;
    }
    
    updateResultsCount(total) {
        const el = document.getElementById('results-total');
        if (el) {
            el.textContent = total.toLocaleString();
        }
    }
    
    initInfiniteScroll() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.isLoading) {
                    this.page++;
                    this.loadSeries(true);
                }
            });
        }, { rootMargin: '100px' });
        
        const sentinel = document.createElement('div');
        sentinel.id = 'scroll-sentinel';
        sentinel.style.height = '10px';
        document.getElementById('catalog-grid')?.appendChild(sentinel);
        observer.observe(sentinel);
    }
    
    initFilters() {
        // Filtre type (Film/Série/Tout)
        document.querySelectorAll('.filter-type').forEach(chip => {
            chip.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-type').forEach(c => c.classList.remove('active'));
                e.target.classList.add('active');
                
                const type = e.target.dataset.type; // 'all', 'movie', 'tv'
                this.updateFilter('type', type);
            });
        });
        
        // Recherche
        const searchInput = document.getElementById('catalog-search');
        if (searchInput) {
            searchInput.addEventListener('input', debounce((e) => {
                this.updateFilter('query', e.target.value);
            }, 300));
        }
    }
    
    updateFilter(key, value) {
        this.filters[key] = value;
        this.page = 1;
        this.loadSeries();
    }
}

// Initialiser
document.addEventListener('DOMContentLoaded', () => {
    window.catalogManager = new CatalogManager();
});

// Helper
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
