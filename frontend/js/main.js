/**
 * Script principal ZeeXClub - Page d'accueil
 */

import api from './api.js';
import { APP_CONFIG } from './config.js';

class ZeeXApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupNavigation();
        this.loadHero();
        this.loadSections();
        this.setupEventListeners();
        this.setupSearch();
    }

    /**
     * Navigation scroll effect
     */
    setupNavigation() {
        const navbar = document.querySelector('.navbar');
        
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });

        // Mobile menu
        const mobileBtn = document.getElementById('mobileMenuBtn');
        const navLinks = document.getElementById('navLinks');
        
        if (mobileBtn) {
            mobileBtn.addEventListener('click', () => {
                navLinks.classList.toggle('active');
            });
        }
    }

    /**
     * Charge le hero avec un show aléatoire/populaire
     */
    async loadHero() {
        try {
            const response = await api.getTrending('all', 'week');
            const shows = response.data || [];
            
            if (shows.length === 0) return;
            
            // Sélection aléatoire parmi les 5 premiers
            const heroShow = shows[Math.floor(Math.random() * Math.min(5, shows.length))];
            
            this.renderHero(heroShow);
            
        } catch (error) {
            console.error('Erreur chargement hero:', error);
        }
    }

    renderHero(show) {
        const backdrop = document.getElementById('heroBackdrop');
        const title = document.getElementById('heroTitle');
        const meta = document.getElementById('heroMeta');
        const description = document.getElementById('heroDescription');
        const badge = document.getElementById('heroBadge');
        const playBtn = document.getElementById('heroPlay');
        const moreInfoBtn = document.getElementById('heroMoreInfo');

        if (backdrop) {
            const imageUrl = api.getImageUrl(show.backdrop_path || show.poster_path, 'original');
            backdrop.style.backgroundImage = `url(${imageUrl})`;
        }

        if (title) title.textContent = show.title;
        
        if (meta) {
            const year = show.release_date ? new Date(show.release_date).getFullYear() : 'N/A';
            const rating = show.rating ? `<span class="rating"><i class="fas fa-star"></i> ${show.rating.toFixed(1)}</span>` : '';
            const type = show.type === 'movie' ? 'Film' : 'Série';
            meta.innerHTML = `${rating} <span>${year}</span> <span>${type}</span>`;
        }

        if (description) {
            description.textContent = show.overview || 'Aucun synopsis disponible.';
        }

        if (badge) {
            badge.textContent = show.type === 'movie' ? 'Nouveau Film' : 'Nouvelle Série';
        }

        // Boutons
        if (playBtn) {
            playBtn.href = `details.html?id=${show.id}`;
            playBtn.onclick = (e) => {
                e.preventDefault();
                window.location.href = `player.html?show=${show.id}`;
            };
        }

        if (moreInfoBtn) {
            moreInfoBtn.onclick = () => {
                window.location.href = `details.html?id=${show.id}`;
            };
        }
    }

    /**
     * Charge toutes les sections (sliders)
     */
    async loadSections() {
        await Promise.all([
            this.loadTrending(),
            this.loadRecent(),
            this.loadMovies(),
            this.loadSeries()
        ]);
    }

    async loadTrending() {
        try {
            const response = await api.getTrending('all', 'week');
            this.renderSlider('trendingContainer', response.data || []);
        } catch (error) {
            console.error('Erreur tendances:', error);
        }
    }

    async loadRecent() {
        try {
            const response = await api.getRecent();
            this.renderSlider('recentContainer', response.data || []);
        } catch (error) {
            console.error('Erreur nouveautés:', error);
        }
    }

    async loadMovies() {
        try {
            const response = await api.getShows({ type: 'movie', limit: 15 });
            this.renderSlider('moviesContainer', response.data || []);
        } catch (error) {
            console.error('Erreur films:', error);
        }
    }

    async loadSeries() {
        try {
            const response = await api.getShows({ type: 'series', limit: 15 });
            this.renderSlider('seriesContainer', response.data || []);
        } catch (error) {
            console.error('Erreur séries:', error);
        }
    }

    renderSlider(containerId, shows) {
        const container = document.getElementById(containerId);
        if (!container || shows.length === 0) return;

        container.innerHTML = shows.map(show => this.createMovieCard(show)).join('');
        
        // Ajout des event listeners sur les cartes
        container.querySelectorAll('.movie-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.movie-actions')) {
                    const showId = card.dataset.id;
                    window.location.href = `details.html?id=${showId}`;
                }
            });
        });
    }

    createMovieCard(show) {
        const imageUrl = api.getImageUrl(show.poster_path, APP_CONFIG.posterSize);
        const year = show.release_date ? new Date(show.release_date).getFullYear() : 'N/A';
        const rating = show.rating ? `<span class="movie-rating"><i class="fas fa-star"></i> ${show.rating.toFixed(1)}</span>` : '';
        
        return `
            <div class="movie-card" data-id="${show.id}">
                <img src="${imageUrl}" alt="${show.title}" class="movie-poster" loading="lazy">
                <div class="movie-info">
                    <h3 class="movie-title">${show.title}</h3>
                    <div class="movie-meta">
                        ${rating}
                        <span>${year}</span>
                    </div>
                    <div class="movie-actions">
                        <button class="play-btn" onclick="window.location.href='player.html?show=${show.id}'">
                            <i class="fas fa-play"></i>
                        </button>
                        <button onclick="addToList('${show.id}')">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button onclick="window.location.href='details.html?id=${show.id}'">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Défilement des sliders
     */
    scrollSlider(sliderId, direction) {
        const slider = document.getElementById(sliderId.replace('Slider', 'Container'));
        if (!slider) return;
        
        const scrollAmount = slider.clientWidth * 0.8;
        slider.scrollBy({
            left: direction * scrollAmount,
            behavior: 'smooth'
        });
    }

    /**
     * Recherche
     */
    setupSearch() {
        const searchInput = document.getElementById('searchInput');
        const searchBtn = document.getElementById('searchBtn');

        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.performSearch(searchInput.value);
                }
            });
        }

        if (searchBtn) {
            searchBtn.addEventListener('click', () => {
                if (searchInput) {
                    this.performSearch(searchInput.value);
                }
            });
        }
    }

    performSearch(query) {
        if (query.trim()) {
            window.location.href = `catalog.html?search=${encodeURIComponent(query)}`;
        }
    }

    setupEventListeners() {
        // Gestion des erreurs d'images
        document.addEventListener('error', (e) => {
            if (e.target.tagName === 'IMG') {
                e.target.src = '/img/default-poster.png';
            }
        }, true);
    }
}

// Fonctions globales
window.scrollSlider = (sliderId, direction) => {
    const app = new ZeeXApp();
    app.scrollSlider(sliderId, direction);
};

window.addToList = (showId) => {
    // Implémentation "Ma Liste" (localStorage ou API)
    let myList = JSON.parse(localStorage.getItem('myList') || '[]');
    
    if (!myList.includes(showId)) {
        myList.push(showId);
        localStorage.setItem('myList', JSON.stringify(myList));
        showToast('Ajouté à Ma Liste', 'success');
    } else {
        showToast('Déjà dans Ma Liste', 'warning');
    }
};

window.showToast = (message, type = 'info') => {
    const container = document.querySelector('.toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
};

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    new ZeeXApp();
});
