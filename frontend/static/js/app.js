/**
 * Global App JavaScript - Sidebar, Theme, Utilities
 */

// Sidebar Collapse/Expand
class SidebarManager {
    constructor() {
        this.sidebar = document.getElementById('sidebar');
        this.mainContent = document.querySelector('.main-content') || document.querySelector('main');
        this.toggleBtn = document.getElementById('sidebar-toggle');
        this.storageKey = 'daena_sidebar_collapsed';

        this.init();
    }

    init() {
        if (!this.sidebar || !this.toggleBtn) {
            console.warn('Sidebar elements not found');
            return;
        }

        // Restore state from localStorage
        const isCollapsed = localStorage.getItem(this.storageKey) === 'true';
        if (isCollapsed) {
            this.collapse(false); // false = no animation on load
        }

        // Add click handler
        this.toggleBtn.addEventListener('click', () => {
            if (this.sidebar.classList.contains('collapsed')) {
                this.expand();
            } else {
                this.collapse();
            }
        });
    }

    collapse(animate = true) {
        if (!animate) {
            this.sidebar.classList.add('no-transition');
        }

        this.sidebar.classList.add('collapsed');

        // Change icon
        const icon = this.toggleBtn.querySelector('i');
        if (icon) {
            icon.classList.remove('fa-chevron-left');
            icon.classList.add('fa-chevron-right');
        }

        // Adjust main content width
        if (this.mainContent) {
            this.mainContent.style.marginLeft = '80px'; // Collapsed sidebar width
        }

        // Save state
        localStorage.setItem(this.storageKey, 'true');

        if (!animate) {
            setTimeout(() => {
                this.sidebar.classList.remove('no-transition');
            }, 50);
        }
    }

    expand(animate = true) {
        if (!animate) {
            this.sidebar.classList.add('no-transition');
        }

        this.sidebar.classList.remove('collapsed');

        // Change icon
        const icon = this.toggleBtn.querySelector('i');
        if (icon) {
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-left');
        }

        // Adjust main content width
        if (this.mainContent) {
            this.mainContent.style.marginLeft = '256px'; // Full sidebar width (w-64 = 16rem = 256px)
        }

        // Save state
        localStorage.setItem(this.storageKey, 'false');

        if (!animate) {
            setTimeout(() => {
                this.sidebar.classList.remove('no-transition');
            }, 50);
        }
    }
}

// Initialize sidebar manager
let sidebarManager = null;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        sidebarManager = new SidebarManager();
    });
} else {
    sidebarManager = new SidebarManager();
}

// Toast Notification System (Reusable)
window.showToast = function (message, type = 'info') {
    // Remove existing toasts
    const existingToast = document.getElementById('global-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast
    const toast = document.createElement('div');
    toast.id = 'global-toast';
    toast.className = `fixed bottom-4 right-4 z-50 px-6 py-3 rounded-lg shadow-lg text-white transition-all transform translate-y-0 opacity-100`;

    // Color based on type
    const colors = {
        'success': 'bg-green-600',
        'error': 'bg-red-600',
        'warning': 'bg-yellow-600',
        'info': 'bg-blue-600'
    };
    toast.classList.add(colors[type] || colors['info']);

    // Icon based on type
    const icons = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };
    const icon = icons[type] || icons['info'];

    toast.innerHTML = `
        <div class="flex items-center gap-3">
            <i class="fas ${icon}"></i>
            <span>${message}</span>
        </div>
    `;

    document.body.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-y-2', 'opacity-0');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
};

// Loading Indicator
window.showLoading = function () {
    let loader = document.getElementById('global-loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'global-loader';
        loader.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50';
        loader.innerHTML = `
            <div class="glass-panel p-8 rounded-2xl">
                <div class="flex items-center gap-4">
                    <i class="fas fa-circle-notch fa-spin text-3xl text-daena-gold"></i>
                    <span class="text-white text-lg">Loading...</span>
                </div>
            </div>
        `;
        document.body.appendChild(loader);
    }
    loader.style.display = 'flex';
};

window.hideLoading = function () {
    const loader = document.getElementById('global-loader');
    if (loader) {
        loader.style.display = 'none';
    }
};

// Format timestamp helper
window.formatTimestamp = function (timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
        return 'just now';
    }

    // Less than 1 hour
    if (diff < 3600000) {
        const mins = Math.floor(diff / 60000);
        return `${mins} min${mins > 1 ? 's' : ''} ago`;
    }

    // Less than 1 day
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }

    // Same year
    if (date.getFullYear() === now.getFullYear()) {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    // Different year
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

// Console log
console.log('✅ Global app.js loaded');
