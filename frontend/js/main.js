// frontend/js/main.js
/**
 * Point d'entrée principal de l'application ZeeXClub
 * Gère l'initialisation, la navigation, et les interactions globales
 */

import { initAuth, signOut } from './auth.js';
import api from './api.js';
import { 
    createMovieCard, 
    showLoading, 
    hideLoading, 
    showToast,
    handleApiError,
    debounce,
    formatDate,
    formatDuration
} from './utils.js';

// État global de l'application.
const AppState = {
    currentUser: null,
    isLoading: false,
    currentSection: 'home',
    searchQuery: '',
    heroSlides: [],
    currentSlide: 0
};

/**
 * Initialisation au chargement du DOM
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🎬 ZeeXClub initializing...');
    
    try {
        // Initialiser l'authentification
        await initAuth();
        
        // Initialiser les composants UI
        initHeaderScroll();
        initSearch();
        initButtonHandlers();
        initSmoothScroll();
        
        // Charger le contenu selon la page
        await loadPageContent();
        
        // Initialiser la navigation bas si présente
        if (window.bottomNav) {
            window.bottomNav.updateAuthState();
        }
        
        console.log('✅ ZeeXClub ready');
    } catch (error) {
        console.error('❌ Initialization error:', error);
        showToast('Erreur de chargement', 'error');
    }
});

/**
 * Charge le contenu selon la page actuelle
 */
async function loadPageContent() {
    const path = window.location.pathname;
    const page = path.split('/').pop() || 'index.html';
    
    switch(page) {
        case 'index.html':
        case '':
        case '/':
            await loadHomePage();
            break;
        case 'catalog.html':
            await loadCatalogPage();
            break;
        case 'trending.html':
            await loadTrendingPage();
            break;
        case 'mylist.html':
            await loadMyListPage();
            break;
        case 'profile.html':
            await loadProfilePage();
            break;
        case 'player.html':
            // Le player gère son propre chargement
            break;
    }
}

/**
 * Charge la page d'accueil
 */
async function loadHomePage() {
    showLoading();
    
    try {
        // ✅ CORRECTION: Utiliser les bonnes fonctions API
        const [recentResponse, trendingResponse] = await Promise.all([
            api.getRecentVideos(12),
            api.getTrending(12)
        ]);
        
        // Rendre les sections
        // ✅ CORRECTION: createMovieCard retourne un HTMLElement, pas une string
        renderSectionCards('new-grid', recentResponse.data || [], 'Aucun film récent');
        renderSectionCards('trending-grid', trendingResponse.data || [], 'Aucune tendance');
        
        // Initialiser le slider hero
        initHeroSlider((recentResponse.data || []).slice(0, 5));
        
    } catch (error) {
        console.error('Error loading home:', error);
        handleApiError(error);
    } finally {
        hideLoading();
    }
}

/**
 * ✅ CORRECTION: Rend une section avec createMovieCard (HTMLElement)
 */
function renderSectionCards(gridId, movies, emptyMessage) {
    const grid = document.getElementById(gridId);
    if (!grid) return;
    
    if (!movies || movies.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <p>${emptyMessage}</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = '';
    
    movies.forEach((movie, index) => {
        const card = createMovieCard(movie, { 
            delay: index * 0.1,
            onClick: () => navigateToPlayer(movie.id)
        });
        
        if (card) {
            card.style.animationDelay = `${index * 0.1}s`;
            grid.appendChild(card);
        }
    });
}

/**
 * ✅ CORRECTION: Rend une section avec HTML string (pour compatibilité)
 */
function renderSection(gridId, movies, emptyMessage) {
    const grid = document.getElementById(gridId);
    if (!grid) return;
    
    if (!movies || movies.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <p>${emptyMessage}</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = movies.map((movie, index) => `
        <div class="movie-card" style="animation-delay: ${index * 0.1}s" data-id="${movie.id}">
            <div class="card-image">
                <img src="${movie.poster_url || '/img/default-poster.png'}" alt="${movie.title}" loading="lazy">
                <div class="card-overlay">
                    <button class="play-btn">
                        <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </button>
                </div>
            </div>
            <div class="card-content">
                <h3 class="card-title">${movie.title}</h3>
                ${movie.year ? `<span class="card-year">${movie.year}</span>` : ''}
                ${movie.rating ? `<span class="card-rating">⭐ ${movie.rating.toFixed(1)}</span>` : ''}
            </div>
        </div>
    `).join('');
    
    // Ajouter les événements de clic
    grid.querySelectorAll('.movie-card').forEach((card) => {
        card.addEventListener('click', () => {
            const movieId = card.dataset.id;
            navigateToPlayer(movieId);
        });
    });
}

/**
 * Initialise le slider hero
 */
function initHeroSlider(slides = []) {
    if (slides.length === 0) return;
    
    AppState.heroSlides = slides;
    const heroSection = document.querySelector('.hero-section');
    if (!heroSection) return;
    
    let currentIndex = 0;
    let autoSlideInterval;
    
    // Mettre à jour le contenu
    function updateSlide(index) {
        const slide = slides[index];
        currentIndex = index;
        
        // Mettre à jour l'image de fond
        const bgImg = heroSection.querySelector('.hero-bg img');
        if (bgImg && slide.backdrop_url) {
            bgImg.src = slide.backdrop_url;
            bgImg.alt = slide.title;
        }
        
        // Mettre à jour le texte
        const titleEl = heroSection.querySelector('.hero-title');
        const synopsisEl = heroSection.querySelector('.hero-synopsis');
        const metaEl = heroSection.querySelector('.hero-meta');
        const ctaBtn = heroSection.querySelector('.btn-hero-primary');
        
        if (titleEl) {
            titleEl.style.opacity = '0';
            titleEl.style.transform = 'translateY(20px)';
            setTimeout(() => {
                titleEl.textContent = slide.title;
                titleEl.style.opacity = '1';
                titleEl.style.transform = 'translateY(0)';
            }, 300);
        }
        
        if (synopsisEl) {
            synopsisEl.textContent = slide.description || '';
        }
        
        if (metaEl) {
            metaEl.innerHTML = `
                <span class="hero-rating">★ ${slide.rating || 'N/A'}</span>
                <span>${slide.year || ''}</span>
                <span>${slide.duration ? formatDuration(slide.duration) : ''}</span>
                <span class="hero-badge">${(slide.genre || [])[0] || 'Action'}</span>
            `;
        }
        
        if (ctaBtn) {
            ctaBtn.onclick = () => navigateToPlayer(slide.id);
        }
        
        // Mettre à jour les indicateurs
        document.querySelectorAll('.hero-dot').forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
        });
    }
    
    // Navigation
    function nextSlide() {
        const next = (currentIndex + 1) % slides.length;
        updateSlide(next);
    }
    
    function prevSlide() {
        const prev = (currentIndex - 1 + slides.length) % slides.length;
        updateSlide(prev);
    }
    
    // Auto-slide
    function startAutoSlide() {
        autoSlideInterval = setInterval(nextSlide, 6000);
    }
    
    function stopAutoSlide() {
        clearInterval(autoSlideInterval);
    }
    
    // Événements
    const nextBtn = document.querySelector('.hero-nav.next');
    const prevBtn = document.querySelector('.hero-nav.prev');
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            stopAutoSlide();
            nextSlide();
            startAutoSlide();
        });
    }
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            stopAutoSlide();
            prevSlide();
            startAutoSlide();
        });
    }
    
    // Dots
    document.querySelectorAll('.hero-dot').forEach((dot, index) => {
        dot.addEventListener('click', () => {
            stopAutoSlide();
            updateSlide(index);
            startAutoSlide();
        });
    });
    
    // Pause au survol
    heroSection.addEventListener('mouseenter', stopAutoSlide);
    heroSection.addEventListener('mouseleave', startAutoSlide);
    
    // Touch swipe
    let touchStartX = 0;
    heroSection.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
    }, { passive: true });
    
    heroSection.addEventListener('touchend', (e) => {
        const touchEndX = e.changedTouches[0].clientX;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > 50) {
            stopAutoSlide();
            if (diff > 0) nextSlide();
            else prevSlide();
            startAutoSlide();
        }
    }, { passive: true });
    
    // Initialiser avec le premier slide
    updateSlide(0);
    startAutoSlide();
}

/**
 * Gestionnaire global de boutons
 */
function initButtonHandlers() {
    // Délégation d'événements pour tous les boutons
    document.addEventListener('click', async (e) => {
        const btn = e.target.closest('button, a, [role="button"]');
        if (!btn) return;
        
        // Bouton "Regarder"
        if (btn.matches('.btn-hero-primary, .btn-play, [data-action="play"]')) {
            e.preventDefault();
            const videoId = btn.dataset.id || btn.closest('[data-id]')?.dataset.id;
            if (videoId) navigateToPlayer(videoId);
        }
        
        // Bouton "Ajouter à ma liste"
        if (btn.matches('.btn-hero-icon, .btn-watchlist, [data-action="add-to-list"]')) {
            e.preventDefault();
            const videoId = btn.dataset.id || btn.closest('[data-id]')?.dataset.id;
            if (videoId) await addToList(videoId, btn);
        }
        
        // Bouton "Bande-annonce"
        if (btn.matches('[data-action="trailer"], .btn-trailer')) {
            e.preventDefault();
            const videoId = btn.dataset.id;
            if (videoId) showTrailer(videoId);
        }
        
        // Bouton "Voir épisodes"
        if (btn.matches('[data-action="episodes"], .btn-episodes')) {
            e.preventDefault();
            const seriesId = btn.dataset.id;
            if (seriesId) showEpisodes(seriesId);
        }
        
        // Bouton "Partager"
        if (btn.matches('[data-action="share"], .btn-share')) {
            e.preventDefault();
            await shareContent();
        }
        
        // Bouton "Favoris"
        if (btn.matches('.btn-favorite, [data-action="favorite"]')) {
            e.preventDefault();
            const videoId = btn.dataset.id;
            if (videoId) toggleFavorite(videoId, btn);
        }
        
        // Bouton "Retirer de la liste"
        if (btn.matches('.btn-remove, [data-action="remove"]')) {
            e.preventDefault();
            const videoId = btn.dataset.id;
            if (videoId) await removeFromList(videoId, btn);
        }
        
        // Bouton "Charger plus"
        if (btn.matches('.btn-load-more, [data-action="load-more"]')) {
            e.preventDefault();
            await loadMoreContent(btn);
        }
        
        // Bouton "Fermer modal"
        if (btn.matches('.modal-close, [data-action="close-modal"]')) {
            e.preventDefault();
            closeModal();
        }
        
        // Bouton "Recherche"
        if (btn.matches('#search-toggle, [data-action="search"]')) {
            e.preventDefault();
            toggleSearch();
        }
        
        // Bouton "Menu utilisateur"
        if (btn.matches('#user-menu-toggle, [data-action="user-menu"]')) {
            e.preventDefault();
            toggleUserMenu();
        }
        
        // Bouton "Déconnexion"
        if (btn.matches('[data-action="logout"], .btn-logout')) {
            e.preventDefault();
            await handleLogout();
        }
    });
    
    // Fermer les menus au clic extérieur
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.user-menu-wrapper')) {
            closeUserMenu();
        }
        if (!e.target.closest('.search-wrapper')) {
            closeSearch();
        }
    });
}

/**
 * Navigation vers le lecteur
 */
function navigateToPlayer(videoId) {
    if (!videoId) return;
    
    // Animation de transition
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    
    setTimeout(() => {
        window.location.href = `player.html?id=${videoId}`;
    }, 300);
}

/**
 * Ajoute à la liste de lecture
 */
async function addToList(videoId, btn) {
    if (!videoId) return;
    
    // Animation du bouton
    animateButton(btn);
    
    // Feedback visuel immédiat
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#10B981" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    btn.style.color = '#10B981';
    
    try {
        await api.addToWatchlist(videoId);
        showToast('Ajouté à votre liste !', 'success');
        
        // Mettre à jour la navbar
        if (window.bottomNav) {
            await window.bottomNav.updateListCount();
        }
        
    } catch (error) {
        // Restaurer si erreur
        btn.innerHTML = originalContent;
        btn.style.color = '';
        
        if (error.message?.includes('duplicate') || error.status === 409) {
            showToast('Déjà dans votre liste', 'info');
        } else {
            handleApiError(error);
        }
    }
}

/**
 * Retire de la liste
 */
async function removeFromList(videoId, btn) {
    if (!videoId) return;
    
    animateButton(btn);
    
    try {
        await api.removeFromWatchlist(videoId);
        showToast('Retiré de votre liste', 'success');
        
        // Animer la suppression
        const item = btn.closest('.mylist-item, .movie-card');
        if (item) {
            item.style.transform = 'translateX(100%)';
            item.style.opacity = '0';
            setTimeout(() => item.remove(), 300);
        }
        
        // Mettre à jour le compteur
        if (window.bottomNav) {
            await window.bottomNav.updateListCount();
        }
        
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Toggle favoris
 */
async function toggleFavorite(videoId, btn) {
    animateButton(btn);
    
    const isFav = btn.classList.contains('active');
    
    try {
        if (isFav) {
            await api.removeFromFavorites(videoId);
            btn.classList.remove('active');
            showToast('Retiré des favoris', 'info');
        } else {
            await api.addToFavorites(videoId);
            btn.classList.add('active');
            showToast('Ajouté aux favoris !', 'success');
        }
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Affiche la bande-annonce
 */
function showTrailer(videoId) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay trailer-modal active';
    modal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h3 class="modal-title">Bande-annonce</h3>
                <button class="modal-close" data-action="close-modal">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            <div class="trailer-container">
                <iframe 
                    src="https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen>
                </iframe>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden';
    
    // Fermer au clic sur l'overlay
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
    
    // Fermer avec Escape
    document.addEventListener('keydown', handleEscape);
}

/**
 * Affiche les épisodes
 */
function showEpisodes(seriesId) {
    showToast('Chargement des épisodes...', 'info');
    window.location.href = `player.html?id=${seriesId}&tab=episodes`;
}

/**
 * Partage le contenu
 */
async function shareContent() {
    const shareData = {
        title: 'ZeeXClub',
        text: 'Regarde ce contenu incroyable sur ZeeXClub !',
        url: window.location.href
    };
    
    if (navigator.share) {
        try {
            await navigator.share(shareData);
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('Share failed:', err);
            }
        }
    } else {
        try {
            await navigator.clipboard.writeText(shareData.url);
            showToast('Lien copié dans le presse-papiers !', 'success');
        } catch (err) {
            showToast('Impossible de copier le lien', 'error');
        }
    }
}

/**
 * Charge plus de contenu
 */
async function loadMoreContent(btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Chargement...';
    
    try {
        // Implémenter la logique de pagination ici
        await new Promise(r => setTimeout(r, 1000)); // Simulation
        showToast('Plus de contenu chargé', 'success');
    } catch (error) {
        handleApiError(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Charger plus';
    }
}

/**
 * Gestion de la recherche
 */
function initSearch() {
    const searchToggle = document.getElementById('search-toggle');
    const searchPanel = document.querySelector('.search-panel');
    const searchInput = document.querySelector('.search-input');
    
    if (!searchToggle) return;
    
    // Toggle recherche
    window.toggleSearch = () => {
        searchPanel?.classList.toggle('active');
        if (searchPanel?.classList.contains('active')) {
            searchInput?.focus();
        }
    };
    
    window.closeSearch = () => {
        searchPanel?.classList.remove('active');
    };
    
    // Recherche avec debounce
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            const query = e.target.value.trim();
            if (query.length >= 2) {
                performSearch(query);
            }
        }, 300));
    }
}

/**
 * Effectue la recherche
 */
async function performSearch(query) {
    try {
        const results = await api.searchVideos(query);
        displaySearchResults(results.data);
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Affiche les résultats de recherche
 */
function displaySearchResults(results) {
    const container = document.querySelector('.search-results');
    if (!container) return;
    
    if (!results || results.length === 0) {
        container.innerHTML = '<p class="no-results">Aucun résultat trouvé</p>';
        return;
    }
    
    container.innerHTML = results.map(movie => `
        <div class="search-result-item" data-id="${movie.id}">
            <img src="${movie.poster_url || '/img/default-poster.png'}" alt="${movie.title}">
            <div class="result-info">
                <h4>${movie.title}</h4>
                <span>${movie.year} • ${(movie.genre || [])[0] || 'Action'}</span>
            </div>
        </div>
    `).join('');
    
    // Clic sur résultat
    container.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            navigateToPlayer(item.dataset.id);
        });
    });
}

/**
 * Menu utilisateur
 */
function toggleUserMenu() {
    const menu = document.querySelector('.user-dropdown');
    if (menu) {
        menu.classList.toggle('active');
    }
}

function closeUserMenu() {
    const menu = document.querySelector('.user-dropdown');
    if (menu) {
        menu.classList.remove('active');
    }
}

/**
 * Déconnexion
 */
async function handleLogout() {
    try {
        await signOut();
        showToast('Déconnecté avec succès', 'success');
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1000);
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Ferme le modal actif
 */
function closeModal() {
    const modal = document.querySelector('.modal-overlay');
    if (modal) {
        modal.classList.add('closing');
        setTimeout(() => {
            modal.remove();
            document.body.style.overflow = '';
        }, 300);
    }
    document.removeEventListener('keydown', handleEscape);
}

/**
 * Gestion de la touche Escape
 */
function handleEscape(e) {
    if (e.key === 'Escape') {
        closeModal();
        closeSearch();
        closeUserMenu();
    }
}

/**
 * Animation de bouton
 */
function animateButton(btn) {
    btn.style.transform = 'scale(0.95)';
    setTimeout(() => {
        btn.style.transform = '';
    }, 150);
}

/**
 * Header scroll effect
 */
function initHeaderScroll() {
    const header = document.getElementById('main-header');
    if (!header) return;
    
    let lastScroll = 0;
    let ticking = false;
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                const currentScroll = window.scrollY;
                
                // Ajouter/enlever la classe scrolled
                header.classList.toggle('scrolled', currentScroll > 50);
                
                // Cacher/montrer le header au scroll
                if (currentScroll > lastScroll && currentScroll > 100) {
                    header.style.transform = 'translateY(-100%)';
                } else {
                    header.style.transform = 'translateY(0)';
                }
                
                lastScroll = currentScroll;
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
}

/**
 * Scroll fluide
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

/**
 * ✅ CORRECTION: Implémentation complète des pages
 */
async function loadCatalogPage() {
    console.log('Loading catalog...');
    // Le catalog.js gère cette page
}

async function loadTrendingPage() {
    console.log('Loading trending...');
    // Charger les tendances
    try {
        const { data } = await api.getTrending(20);
        const grid = document.getElementById('trending-grid');
        if (grid) {
            renderSectionCards('trending-grid', data, 'Aucune tendance');
        }
    } catch (error) {
        handleApiError(error);
    }
}

async function loadMyListPage() {
    console.log('Loading my list...');
    // La page mylist gère son propre contenu
}

async function loadProfilePage() {
    console.log('Loading profile...');
    // La page profile gère son propre contenu
}

// Exposer les fonctions globales
window.AppState = AppState;
window.navigateToPlayer = navigateToPlayer;
window.addToList = addToList;
window.removeFromList = removeFromList;
window.toggleFavorite = toggleFavorite;
window.showTrailer = showTrailer;
window.showEpisodes = showEpisodes;
window.shareContent = shareContent;
window.closeModal = closeModal;
window.toggleSearch = toggleSearch;
window.toggleUserMenu = toggleUserMenu;
window.handleLogout = handleLogout;

export {
    AppState,
    navigateToPlayer,
    addToList,
    removeFromList
};
