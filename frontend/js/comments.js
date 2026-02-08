// frontend/js/comments.js
/**
 * Système de commentaires avancé pour ZeeXClub
 * Gestion complète des commentaires avec animations et interactions
 */

import { supabase, getCurrentUser } from './supabase-client.js';
import api from './api.js';
import { 
    showToast, 
    formatDate, 
    escapeHtml, 
    animate,
    debounce 
} from './utils.js';

/**
 * Classe principale pour gérer les commentaires
 */
export class CommentsManager {
    constructor(containerId, videoId) {
        this.container = document.getElementById(containerId);
        this.videoId = videoId;
        this.comments = [];
        this.currentUser = null;
        this.isLoading = false;
        this.hasMore = true;
        this.page = 1;
        this.perPage = 20;
        
        this.init();
    }
    
    async init() {
        if (!this.container) return;
        
        this.currentUser = await getCurrentUser();
        this.renderSkeleton();
        await this.loadComments();
        this.setupRealtime();
        this.setupInfiniteScroll();
    }
    
    /**
     * Rend le squelette de chargement
     */
    renderSkeleton() {
        this.container.innerHTML = `
            <div class="comments-header">
                <h3>
                    <svg class="icon" viewBox="0 0 24 24">
                        <path d="M21.99 4c0-1.1-.89-2-1.99-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18z"/>
                    </svg>
                    Commentaires
                    <span class="comments-count">0</span>
                </h3>
                <div class="comments-sort">
                    <button class="sort-btn active" data-sort="newest">Plus récents</button>
                    <button class="sort-btn" data-sort="popular">Populaires</button>
                </div>
            </div>
            
            <form class="comment-form" id="comment-form">
                <div class="form-avatar">
                    <img src="${this.currentUser?.user_metadata?.avatar_url || '/img/default-avatar.png'}" 
                         alt="Votre avatar">
                </div>
                <div class="form-input-wrapper">
                    <textarea 
                        id="comment-input"
                        placeholder="Ajouter un commentaire public..."
                        rows="1"
                        maxlength="1000"
                    ></textarea>
                    <div class="form-actions">
                        <span class="char-count">0/1000</span>
                        <button type="button" class="btn-cancel" style="display:none;">Annuler</button>
                        <button type="submit" class="btn-submit" disabled>Commenter</button>
                    </div>
                </div>
            </form>
            
            <div class="comments-list" id="comments-list">
                ${this.renderSkeletonItems(3)}
            </div>
            
            <button class="load-more" id="load-more" style="display:none;">
                Charger plus de commentaires
            </button>
        `;
        
        this.bindEvents();
    }
    
    renderSkeletonItems(count) {
        return Array(count).fill(0).map(() => `
            <div class="comment-skeleton">
                <div class="skeleton-avatar"></div>
                <div class="skeleton-content">
                    <div class="skeleton-line short"></div>
                    <div class="skeleton-line"></div>
                    <div class="skeleton-line medium"></div>
                </div>
            </div>
        `).join('');
    }
    
    /**
     * Charge les commentaires depuis l'API
     */
    async loadComments(append = false) {
        if (this.isLoading || !this.hasMore) return;
        
        this.isLoading = true;
        
        try {
            const { data } = await api.getComments(this.videoId, this.perPage * this.page);
            
            if (!append) {
                this.comments = data || [];
            } else {
                this.comments.push(...(data || []));
            }
            
            this.hasMore = (data || []).length === this.perPage * this.page;
            this.renderComments(append);
            this.updateCount();
            
        } catch (error) {
            console.error('Failed to load comments:', error);
            this.showError();
        } finally {
            this.isLoading = false;
        }
    }
    
    /**
     * Rend les commentaires dans la liste
     */
    renderComments(append = false) {
        const list = this.container.querySelector('#comments-list');
        
        if (!append) {
            list.innerHTML = '';
        } else {
            // Retirer le skeleton de chargement
            const skeletons = list.querySelectorAll('.comment-skeleton');
            skeletons.forEach(s => s.remove());
        }
        
        this.comments.forEach((comment, index) => {
            const existing = list.querySelector(`[data-comment-id="${comment.id}"]`);
            if (existing) return; // Éviter les doublons
            
            const el = this.createCommentElement(comment);
            
            // Animation staggered
            el.style.animationDelay = `${index * 0.05}s`;
            el.classList.add('animate-in');
            
            list.appendChild(el);
        });
        
        // Bouton charger plus
        const loadMoreBtn = this.container.querySelector('#load-more');
        if (loadMoreBtn) {
            loadMoreBtn.style.display = this.hasMore ? 'block' : 'none';
        }
    }
    
    /**
     * Crée un élément de commentaire
     */
    createCommentElement(comment) {
        const div = document.createElement('div');
        div.className = 'comment-item';
        div.dataset.commentId = comment.id;
        
        const user = comment.users || {};
        const isOwner = this.currentUser?.id === comment.user_id;
        const isLiked = comment.user_liked; // Si on implémente le like utilisateur
        
        const timeAgo = this.getTimeAgo(comment.created_at);
        
        div.innerHTML = `
            <div class="comment-avatar">
                <img src="${user.avatar_url || '/img/default-avatar.png'}" 
                     alt="${escapeHtml(user.display_name || 'Utilisateur')}">
                ${user.verified ? '<span class="verified-badge">✓</span>' : ''}
            </div>
            
            <div class="comment-body">
                <div class="comment-header">
                    <span class="comment-author">${escapeHtml(user.display_name || user.email || 'Anonyme')}</span>
                    <span class="comment-time" title="${formatDate(comment.created_at)}">${timeAgo}</span>
                </div>
                
                <p class="comment-text">${this.formatCommentText(comment.comment_text)}</p>
                
                <div class="comment-actions-bar">
                    <button class="action-btn like-btn ${isLiked ? 'liked' : ''}" 
                            data-comment-id="${comment.id}">
                        <svg viewBox="0 0 24 24" class="icon">
                            <path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/>
                        </svg>
                        <span class="count">${comment.likes || 0}</span>
                    </button>
                    
                    <button class="action-btn reply-btn" data-comment-id="${comment.id}">
                        Répondre
                    </button>
                    
                    ${isOwner ? `
                        <button class="action-btn edit-btn" data-comment-id="${comment.id}">
                            Modifier
                        </button>
                        <button class="action-btn delete-btn" data-comment-id="${comment.id}">
                            Supprimer
                        </button>
                    ` : `
                        <button class="action-btn report-btn" data-comment-id="${comment.id}">
                            Signaler
                        </button>
                    `}
                </div>
                
                <!-- Formulaire de réponse (caché par défaut) -->
                <form class="reply-form" style="display:none;" data-parent-id="${comment.id}">
                    <textarea placeholder="Répondre à ${escapeHtml(user.display_name || 'cet utilisateur')}..."
                              rows="1"></textarea>
                    <div class="form-actions">
                        <button type="button" class="btn-cancel-reply">Annuler</button>
                        <button type="submit" class="btn-submit-reply">Répondre</button>
                    </div>
                </form>
            </div>
        `;
        
        this.bindCommentEvents(div, comment);
        
        return div;
    }
    
    /**
     * Formate le texte du commentaire (liens, mentions, etc.)
     */
    formatCommentText(text) {
        // Échapper le HTML
        let formatted = escapeHtml(text);
        
        // URLs cliquables
        formatted = formatted.replace(
            /(https?:\/\/[^\s]+)/g,
            '<a href="$1" target="_blank" rel="noopener" class="comment-link">$1</a>'
        );
        
        // Mentions @utilisateur
        formatted = formatted.replace(
            /@(\w+)/g,
            '<span class="mention">@$1</span>'
        );
        
        // Hashtags #tag
        formatted = formatted.replace(
            /#(\w+)/g,
            '<span class="hashtag">#$1</span>'
        );
        
        return formatted;
    }
    
    /**
     * Calcule le temps relatif
     */
    getTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        const intervals = {
            année: 31536000,
            mois: 2592000,
            semaine: 604800,
            jour: 86400,
            heure: 3600,
            minute: 60
        };
        
        for (const [unit, secondsInUnit] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsInUnit);
            if (interval >= 1) {
                return `il y a ${interval} ${unit}${interval > 1 ? 's' : ''}`;
            }
        }
        
        return "à l'instant";
    }
    
    /**
     * Lie les événements aux éléments de commentaire
     */
    bindCommentEvents(element, comment) {
        // Like
        const likeBtn = element.querySelector('.like-btn');
        likeBtn?.addEventListener('click', () => this.toggleLike(comment.id, likeBtn));
        
        // Reply
        const replyBtn = element.querySelector('.reply-btn');
        const replyForm = element.querySelector('.reply-form');
        replyBtn?.addEventListener('click', () => {
            replyForm.style.display = replyForm.style.display === 'none' ? 'block' : 'none';
        });
        
        // Cancel reply
        const cancelReplyBtn = element.querySelector('.btn-cancel-reply');
        cancelReplyBtn?.addEventListener('click', () => {
            replyForm.style.display = 'none';
        });
        
        // Submit reply
        replyForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = replyForm.querySelector('textarea').value.trim();
            if (text) {
                this.postReply(comment.id, text);
                replyForm.style.display = 'none';
                replyForm.querySelector('textarea').value = '';
            }
        });
        
        // Delete
        const deleteBtn = element.querySelector('.delete-btn');
        deleteBtn?.addEventListener('click', () => this.deleteComment(comment.id, element));
        
        // Edit
        const editBtn = element.querySelector('.edit-btn');
        editBtn?.addEventListener('click', () => this.startEdit(comment.id, element));
    }
    
    /**
     * Lie les événements principaux
     */
    bindEvents() {
        // Formulaire principal
        const form = this.container.querySelector('#comment-form');
        const textarea = this.container.querySelector('#comment-input');
        const charCount = this.container.querySelector('.char-count');
        const cancelBtn = this.container.querySelector('.btn-cancel');
        const submitBtn = this.container.querySelector('.btn-submit');
        
        // Auto-resize textarea
        textarea?.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
            
            const len = textarea.value.length;
            charCount.textContent = `${len}/1000`;
            submitBtn.disabled = len < 3;
            
            cancelBtn.style.display = len > 0 ? 'block' : 'none';
        });
        
        // Focus/blur effects
        textarea?.addEventListener('focus', () => {
            form?.classList.add('focused');
        });
        
        // Cancel
        cancelBtn?.addEventListener('click', () => {
            textarea.value = '';
            textarea.style.height = 'auto';
            charCount.textContent = '0/1000';
            submitBtn.disabled = true;
            cancelBtn.style.display = 'none';
            form?.classList.remove('focused');
        });
        
        // Submit
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = textarea.value.trim();
            if (text.length < 3) return;
            
            await this.postComment(text);
            
            // Reset form
            textarea.value = '';
            textarea.style.height = 'auto';
            charCount.textContent = '0/1000';
            submitBtn.disabled = true;
            cancelBtn.style.display = 'none';
        });
        
        // Tri
        const sortBtns = this.container.querySelectorAll('.sort-btn');
        sortBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                sortBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.sortComments(btn.dataset.sort);
            });
        });
        
        // Charger plus
        const loadMoreBtn = this.container.querySelector('#load-more');
        loadMoreBtn?.addEventListener('click', () => {
            this.page++;
            this.loadComments(true);
        });
    }
    
    /**
     * Publie un nouveau commentaire
     */
    async postComment(text) {
        try {
            const { data } = await api.postComment(this.videoId, text);
            
            // Ajouter en haut de la liste
            this.comments.unshift(data);
            this.renderComments();
            this.updateCount();
            
            showToast('Commentaire publié !', 'success');
            
        } catch (error) {
            handleApiError(error, 'Erreur lors de la publication');
        }
    }
    
    /**
     * Publie une réponse
     */
    async postReply(parentId, text) {
        // TODO: Implémenter les réponses imbriquées dans la base de données
        showToast('Réponse publiée !', 'success');
    }
    
    /**
     * Supprime un commentaire
     */
    async deleteComment(commentId, element) {
        if (!confirm('Supprimer ce commentaire ?')) return;
        
        try {
            // Animation de suppression
            element.style.transform = 'translateX(-100%)';
            element.style.opacity = '0';
            
            setTimeout(async () => {
                // TODO: Appel API suppression
                element.remove();
                this.comments = this.comments.filter(c => c.id !== commentId);
                this.updateCount();
                showToast('Commentaire supprimé', 'success');
            }, 300);
            
        } catch (error) {
            handleApiError(error);
        }
    }
    
    /**
     * Démarre l'édition d'un commentaire
     */
    startEdit(commentId, element) {
        const textEl = element.querySelector('.comment-text');
        const currentText = this.comments.find(c => c.id === commentId)?.comment_text || '';
        
        const textarea = document.createElement('textarea');
        textarea.className = 'edit-textarea';
        textarea.value = currentText;
        textarea.rows = 3;
        
        const saveBtn = document.createElement('button');
        saveBtn.className = 'btn-save-edit';
        saveBtn.textContent = 'Enregistrer';
        
        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn-cancel-edit';
        cancelBtn.textContent = 'Annuler';
        
        const actions = document.createElement('div');
        actions.className = 'edit-actions';
        actions.appendChild(cancelBtn);
        actions.appendChild(saveBtn);
        
        // Remplacer le texte par le formulaire
        textEl.style.display = 'none';
        textEl.parentNode.insertBefore(textarea, textEl.nextSibling);
        textEl.parentNode.insertBefore(actions, textarea.nextSibling);
        
        // Focus
        textarea.focus();
        
        // Cancel
        cancelBtn.addEventListener('click', () => {
            textarea.remove();
            actions.remove();
            textEl.style.display = '';
        });
        
        // Save
        saveBtn.addEventListener('click', async () => {
            const newText = textarea.value.trim();
            if (newText && newText !== currentText) {
                // TODO: Appel API modification
                textEl.innerHTML = this.formatCommentText(newText);
            }
            
            textarea.remove();
            actions.remove();
            textEl.style.display = '';
        });
    }
    
    /**
     * Toggle like sur un commentaire
     */
    async toggleLike(commentId, btn) {
        const isLiked = btn.classList.contains('liked');
        const countEl = btn.querySelector('.count');
        let count = parseInt(countEl.textContent) || 0;
        
        if (isLiked) {
            btn.classList.remove('liked');
            countEl.textContent = Math.max(0, count - 1);
        } else {
            btn.classList.add('liked');
            // Animation
            animate(btn, 'pulse');
            countEl.textContent = count + 1;
        }
        
        // TODO: Appel API like/unlike
    }
    
    /**
     * Trie les commentaires
     */
    sortComments(sortType) {
        if (sortType === 'newest') {
            this.comments.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        } else if (sortType === 'popular') {
            this.comments.sort((a, b) => (b.likes || 0) - (a.likes || 0));
        }
        
        this.renderComments();
    }
    
    /**
     * Met à jour le compteur
     */
    updateCount() {
        const countEl = this.container.querySelector('.comments-count');
        if (countEl) {
            countEl.textContent = this.comments.length;
            animate(countEl, 'bounce');
        }
    }
    
    /**
     * Configure le temps réel Supabase
     */
    setupRealtime() {
        // Écouter les nouveaux commentaires
        supabase
            .channel(`comments:${this.videoId}`)
            .on('postgres_changes', {
                event: 'INSERT',
                schema: 'public',
                table: 'comments',
                filter: `video_id=eq.${this.videoId}`
            }, (payload) => {
                // Nouveau commentaire reçu
                if (payload.new.user_id !== this.currentUser?.id) {
                    this.comments.unshift(payload.new);
                    this.renderComments();
                    this.updateCount();
                    showToast('Nouveau commentaire !', 'info');
                }
            })
            .subscribe();
    }
    
    /**
     * Configure le scroll infini
     */
    setupInfiniteScroll() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && this.hasMore && !this.isLoading) {
                    this.page++;
                    this.loadComments(true);
                }
            });
        }, { rootMargin: '100px' });
        
        const loadMoreBtn = this.container.querySelector('#load-more');
        if (loadMoreBtn) {
            observer.observe(loadMoreBtn);
        }
    }
    
    /**
     * Affiche une erreur
     */
    showError() {
        this.container.querySelector('#comments-list').innerHTML = `
            <div class="comments-error">
                <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
                <p>Impossible de charger les commentaires</p>
                <button onclick="location.reload()">Réessayer</button>
            </div>
        `;
    }
}

// Export pour utilisation
export default CommentsManager;
