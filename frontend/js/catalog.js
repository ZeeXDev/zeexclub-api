// frontend/js/catalog.js
/**
 * Logique spécifique au catalogue
 */

import api from './api.js';
import { createMovieCard, showToast, handleApiError, debounce } from './utils.js';

class CatalogManager {
    constructor() {
        this.filters = {
            category: 'all',
            type: 'all',
            year: 'all',
            quality: 'all',
            rating: 0,
            genres: [],
            sort: 'popularity',
            query: ''
        };
        this.page = 1;
        this.isLoading = false;
        this.init();
    }
    
    init() {
        this.loadMovies();
        this.initInfiniteScroll();
        this.initFilters();
    }
    
    async loadMovies(append = false) {
        if (this.isLoading) return;
        this.isLoading = true;
        
        try {
            // ✅ CORRECTION: Utiliser la bonne fonction API
            const response = await api.getMovies({
                ...this.filters,
                page: this.page,
                limit: 20
            });
            
            this.renderMovies(response.data || [], append);
            this.updateResultsCount(response.total || (response.data || []).length);
            
        } catch (error) {
            handleApiError(error);
        } finally {
            this.isLoading = false;
        }
    }
    
    renderMovies(movies, append = false) {
        const grid = document.getElementById('catalog-grid');
        if (!grid) return;
        
        // Retirer les skeletons si première charge
        if (!append) {
            grid.innerHTML = '';
        }
        
        if (!movies || movies.length === 0) {
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
        
        // ✅ CORRECTION: Utiliser createMovieCard correctement (HTMLElement)
        movies.forEach((movie, index) => {
            const card = createMovieCard(movie, {
                onClick: () => {
                    window.location.href = `player.html?id=${movie.id}`;
                }
            });
            
            if (card) {
                card.style.animationDelay = `${index * 0.05}s`;
                grid.appendChild(card);
            }
        });
    }
    
    updateResultsCount(total) {
        const el = document.getElementById('results-total');
        if (el) {
            // Animation du compteur
            const start = parseInt(el.textContent.replace(/[^\d]/g, '')) || 0;
            const end = total || 0;
            const duration = 500;
            const startTime = performance.now();
            
            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easeProgress = 1 - Math.pow(1 - progress, 3);
                const current = Math.round(start + (end - start) * easeProgress);
                
                el.textContent = current.toLocaleString();
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            };
            
            requestAnimationFrame(animate);
        }
    }
    
    initInfiniteScroll() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.isLoading) {
                    this.page++;
                    this.loadMovies(true);
                }
            });
        }, { rootMargin: '100px' });
        
        // Observer un élément sentinelle à la fin de la grille
        const sentinel = document.createElement('div');
        sentinel.id = 'scroll-sentinel';
        sentinel.style.height = '10px';
        document.getElementById('catalog-grid')?.appendChild(sentinel);
        observer.observe(sentinel);
    }
    
    initFilters() {
        // Initialiser les écouteurs de filtres
        document.querySelectorAll('.filter-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
                e.target.classList.add('active');
                
                const filterType = e.target.dataset.filter;
                this.updateFilter('type', filterType === 'all' ? null : filterType);
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
        this.loadMovies();
    }
}

// Initialiser
document.addEventListener('DOMContentLoaded', () => {
    window.catalogManager = new CatalogManager();
});
