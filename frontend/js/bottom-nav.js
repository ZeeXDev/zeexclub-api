// frontend/js/bottom-nav.js
/**
 * Navigation en bas avec animations et gestion d'état
 */

class BottomNav {
    constructor() {
        this.currentPage = this.detectCurrentPage();
        this.init();
    }
    
    detectCurrentPage() {
        const path = window.location.pathname;
        const page = path.split('/').pop() || 'index.html';
        
        const pageMap = {
            'index.html': 'home',
            'catalog.html': 'catalog',
            'trending.html': 'trending',
            'mylist.html': 'mylist',
            'profile.html': 'profile'
        };
        
        return pageMap[page] || 'home';
    }
    
    init() {
        this.render();
        this.attachEvents();
        this.updateActiveState();
        this.animateEntry();
    }
    
    render() {
        // Vérifier si déjà présent
        if (document.querySelector('.bottom-nav')) return;
        
        const nav = document.createElement('nav');
        nav.className = 'bottom-nav';
        nav.innerHTML = `
            <div class="bottom-nav-container">
                <a href="index.html" class="bottom-nav-item" data-page="home">
                    <svg class="bottom-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                        <polyline points="9 22 9 12 15 12 15 22"></polyline>
                    </svg>
                    <span class="bottom-nav-label">Accueil</span>
                </a>
                
                <a href="catalog.html" class="bottom-nav-item" data-page="catalog">
                    <svg class="bottom-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="7" height="7"></rect>
                        <rect x="14" y="3" width="7" height="7"></rect>
                        <rect x="14" y="14" width="7" height="7"></rect>
                        <rect x="3" y="14" width="7" height="7"></rect>
                    </svg>
                    <span class="bottom-nav-label">Catalogue</span>
                </a>
                
                <a href="trending.html" class="bottom-nav-item" data-page="trending">
                    <svg class="bottom-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
                        <polyline points="17 6 23 6 23 12"></polyline>
                    </svg>
                    <span class="bottom-nav-label">Tendances</span>
                    <span class="nav-badge">HOT</span>
                </a>
                
                <a href="mylist.html" class="bottom-nav-item" data-page="mylist" data-auth>
                    <svg class="bottom-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                    </svg>
                    <span class="bottom-nav-label">Ma Liste</span>
                    <span class="nav-badge" id="nav-list-count" style="display:none;">0</span>
                </a>
                
                <a href="profile.html" class="bottom-nav-item" data-page="profile" data-auth>
                    <svg class="bottom-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                    <span class="bottom-nav-label">Profil</span>
                </a>
            </div>
        `;
        
        document.body.appendChild(nav);
        
        // Gérer l'auth
        this.updateAuthState();
    }
    
    attachEvents() {
        // Ripple effect au clic
        document.querySelectorAll('.bottom-nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Position du clic pour le ripple
                const rect = item.getBoundingClientRect();
                const x = ((e.clientX - rect.left) / rect.width) * 100;
                const y = ((e.clientY - rect.top) / rect.height) * 100;
                item.style.setProperty('--x', `${x}%`);
                item.style.setProperty('--y', `${y}%`);
                
                // Animation de transition de page
                this.animateTransition(item);
            });
        });
        
        // Swipe up pour cacher/montrer
        let lastScrollY = window.scrollY;
        let ticking = false;
        
        window.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(() => {
                    this.handleScroll(lastScrollY);
                    lastScrollY = window.scrollY;
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }
    
    handleScroll(lastScrollY) {
        const nav = document.querySelector('.bottom-nav');
        if (!nav) return;
        
        const currentScrollY = window.scrollY;
        const scrollingDown = currentScrollY > lastScrollY;
        const scrollThreshold = 100;
        
        if (scrollingDown && currentScrollY > scrollThreshold) {
            nav.style.transform = 'translateY(100%)';
            nav.style.opacity = '0';
        } else {
            nav.style.transform = 'translateY(0)';
            nav.style.opacity = '1';
        }
    }
    
    animateTransition(item) {
        // Créer un effet de transition vers la nouvelle page
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            inset: 0;
            background: var(--primary-red);
            z-index: 9999;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        `;
        document.body.appendChild(overlay);
        
        // Flash rouge rapide
        requestAnimationFrame(() => {
            overlay.style.opacity = '0.1';
            setTimeout(() => {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 300);
            }, 100);
        });
    }
    
    updateActiveState() {
        document.querySelectorAll('.bottom-nav-item').forEach(item => {
            const page = item.dataset.page;
            item.classList.toggle('active', page === this.currentPage);
        });
    }
    
    updateAuthState() {
        // Vérifier si l'utilisateur est connecté
        const user = localStorage.getItem('zeex_user');
        
        document.querySelectorAll('.bottom-nav-item[data-auth]').forEach(item => {
            if (!user) {
                item.style.display = 'none';
            } else {
                item.style.display = 'flex';
            }
        });
        
        // Mettre à jour le compteur de liste
        if (user) {
            this.updateListCount();
        }
    }
    
    async updateListCount() {
        try {
            // Importer dynamiquement pour éviter les dépendances circulaires
            const { default: api } = await import('./api.js');
            const { data } = await api.getWatchlist();
            const count = data?.length || 0;
            
            const badge = document.getElementById('nav-list-count');
            if (badge) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = count > 0 ? 'flex' : 'none';
            }
        } catch (e) {
            console.log('Failed to update list count');
        }
    }
    
    animateEntry() {
        const items = document.querySelectorAll('.bottom-nav-item');
        items.forEach((item, index) => {
            item.style.opacity = '0';
            item.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                item.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
                item.style.opacity = '1';
                item.style.transform = 'translateY(0)';
            }, 100 + (index * 50));
        });
    }
}

// Initialiser au chargement
document.addEventListener('DOMContentLoaded', () => {
    window.bottomNav = new BottomNav();
});

export default BottomNav;
