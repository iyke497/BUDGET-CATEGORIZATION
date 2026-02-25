// fmoh2024/static/js/main.js

// Global utility functions
const FMOH = {
    // Format currency
    formatCurrency: (amount) => {
        return new Intl.NumberFormat('en-NG', {
            style: 'currency',
            currency: 'NGN',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    },
    
    // Format percentage
    formatPercentage: (value) => {
        return `${value.toFixed(1)}%`;
    },
    
    // Show loading spinner
    showLoading: (element) => {
        const originalContent = element.innerHTML;
        element.innerHTML = '<span class="loading"></span>';
        element.disabled = true;
        return originalContent;
    },
    
    // Hide loading spinner
    hideLoading: (element, originalContent) => {
        element.innerHTML = originalContent;
        element.disabled = false;
    },
    
    // Make API request
    api: async (url, options = {}) => {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },
    
    // Show notification
    notify: (message, type = 'info') => {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="close" onclick="this.parentElement.style.display='none';">&times;</button>
        `;
        
        const container = document.querySelector('.flash-messages') || document.createElement('div');
        if (!container.classList.contains('flash-messages')) {
            container.className = 'flash-messages container';
            document.querySelector('.main-content').prepend(container);
        }
        
        container.appendChild(alert);
        
        // Auto dismiss after 5 seconds
        setTimeout(() => {
            alert.style.animation = 'slideDown 0.3s reverse';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            alert.style.animation = 'slideDown 0.3s reverse';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
    
    // Add active class to current nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});