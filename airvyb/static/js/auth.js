// Common authentication utilities
class AuthAPI {
    static async request(endpoint, data) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(data)
            });
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            return { success: false, message: 'Network error' };
        }
    }
    
    static async register(formData) {
        return await this.request('/ajax/register/', formData);
    }
    
    static async login(identifier, password) {
        return await this.request('/ajax/login/', {
            username: identifier,
            password: password
        });
    }
    
    static async verifyEmail(userId, code) {
        return await this.request('/ajax/verify-email/', {
            user_id: userId,
            code: code
        });
    }
    
    static async resendVerification(userId) {
        return await this.request('/ajax/resend-verification/', {
            user_id: userId
        });
    }
    
    static async requestPasswordReset(identifier) {
        return await this.request('/ajax/password-reset-request/', {
            email_or_phone: identifier
        });
    }
    
    static async confirmPasswordReset(userId, code, newPassword) {
        return await this.request('/ajax/password-reset-confirm/', {
            user_id: userId,
            code: code,
            new_password: newPassword
        });
    }
    
    static async logout() {
        return await this.request('/ajax/logout/', {});
    }
    
    static async getProfile() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        
        try {
            const response = await fetch('/ajax/get-profile/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrfToken
                }
            });
            
            return await response.json();
        } catch (error) {
            console.error('Get profile failed:', error);
            return { success: false };
        }
    }
    
    static async updateProfile(formData) {
        // For file uploads, use FormData instead of JSON
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        
        try {
            const response = await fetch('/ajax/update-profile/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });
            
            return await response.json();
        } catch (error) {
            console.error('Update profile failed:', error);
            return { success: false };
        }
    }
    
    static async changePassword(currentPassword, newPassword) {
        return await this.request('/ajax/change-password/', {
            current_password: currentPassword,
            new_password: newPassword
        });
    }
}

// Form validation utilities
class FormValidator {
    static validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    static validatePhone(phone) {
        // Kenyan phone validation
        const cleaned = phone.replace(/\D/g, '');
        return /^07[0-9]{8}$/.test(cleaned);
    }
    
    static validatePassword(password) {
        const minLength = 8;
        const hasUpperCase = /[A-Z]/.test(password);
        const hasLowerCase = /[a-z]/.test(password);
        const hasNumbers = /\d/.test(password);
        const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);
        
        return password.length >= minLength && 
               hasUpperCase && 
               hasLowerCase && 
               hasNumbers && 
               hasSpecialChar;
    }
    
    static validateAge(dateOfBirth) {
        if (!dateOfBirth) return false;
        
        const dob = new Date(dateOfBirth);
        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const monthDiff = today.getMonth() - dob.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
            age--;
        }
        
        return age >= 18 && age <= 35;
    }
}

// UI Utilities
class AuthUI {
    static showLoading(button, text = 'Processing...') {
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
        return originalText;
    }
    
    static resetButton(button, originalText) {
        button.disabled = false;
        button.innerHTML = originalText;
    }
    
    static showError(elementId, message) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = message;
            element.style.display = 'block';
        }
    }
    
    static clearErrors() {
        document.querySelectorAll('.error-message').forEach(el => {
            el.textContent = '';
            el.style.display = 'none';
        });
    }
    
    static showToast(message, type = 'success') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        // Add to page
        document.body.appendChild(toast);
        
        // Show with animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Remove after delay
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Session Management
class SessionManager {
    static setAuthToken(token) {
        localStorage.setItem('auth_token', token);
    }
    
    static getAuthToken() {
        return localStorage.getItem('auth_token');
    }
    
    static clearAuthToken() {
        localStorage.removeItem('auth_token');
    }
    
    static isLoggedIn() {
        return !!this.getAuthToken();
    }
}

export { AuthAPI, FormValidator, AuthUI, SessionManager };