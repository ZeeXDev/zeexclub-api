/**
 * Page Catalogue - Grille de films/séries avec filtres
 */

import api from './api.js';
import { APP_CONFIG } from './config.js';

class CatalogPage {
    constructor() {
        this.currentPage = 1;
        this.totalPages = 1;
        this.currentFilters = {};
        this.isLoading = false;
        
        this.init();
    }

    init() {
        this.parseUrlParams();
        this.setupFilters();
        this.loadCatalog();
        this.setupEventListeners();
    }

    parseUrlParams() {
        const params = new URLSearchParams(window.location.search);
        
        this.currentFilters = {
            type: params.get('type') || null,
            genre: params.get('genre') || null,
            year: params.get('year') || null,
            search: params.get('search') || null,
            trending: params.get('trending') === 'true',
            recent: params.get('recent') === 'true'
        };

        // Mise à jour titre
        this.updatePageTitle();
    }

    updatePageTitle() {
        const title = document.querySelector('.catalog-title');
        if (!title) return;

        if (this.currentFilters.search) {
            title.textContent = `Résultats pour "${this.currentFilters.search}"`;
        } else if (this.currentFilters.type === 'movie') {
            title.textContent = 'Films';
        } else if (this.currentFilters.type === 'series') {
            title.textContent = 'Séries';
        } else if (this.currentFilters.trending) {
            title.textContent = 'Tendances';
        } else if (this.currentFilters.recent) {
            title.textContent = 'Nouveautés';
        } else {
            title.textContent = 'Catalogue';
        }
    }

    setupFilters() {
        // Remplir les filtres si nécessaire
        this.loadGenres();
    }

    async loadGenres() {
        try {
            const response = await api.getGenres();
            const genres = response.data || [];
            
            // Peupler le dropdown de genres si présent
            const genreSelect = document.getElementById('genreFilter');
            if (genreSelect) {
                genreSelect.innerHTML = '<option value="">Tous les genres</option>' +
                    genres.map(g => `<option value="${g.name}">${g.name}</option>`).join('');
                
                if (this.currentFilters.genre) {
                    genreSelect.value = this.currentFilters.genre;
                }
            }
        } catch (error) {
            console.error('Erreur chargement genres:', error);
        }
    }

    async loadCatalog() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading(true);

        try {
            let response;

            if (this.currentFilters.search) {
                response = await api.searchShows(
                    this.currentFilters.search, 
                    this.currentFilters.type
                );
            } else if (this.currentFilters.trending) {
                response = await api.getTrending(
                    this.currentFilters.type || 'all', 
                    'week'
                );
                response = { data: response.data }; // Normalisation
            } else if (this.currentFilters.recent) {
                response = await api.getRecent(this.currentFilters.type);
            } else {
                const params = {
                    page: this.currentPage,
                    limit: APP_CONFIG.itemsPerPage,
                    ...this.currentFilters
                };
                response = await api.getShows(params);
            }

            const shows = response.data || [];
            this.totalPages = response.pagination?.total_pages || 1;
            
            this.renderGrid(shows);
            this.renderPagination();
            
        } catch (error) {
            console.error('Erreur chargement catalogue:', error);
            this.showError('Impossible de charger le catalogue');
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }

    renderGrid(shows) {
        const grid = document.getElementById('catalogGrid');
        if (!grid) return;

        if (shows.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1/-1;">
                    <i class="fas fa-film"></i>
                    <h3>Aucun résultat</h3>
                    <p>Essayez d'autres critères de recherche</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = shows.map(show => this.createCatalogCard(show)).join('');
    }

    createCatalogCard(show) {
        const imageUrl = api.getImageUrl(show.poster_path, APP_CONFIG.posterSize);
        const year = show.release_date ? new Date(show.release_date).getFullYear() : 'N/A';
        const typeLabel = show.type === 'movie' ? 'Film' : 'Série';
        
        return `
            <div class="movie-card catalog-card" data-id="${show.id}">
                <img src="${imageUrl}" alt="${show.title}" class="movie-poster" loading="lazy">
                <div class="movie-info">
                    <span class="catalog-type">${typeLabel}</span>
                    <h3 class="movie-title">${show.title}</h3>
                    <div class="movie-meta">
                        <span>${year}</span>
                        ${show.rating ? `<span class="movie-rating"><i class="fas fa-star"></i> ${show.rating.toFixed(1)}</span>` : ''}
                    </div>
                </div>
                <a href="details.html?id=${show.id}" class="card-link"></a>
            </div>
        `;
    }

    renderPagination() {
        const container = document.getElementById('pagination');
        if (!container || this.totalPages <= 1) {
            if (container) container.innerHTML = '';
            return;
        }

        let html = '';
        
        // Bouton précédent
        if (this.currentPage > 1) {
            html += `<button class="page-btn" onclick="catalog.goToPage(${this.currentPage - 1})">
                <i class="fas fa-chevron-left"></i>
            </button>`;
        }

        // Pages
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(this.totalPages, this.currentPage + 2);

        if (startPage > 1) {
            html += `<button class="page-btn" onclick="catalog.goToPage(1)">1</button>`;
            if (startPage > 2) html += `<span class="page-dots">...</span>`;
        }

        for (let i = startPage; i <= endPage; i++) {
            const active = i === this.currentPage ? 'active' : '';
            html += `<button class="page-btn ${active}" onclick="catalog.goToPage(${i})">${i}</button>`;
        }

        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) html += `<span class="page-dots">...</span>`;
            html += `<button class="page-btn" onclick="catalog.goToPage(${this.totalPages})">${this.totalPages}</button>`;
        }

        // Bouton suivant
        if (this.currentPage < this.totalPages) {
            html += `<button class="page-btn" onclick="catalog.goToPage(${this.currentPage + 1})">
                <i class="fas fa-chevron-right"></i>
            </button>`;
        }

        container.innerHTML = html;
    }

    goToPage(page) {
        this.currentPage = page;
        this.loadCatalog();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    setupEventListeners() {
        // Filtres
        const typeFilter = document.getElementById('typeFilter');
        const genreFilter = document.getElementById('genreFilter');
        const yearFilter = document.getElementById('yearFilter');
        const sortFilter = document.getElementById('sortFilter');

        const applyFilters = () => {
            this.currentFilters.type = typeFilter?.value || null;
            this.currentFilters.genre = genreFilter?.value || null;
            this.currentFilters.year = yearFilter?.value || null;
            this.currentPage = 1;
            this.loadCatalog();
        };

        typeFilter?.addEventListener('change', applyFilters);
        genreFilter?.addEventListener('change', applyFilters);
        yearFilter?.addEventListener('change', applyFilters);
        sortFilter?.addEventListener('change', () => {
            // Implémenter le tri
            this.loadCatalog();
        });
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.classList.toggle('active', show);
        }
    }

    showError(message) {
        const grid = document.getElementById('catalogGrid');
        if (grid) {
            grid.innerHTML = `
                <div class="error-container" style="grid-column: 1/-1;">
                    <div class="error-code"><i class="fas fa-exclamation-triangle"></i></div>
                    <p class="error-message">${message}</p>
                    <button class="btn btn-primary" onclick="location.reload()">Réessayer</button>
                </div>
            `;
        }
    }
}

// Initialisation
let catalog;
document.addEventListener('DOMContentLoaded', () => {
    catalog = new CatalogPage();
});
