/**
 * Daena Core Application Logic
 * Handles global UI state, sidebar/operator toggling, and notifications.
 */

const App = {
    state: {
        sidebarCollapsed: localStorage.getItem('daena_sidebar_collapsed') === 'true',
        operatorOpen: false, // Operator panel closed by default
        currentPath: window.location.pathname
    },

    init() {
        this.bindEvents();
        this.applySidebarState();
        this.highlightCurrentNav();
        console.log('Daena App Initialized');
    },

    bindEvents() {
        // Sidebar Toggle
        const sidebarToggle = document.getElementById('sidebar-toggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }

        // Operator Toggle
        const operatorToggle = document.getElementById('operator-toggle');
        if (operatorToggle) {
            operatorToggle.addEventListener('click', () => this.toggleOperator());
        }

        // Close Operator Button
        const closeOperator = document.getElementById('close-operator');
        if (closeOperator) {
            closeOperator.addEventListener('click', () => this.toggleOperator(false));
        }
    },

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
        localStorage.setItem('daena_sidebar_collapsed', this.state.sidebarCollapsed);
        this.applySidebarState();
    },

    applySidebarState() {
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('main-content');
        const labels = document.querySelectorAll('.sidebar-label');
        const icon = document.getElementById('sidebar-toggle-icon');

        if (this.state.sidebarCollapsed) {
            sidebar.classList.add('w-20');
            sidebar.classList.remove('w-64');
            labels.forEach(el => el.classList.add('hidden'));
            if (icon) icon.classList.add('rotate-180');
        } else {
            sidebar.classList.remove('w-20');
            sidebar.classList.add('w-64');
            labels.forEach(el => el.classList.remove('hidden'));
            if (icon) icon.classList.remove('rotate-180');
        }
    },

    toggleOperator(forceState = null) {
        this.state.operatorOpen = forceState !== null ? forceState : !this.state.operatorOpen;
        const operatorPanel = document.getElementById('operator-panel');

        if (this.state.operatorOpen) {
            operatorPanel.classList.remove('translate-x-full');
        } else {
            operatorPanel.classList.add('translate-x-full');
        }
    },

    highlightCurrentNav() {
        const links = document.querySelectorAll('.nav-link');
        links.forEach(link => {
            if (link.getAttribute('href') === this.state.currentPath) {
                link.classList.add('bg-white/10', 'text-white');
                link.classList.remove('text-gray-400', 'hover:bg-white/5');
            }
        });
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type} text-sm text-white`;

        let icon = '';
        switch (type) {
            case 'success': icon = '<i class="fas fa-check-circle text-green-400"></i>'; break;
            case 'error': icon = '<i class="fas fa-exclamation-circle text-red-400"></i>'; break;
            case 'warning': icon = '<i class="fas fa-exclamation-triangle text-yellow-400"></i>'; break;
            default: icon = '<i class="fas fa-info-circle text-blue-400"></i>';
        }

        toast.innerHTML = `${icon}<span>${message}</span>`;
        container.appendChild(toast);

        // Remove after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
