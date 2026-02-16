/**
 * Gestion de l'inscription ZeeXClub
 */

class RegisterForm {
    constructor() {
        this.form = document.getElementById('registerForm');
        this.password = document.getElementById('password');
        this.confirmPassword = document.getElementById('confirmPassword');
        this.strengthBar = document.getElementById('strengthBar');
        this.strengthText = document.getElementById('strengthText');
        this.username = document.getElementById('username');
        this.email = document.getElementById('email');
        this.acceptTerms = document.getElementById('acceptTerms');
        this.submitBtn = this.form.querySelector('.btn-auth');
        
        this.API_URL = window.location.hostname === 'localhost' 
            ? 'http://localhost:8000' 
            : 'https://zeexclub.koyeb.app';
        
        this.init();
    }

    init() {
        // Validation mot de passe en temps réel
        this.password.addEventListener('input', (e) => this.checkPasswordStrength(e.target.value));
        
        // Validation confirmation mot de passe
        this.confirmPassword.addEventListener('input', () => this.checkPasswordMatch());
        
        // Validation email en temps réel
        this.email.addEventListener('blur', () => this.validateEmailRealtime());
        
        // Validation username
        this.username.addEventListener('blur', () => this.validateUsernameRealtime());
        
        // Soumission formulaire
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Social auth buttons
        this.initSocialAuth();
    }

    checkPasswordStrength(value) {
        let strength = 0;
        
        if (value.length >= 5) strength++;
        if (value.match(/[a-z]/) && value.match(/[A-Z]/)) strength++;
        if (value.match(/[0-9]/)) strength++;
        if (value.match(/[^a-zA-Z0-9]/)) strength++;

        this.strengthBar.className = 'strength-bar';
        
        if (value.length === 0) {
            this.strengthBar.style.width = '0%';
            this.strengthText.textContent = 'Force du mot de passe';
            this.strengthText.style.color = 'var(--text-muted)';
        } else if (strength <= 1) {
            this.strengthBar.classList.add('weak');
            this.strengthBar.style.width = '33%';
            this.strengthText.textContent = 'Faible';
            this.strengthText.style.color = 'var(--error-color)';
        } else if (strength === 2) {
            this.strengthBar.classList.add('medium');
            this.strengthBar.style.width = '66%';
            this.strengthText.textContent = 'Moyen';
            this.strengthText.style.color = 'var(--warning-color)';
        } else {
            this.strengthBar.classList.add('strong');
            this.strengthBar.style.width = '100%';
            this.strengthText.textContent = 'Fort';
            this.strengthText.style.color = 'var(--success-color)';
        }

        // Vérifier si les mots de passe correspondent si confirmPassword n'est pas vide
        if (this.confirmPassword.value) {
            this.checkPasswordMatch();
        }

        return strength;
    }

    checkPasswordMatch() {
        const password = this.password.value;
        const confirm = this.confirmPassword.value;
        
        if (!confirm) return;
        
        if (password !== confirm) {
            this.confirmPassword.style.borderColor = 'var(--error-color)';
            this.showFieldError(this.confirmPassword, 'Les mots de passe ne correspondent pas');
        } else {
            this.confirmPassword.style.borderColor = 'var(--success-color)';
            this.removeFieldError(this.confirmPassword);
        }
    }

    validateEmailRealtime() {
        const email = this.email.value;
        if (!email) return;
        
        if (!this.validateEmail(email)) {
            this.email.style.borderColor = 'var(--error-color)';
            this.showFieldError(this.email, 'Adresse email invalide');
        } else {
            this.email.style.borderColor = 'var(--success-color)';
            this.removeFieldError(this.email);
        }
    }

    validateUsernameRealtime() {
        const username = this.username.value;
        if (!username) return;
        
        if (username.length < 3) {
            this.username.style.borderColor = 'var(--error-color)';
            this.showFieldError(this.username, 'Minimum 3 caractères');
        } else if (!/^[a-zA-Z0-9_]+$/.test(username)) {
            this.username.style.borderColor = 'var(--error-color)';
            this.showFieldError(this.username, 'Caractères alphanumériques uniquement');
        } else {
            this.username.style.borderColor = 'var(--success-color)';
            this.removeFieldError(this.username);
        }
    }

    showFieldError(input, message) {
        // Supprimer l'erreur existante
        this.removeFieldError(input);
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.style.cssText = `
            color: var(--error-color);
            font-size: 0.8rem;
            margin-top: 5px;
            display: flex;
            align-items: center;
            gap: 5px;
        `;
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        
        input.parentElement.appendChild(errorDiv);
    }

    removeFieldError(input) {
        const existingError = input.parentElement.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
    }

    validateForm() {
        const password = this.password.value;
        const confirm = this.confirmPassword.value;
        const email = this.email.value;
        const username = this.username.value;

        // Reset des erreurs
        this.clearAllErrors();

        // Vérifications
        if (username.length < 3) {
            this.showError('Le nom d\'utilisateur doit faire au moins 3 caractères');
            this.username.focus();
            return false;
        }

        if (!/^[a-zA-Z0-9_]+$/.test(username)) {
            this.showError('Le nom d\'utilisateur ne doit contenir que des lettres, chiffres et underscores');
            this.username.focus();
            return false;
        }

        if (!this.validateEmail(email)) {
            this.showError('Adresse email invalide');
            this.email.focus();
            return false;
        }

        if (password.length < 5) {
            this.showError('Le mot de passe doit faire au moins 5 caractères');
            this.password.focus();
            return false;
        }

        if (password !== confirm) {
            this.showError('Les mots de passe ne correspondent pas');
            this.confirmPassword.focus();
            return false;
        }

        if (!this.acceptTerms.checked) {
            this.showError('Vous devez accepter les conditions d\'utilisation');
            return false;
        }

        return true;
    }

    validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    showError(message) {
        // Supprimer l'erreur existante
        this.clearAllErrors();
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'auth-error';
        errorDiv.style.cssText = `
            background: rgba(229, 9, 20, 0.1);
            border: 1px solid var(--error-color);
            color: var(--error-color);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
            animation: shake 0.5s ease-in-out;
        `;
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
        `;
        
        // Insérer avant le formulaire
        this.form.parentElement.insertBefore(errorDiv, this.form);
        
        // Auto-suppression après 5 secondes
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }

    clearAllErrors() {
        const existingErrors = document.querySelectorAll('.auth-error');
        existingErrors.forEach(error => error.remove());
        
        // Reset des bordures
        [this.username, this.email, this.password, this.confirmPassword].forEach(input => {
            input.style.borderColor = '';
        });
    }

    setLoading(loading) {
        if (loading) {
            this.submitBtn.disabled = true;
            this.submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Création en cours...';
            this.submitBtn.style.opacity = '0.7';
        } else {
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> S\'inscrire';
            this.submitBtn.style.opacity = '1';
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        if (!this.validateForm()) {
            return;
        }

        this.setLoading(true);

        const userData = {
            username: this.username.value.trim(),
            email: this.email.value.trim(),
            password: this.password.value
        };

        try {
            // Appel API vers le backend FastAPI
            const response = await fetch(`${this.API_URL}/api/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Erreur lors de l\'inscription');
            }

            // Stockage du token et des infos utilisateur
            localStorage.setItem('zeexclub_token', data.access_token);
            localStorage.setItem('zeexclub_user', JSON.stringify({
                id: data.user_id,
                username: data.username,
                email: data.email,
                is_admin: data.is_admin || false
            }));

            // Redirection avec animation
            this.showSuccess('Compte créé avec succès ! Redirection...');
            
            setTimeout(() => {
                window.location.href = 'index.html?welcome=true';
            }, 1500);

        } catch (error) {
            this.showError(error.message || 'Erreur de connexion au serveur');
            this.setLoading(false);
        }
    }

    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'auth-success';
        successDiv.style.cssText = `
            background: rgba(46, 204, 113, 0.1);
            border: 1px solid var(--success-color);
            color: var(--success-color);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
        `;
        successDiv.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>${message}</span>
        `;
        
        this.form.parentElement.insertBefore(successDiv, this.form);
    }

    initSocialAuth() {
        // Google OAuth
        const googleBtn = document.querySelector('.social-btn.google');
        if (googleBtn) {
            googleBtn.addEventListener('click', () => {
                // Redirection vers l'endpoint OAuth Google
                window.location.href = `${this.API_URL}/api/auth/google`;
            });
        }

        // Discord OAuth
        const discordBtn = document.querySelector('.social-btn.discord');
        if (discordBtn) {
            discordBtn.addEventListener('click', () => {
                window.location.href = `${this.API_URL}/api/auth/discord`;
            });
        }

        // Telegram OAuth
        const telegramBtn = document.querySelector('.social-btn.telegram');
        if (telegramBtn) {
            telegramBtn.addEventListener('click', () => {
                window.location.href = `${this.API_URL}/api/auth/telegram`;
            });
        }
    }
}

// Animation shake pour les erreurs
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-10px); }
        75% { transform: translateX(10px); }
    }
`;
document.head.appendChild(style);

// Initialisation quand le DOM est chargé
document.addEventListener('DOMContentLoaded', () => {
    new RegisterForm();
});
